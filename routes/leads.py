from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, Lead, Cliente, Poliza
from datetime import date, datetime

leads_bp = Blueprint('leads', __name__)

ORIGENES = {'web': 'Web', 'telefono': 'Telefono', 'presencial': 'Presencial',
            'recomendacion': 'Recomendacion', 'otro': 'Otro'}
ESTADOS = {'nuevo': 'Nuevo', 'contactado': 'Contactado', 'presupuesto': 'Presupuesto enviado',
           'ganado': 'Ganado', 'perdido': 'Perdido'}


@leads_bp.route('/')
@login_required
def index():
    estado = request.args.get('estado', '')
    origen = request.args.get('origen', '')
    buscar = request.args.get('buscar', '')

    query = Lead.query

    if estado:
        query = query.filter(Lead.estado == estado)
    if origen:
        query = query.filter(Lead.origen == origen)
    if buscar:
        query = query.filter(
            db.or_(
                Lead.nombre.ilike(f'%{buscar}%'),
                Lead.telefono.ilike(f'%{buscar}%'),
                Lead.email.ilike(f'%{buscar}%')
            )
        )

    leads = query.order_by(Lead.created_at.desc()).limit(200).all()

    return render_template('leads/index.html',
                           leads=leads, estado=estado, origen=origen, buscar=buscar,
                           origenes=ORIGENES, estados=ESTADOS)


@leads_bp.route('/nuevo', methods=['POST'])
@login_required
def nuevo():
    lead = Lead(
        nombre=request.form.get('nombre', ''),
        telefono=request.form.get('telefono', ''),
        email=request.form.get('email', ''),
        dni=request.form.get('dni', ''),
        ramo_interes=request.form.get('ramo_interes', ''),
        origen=request.form.get('origen', 'web'),
        estado=request.form.get('estado', 'nuevo'),
        notas=request.form.get('notas', ''),
        user_id=current_user.id,
        created_at=datetime.utcnow()
    )
    db.session.add(lead)
    db.session.commit()
    flash('Lead creado correctamente', 'success')
    return redirect(url_for('leads.index'))


@leads_bp.route('/<int:id>/editar', methods=['POST'])
@login_required
def editar(id):
    lead = Lead.query.get_or_404(id)
    lead.nombre = request.form.get('nombre', lead.nombre)
    lead.telefono = request.form.get('telefono', lead.telefono)
    lead.email = request.form.get('email', lead.email)
    lead.dni = request.form.get('dni', lead.dni)
    lead.ramo_interes = request.form.get('ramo_interes', lead.ramo_interes)
    lead.origen = request.form.get('origen', lead.origen)
    lead.estado = request.form.get('estado', lead.estado)
    lead.notas = request.form.get('notas', lead.notas)
    lead.updated_at = datetime.utcnow()
    db.session.commit()
    flash('Lead actualizado', 'success')
    return redirect(url_for('leads.index'))


@leads_bp.route('/<int:id>/estado', methods=['POST'])
@login_required
def cambiar_estado(id):
    lead = Lead.query.get_or_404(id)
    nuevo_estado = request.form.get('estado', '')
    if nuevo_estado in ESTADOS:
        lead.estado = nuevo_estado
        lead.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Estado cambiado a {ESTADOS[nuevo_estado]}', 'success')
    return redirect(url_for('leads.index'))


@leads_bp.route('/<int:id>/convertir', methods=['POST'])
@login_required
def convertir(id):
    """Convert a lead to a client."""
    lead = Lead.query.get_or_404(id)

    # Create client from lead data
    cliente = Cliente(
        nombre=lead.nombre,
        dni=lead.dni or '',
        telefono=lead.telefono or '',
        email=lead.email or '',
        direccion=lead.direccion or '',
        codigo_postal=lead.codigo_postal or '',
        poblacion=lead.poblacion or '',
        provincia=lead.provincia or '',
        notas=f'Convertido desde lead. Origen: {ORIGENES.get(lead.origen, lead.origen)}. Notas lead: {lead.notas or ""}'
    )
    db.session.add(cliente)
    db.session.flush()

    lead.estado = 'ganado'
    lead.cliente_id = cliente.id
    lead.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f'Lead convertido a cliente: {cliente.nombre}', 'success')
    return redirect(url_for('clientes.ficha', id=cliente.id))


@leads_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar(id):
    lead = Lead.query.get_or_404(id)
    db.session.delete(lead)
    db.session.commit()
    flash('Lead eliminado', 'success')
    return redirect(url_for('leads.index'))
