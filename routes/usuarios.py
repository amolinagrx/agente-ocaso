import json
import pyotp
import qrcode
import base64
import io
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, User

usuarios_bp = Blueprint('usuarios', __name__)

MODULOS = [
    ('dashboard', 'Dashboard'),
    ('recibos', 'Recibos'),
    ('clientes', 'Clientes'),
    ('polizas', 'Polizas'),
    ('renovaciones', 'Renovaciones'),
    ('listados', 'Listados'),
    ('siniestros', 'Siniestros'),
    ('comunicaciones', 'Comunicaciones'),
    ('whatsapp', 'WhatsApp'),
    ('asistente', 'Asistente IA'),
    ('ajustes', 'Ajustes'),
    ('usuarios', 'Gestion de Usuarios'),
]

NIVELES = [
    ('rw', 'Lectura y Escritura'),
    ('r', 'Solo Lectura'),
    ('none', 'Sin acceso'),
]


def requiere_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        flash('Acceso denegado. Solo administradores.', 'danger')
        return redirect(url_for('dashboard.index'))


@usuarios_bp.route('/')
@login_required
def index():
    if not current_user.is_admin:
        return requiere_admin()
    usuarios = User.query.order_by(User.username).all()
    return render_template('usuarios/index.html', usuarios=usuarios, modulos=MODULOS, niveles=NIVELES)


@usuarios_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    if not current_user.is_admin:
        return requiere_admin()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        nombre = request.form.get('nombre', '')

        if not username or not password:
            flash('Usuario y contraseña son obligatorios', 'danger')
            return redirect(url_for('usuarios.nuevo'))

        if User.query.filter_by(username=username).first():
            flash('Ese nombre de usuario ya existe', 'danger')
            return redirect(url_for('usuarios.nuevo'))

        is_admin = request.form.get('is_admin') == 'on'

        permisos = {}
        for modulo, _ in MODULOS:
            nivel = request.form.get(f'perm_{modulo}', 'none')
            if nivel != 'none' or is_admin:
                permisos[modulo] = nivel

        user = User(
            username=username, password=password, nombre=nombre,
            is_admin=is_admin, permisos=json.dumps(permisos), activo=True
        )
        db.session.add(user)
        db.session.commit()
        flash(f'Usuario {username} creado', 'success')
        return redirect(url_for('usuarios.index'))

    return render_template('usuarios/nuevo.html', modulos=MODULOS, niveles=NIVELES)


@usuarios_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    if not current_user.is_admin:
        return requiere_admin()

    user = User.query.get_or_404(id)

    try:
        permisos_actuales = json.loads(user.permisos or '{}')
    except json.JSONDecodeError:
        permisos_actuales = {}

    if request.method == 'POST':
        user.nombre = request.form.get('nombre', '')
        user.is_admin = request.form.get('is_admin') == 'on'
        user.activo = request.form.get('activo') == 'on'

        new_password = request.form.get('password', '')
        if new_password:
            user.password = new_password

        permisos = {}
        if not user.is_admin:
            for modulo, _ in MODULOS:
                nivel = request.form.get(f'perm_{modulo}', 'none')
                permisos[modulo] = nivel
        user.permisos = json.dumps(permisos)

        db.session.commit()
        flash(f'Usuario {user.username} actualizado', 'success')
        return redirect(url_for('usuarios.index'))

    return render_template('usuarios/editar.html', usuario=user, modulos=MODULOS,
                           niveles=NIVELES, permisos_actuales=permisos_actuales)


@usuarios_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar(id):
    if not current_user.is_admin:
        return requiere_admin()

    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('No puedes eliminarte a ti mismo', 'danger')
        return redirect(url_for('usuarios.index'))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'Usuario {username} eliminado', 'success')
    return redirect(url_for('usuarios.index'))


@usuarios_bp.route('/<int:id>/2fa/setup', methods=['GET', 'POST'])
@login_required
def setup_2fa(id):
    """Enable TOTP 2FA for a user."""
    user = User.query.get_or_404(id)

    # Only admin or the user themselves can set up 2FA
    if not current_user.is_admin and current_user.id != user.id:
        flash('No tienes permisos para modificar este usuario', 'danger')
        return redirect(url_for('usuarios.index'))

    if request.method == 'POST':
        code = request.form.get('totp_code', '').strip()
        secret = request.form.get('totp_secret', '')

        if not secret or not code:
            flash('Faltan datos', 'danger')
            return redirect(url_for('usuarios.setup_2fa', id=id))

        totp = pyotp.TOTP(secret)
        if totp.verify(code, valid_window=1):
            user.totp_secret = secret
            user.totp_enabled = True
            db.session.commit()
            flash(f'Autenticacion en dos pasos activada para {user.username}', 'success')
            return redirect(url_for('usuarios.index'))
        else:
            flash('Codigo incorrecto. Intentalo de nuevo.', 'danger')
            return redirect(url_for('usuarios.setup_2fa', id=id))

    # Generate new secret
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.username, issuer_name='Ocaso Armilla')

    # Generate QR code as base64
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return render_template('usuarios/2fa_setup.html',
                           usuario=user, secret=secret, uri=uri, qr_b64=qr_b64)


@usuarios_bp.route('/<int:id>/2fa/disable', methods=['POST'])
@login_required
def disable_2fa(id):
    """Disable 2FA for a user."""
    user = User.query.get_or_404(id)

    if not current_user.is_admin:
        flash('Solo el administrador puede desactivar 2FA', 'danger')
        return redirect(url_for('usuarios.index'))

    user.totp_secret = None
    user.totp_enabled = False
    db.session.commit()
    flash(f'2FA desactivado para {user.username}', 'success')
    return redirect(url_for('usuarios.index'))
