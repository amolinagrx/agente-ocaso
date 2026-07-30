import secrets
import functools
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Cliente, Poliza, Siniestro, DocumentoCliente

portal_bp = Blueprint('portal', __name__, url_prefix='/portal')

SESSION_TIMEOUT = timedelta(minutes=30)


def cliente_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        cliente_id = session.get('cliente_id')
        if not cliente_id:
            return redirect(url_for('portal.login'))

        last_activity = session.get('last_activity')
        if last_activity:
            elapsed = datetime.utcnow() - datetime.fromisoformat(last_activity)
            if elapsed > SESSION_TIMEOUT:
                session.clear()
                return redirect(url_for('portal.login'))

        session['last_activity'] = datetime.utcnow().isoformat()
        return f(*args, **kwargs)
    return decorated


def get_cliente():
    cliente_id = session.get('cliente_id')
    if cliente_id:
        return Cliente.query.get(cliente_id)
    return None


@portal_bp.route('/')
def index():
    return redirect(url_for('portal.login'))


@portal_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        dni = request.form.get('dni', '').strip().upper()
        password = request.form.get('password', '')

        cliente = Cliente.query.filter_by(dni=dni, portal_activo=True).first()
        if cliente and cliente.portal_password and check_password_hash(cliente.portal_password, password):
            session.clear()
            session['cliente_id'] = cliente.id
            session['last_activity'] = datetime.utcnow().isoformat()
            session.permanent = True
            return redirect(url_for('portal.dashboard'))

        flash('DNI o contraseña incorrectos', 'danger')

    return render_template('portal/login.html')


@portal_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('portal.login'))


@portal_bp.route('/dashboard')
@cliente_required
def dashboard():
    cliente = get_cliente()
    polizas_activas = Poliza.query.filter_by(cliente_id=cliente.id, activa=True).count()
    siniestros_abiertos = Siniestro.query.filter(
        Siniestro.cliente_id == cliente.id,
        ~Siniestro.estado.in_(['cerrado', 'resuelto'])
    ).count()
    documentos_count = DocumentoCliente.query.filter_by(cliente_id=cliente.id).count()

    return render_template('portal/dashboard.html',
                           cliente=cliente,
                           polizas_activas=polizas_activas,
                           siniestros_abiertos=siniestros_abiertos,
                           documentos_count=documentos_count)


@portal_bp.route('/polizas')
@cliente_required
def polizas():
    cliente = get_cliente()
    polizas = Poliza.query.filter_by(cliente_id=cliente.id).order_by(Poliza.activa.desc(), Poliza.fecha_efecto.desc()).all()
    return render_template('portal/polizas.html', cliente=cliente, polizas=polizas)


@portal_bp.route('/siniestros')
@cliente_required
def siniestros():
    cliente = get_cliente()
    siniestros = Siniestro.query.filter_by(cliente_id=cliente.id).order_by(Siniestro.fecha_apertura.desc()).all()
    return render_template('portal/siniestros.html', cliente=cliente, siniestros=siniestros)


@portal_bp.route('/documentos')
@cliente_required
def documentos():
    cliente = get_cliente()
    docs = DocumentoCliente.query.filter_by(cliente_id=cliente.id).order_by(DocumentoCliente.uploaded_at.desc()).all()
    return render_template('portal/documentos.html', cliente=cliente, documentos=docs)
