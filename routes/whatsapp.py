from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models import db, Cliente, Comunicacion, PlantillaComunicacion, Configuracion, Recibo
from datetime import datetime
from urllib.parse import quote

whatsapp_bp = Blueprint('whatsapp', __name__)


@whatsapp_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 24

    query = Cliente.query

    buscar = request.args.get('buscar', '')
    if buscar:
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(f'%{buscar}%'),
                Cliente.dni.ilike(f'%{buscar}%'),
                Cliente.telefono.ilike(f'%{buscar}%')
            )
        )

    filtro = request.args.get('filtro', 'todos')
    if filtro == 'con_telefono':
        query = query.filter(Cliente.telefono.isnot(None), Cliente.telefono != '')
    elif filtro == 'con_alerta':
        query = query.filter(Cliente.alerta_devoluciones == True)
    elif filtro == 'contactados':
        subquery = db.session.query(Comunicacion.cliente_id).filter(
            Comunicacion.tipo == 'whatsapp'
        ).subquery()
        query = query.filter(Cliente.id.in_(subquery))
    elif filtro == 'no_contactados':
        subquery = db.session.query(Comunicacion.cliente_id).filter(
            Comunicacion.tipo == 'whatsapp'
        ).subquery()
        query = query.filter(~Cliente.id.in_(subquery))

    if not filtro:
        query = query.filter(Cliente.telefono.isnot(None), Cliente.telefono != '')

    pagination = query.order_by(Cliente.nombre).paginate(
        page=page, per_page=per_page, error_out=False
    )

    plantillas = PlantillaComunicacion.query.filter_by(tipo='whatsapp').all()

    company_phone = Configuracion.query.filter_by(clave='whatsapp_empresa').first()

    return render_template('whatsapp/index.html',
                           clientes=pagination.items,
                           pagination=pagination,
                           buscar=buscar,
                           filtro=filtro,
                           plantillas=plantillas,
                           company_phone=company_phone.valor if company_phone else '')


@whatsapp_bp.route('/web')
@login_required
def whatsapp_web_embebido():
    clientes_con_telefono = Cliente.query.filter(
        Cliente.telefono.isnot(None),
        Cliente.telefono != ''
    ).order_by(Cliente.nombre).all()

    return render_template('whatsapp/web.html',
                           clientes=clientes_con_telefono)


@whatsapp_bp.route('/cliente/<int:id>')
@login_required
def cliente_chat(id):
    cliente = Cliente.query.get_or_404(id)
    if not cliente.telefono:
        flash('Este cliente no tiene telefono registrado', 'warning')
        return redirect(url_for('whatsapp.index'))

    plantilla_id = request.args.get('plantilla', type=int)
    mensaje = request.args.get('mensaje', '')

    from models import Poliza
    polizas = cliente.polizas_activas
    poliza_num = polizas[0].numero_poliza if polizas else ''

    if plantilla_id:
        plantilla = PlantillaComunicacion.query.get(plantilla_id)
        if plantilla:
            contenido = plantilla.contenido
            contenido = contenido.replace('{nombre}', cliente.nombre)
            contenido = contenido.replace('{poliza}', poliza_num)
            contenido = contenido.replace('{importe}', '')
            contenido = contenido.replace('{fecha}', datetime.utcnow().strftime('%d/%m/%Y'))
            contenido = contenido.replace('{enlace}', '')
        else:
            contenido = ''
    elif mensaje:
        contenido = mensaje
    else:
        contenido = f'Hola {cliente.nombre.split()[0]}, te escribo de la oficina Ocaso en Armilla. '

    encoded = quote(contenido)
    phone = cliente.telefono.replace(' ', '').replace('+', '')
    if not phone.startswith('34') and len(phone) == 9:
        phone = '34' + phone

    whatsapp_url = f'https://wa.me/{phone}?text={encoded}'

    com = Comunicacion(
        cliente_id=cliente.id,
        tipo='whatsapp',
        plantilla=plantilla.nombre if plantilla_id else 'mensaje directo',
        contenido=contenido,
        enviado=True
    )
    db.session.add(com)
    db.session.commit()

    return redirect(whatsapp_url)


@whatsapp_bp.route('/enviar-mensaje', methods=['POST'])
@login_required
def enviar_mensaje():
    cliente_id = request.form.get('cliente_id', type=int)
    mensaje = request.form.get('mensaje', '')

    if not cliente_id or not mensaje:
        flash('Faltan datos', 'danger')
        return redirect(request.referrer or url_for('whatsapp.index'))

    cliente = Cliente.query.get_or_404(cliente_id)
    if not cliente.telefono:
        flash('El cliente no tiene telefono', 'warning')
        return redirect(request.referrer or url_for('whatsapp.index'))

    phone = cliente.telefono.replace(' ', '').replace('+', '')
    if not phone.startswith('34') and len(phone) == 9:
        phone = '34' + phone

    encoded = quote(mensaje)
    whatsapp_url = f'https://wa.me/{phone}?text={encoded}'

    com = Comunicacion(
        cliente_id=cliente.id,
        tipo='whatsapp',
        contenido=mensaje,
        enviado=True
    )
    db.session.add(com)
    db.session.commit()

    return redirect(whatsapp_url)


@whatsapp_bp.route('/historial')
@login_required
def historial():
    page = request.args.get('page', 1, type=int)
    per_page = 30

    query = Comunicacion.query.filter(Comunicacion.tipo == 'whatsapp')

    cliente_id = request.args.get('cliente_id', type=int)
    if cliente_id:
        query = query.filter(Comunicacion.cliente_id == cliente_id)

    pagination = query.order_by(Comunicacion.fecha.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template('whatsapp/historial.html',
                           comunicaciones=pagination.items,
                           pagination=pagination)


@whatsapp_bp.route('/vista-previa/<int:id>')
@login_required
def vista_previa(id):
    cliente = Cliente.query.get_or_404(id)
    plantillas = PlantillaComunicacion.query.filter_by(tipo='whatsapp').all()

    from models import Poliza
    polizas = cliente.polizas_activas
    poliza_num = polizas[0].numero_poliza if polizas else ''

    return render_template('whatsapp/vista_previa.html',
                           cliente=cliente,
                           plantillas=plantillas,
                           poliza_num=poliza_num)
