import json
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
