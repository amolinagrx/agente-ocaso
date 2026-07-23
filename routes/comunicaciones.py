from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models import db, PlantillaComunicacion, Comunicacion, Cliente
from datetime import datetime

comunicaciones_bp = Blueprint('comunicaciones', __name__)

PLANTILLAS_PREDEFINIDAS = [
    {
        'nombre': 'Recibo devuelto',
        'tipo': 'whatsapp',
        'contenido': 'Hola {nombre},\n\nTe escribo de la oficina de seguros Ocaso en Armilla. Hemos detectado que el recibo de tu póliza {poliza} por importe de {importe}€ ha sido devuelto.\n\n¿Podrías revisar tu cuenta bancaria y contactarnos para resolverlo?\n\nGracias,\nOficina Ocaso Armilla'
    },
    {
        'nombre': 'Renovación pendiente',
        'tipo': 'whatsapp',
        'contenido': 'Hola {nombre},\n\nTe recordamos que tu póliza {poliza} vence próximamente el día {fecha}. Nos gustaría enviarte un presupuesto de renovación.\n\n¿Hablamos?\n\nOficina Ocaso Armilla'
    },
    {
        'nombre': 'Cita confirmada',
        'tipo': 'whatsapp',
        'contenido': 'Hola {nombre},\n\nConfirmamos tu cita para el día {fecha} en nuestra oficina de Armilla.\n\n¡Te esperamos!\n\nOficina Ocaso Armilla'
    },
    {
        'nombre': 'Presupuesto listo',
        'tipo': 'whatsapp',
        'contenido': 'Hola {nombre},\n\nTu presupuesto para la póliza {poliza} ya está listo. Puedes consultarlo en el siguiente enlace:\n\n{enlace}\n\nSaludos,\nOficina Ocaso Armilla'
    },
    {
        'nombre': 'Siniestro actualizado',
        'tipo': 'whatsapp',
        'contenido': 'Hola {nombre},\n\nTe informamos que tu expediente de siniestro {poliza} ha sido actualizado. Estado actual: en tramitación.\n\nTe mantendremos informado.\n\nOficina Ocaso Armilla'
    },
    {
        'nombre': 'Felicitación de cumpleaños',
        'tipo': 'whatsapp',
        'contenido': '¡Felicidades {nombre}! 🎂\n\nTodo el equipo de Ocaso Armilla te desea un feliz día.\n\nUn abrazo,\nOficina Ocaso Armilla'
    }
]

EMAIL_PLANTILLAS = [
    {
        'nombre': 'Recibo devuelto (Email)',
        'tipo': 'email',
        'asunto': 'Incidencia con tu recibo - Ocaso Seguros',
        'contenido': '<div style="font-family:Arial;max-width:600px;margin:0 auto;border:1px solid #ddd;border-radius:8px;overflow:hidden"><div style="background:#CC0000;color:white;padding:20px;text-align:center"><h2 style="margin:0">Ocaso Seguros</h2></div><div style="padding:20px"><p>Estimado/a <strong>{nombre}</strong>,</p><p>Te informamos que el recibo de tu póliza <strong>{poliza}</strong> por importe de <strong>{importe}€</strong> ha sido devuelto por tu entidad bancaria.</p><p>Te agradeceríamos que revisaras los datos bancarios y te pusieras en contacto con nosotros para regularizar la situación.</p><p>Puedes llamarnos al <strong>958 123 456</strong>.</p><p>Un saludo,<br><strong>Oficina Ocaso Armilla</strong></p></div><div style="background:#f5f5f5;padding:10px;text-align:center;font-size:12px;color:#666">Ocaso Seguros - Oficina Armilla (Granada)</div></div>'
    },
    {
        'nombre': 'Renovación pendiente (Email)',
        'tipo': 'email',
        'asunto': 'Próxima renovación de tu seguro - Ocaso Seguros',
        'contenido': '<div style="font-family:Arial;max-width:600px;margin:0 auto;border:1px solid #ddd;border-radius:8px;overflow:hidden"><div style="background:#CC0000;color:white;padding:20px;text-align:center"><h2 style="margin:0">Ocaso Seguros</h2></div><div style="padding:20px"><p>Estimado/a <strong>{nombre}</strong>,</p><p>Te recordamos que tu póliza <strong>{poliza}</strong> vence el próximo <strong>{fecha}</strong>.</p><p>Nos gustaría enviarte un presupuesto de renovación con las mejores condiciones. Contacta con nosotros para revisarlo.</p><p>Un saludo,<br><strong>Oficina Ocaso Armilla</strong></p></div></div>'
    }
]

SMS_PLANTILLAS = [
    {
        'nombre': 'Recibo devuelto (SMS)',
        'tipo': 'sms',
        'contenido': 'Ocaso: Recibo de su poliza {poliza} devuelto ({importe}€). Contacte con nosotros: 958 123 456'
    },
    {
        'nombre': 'Recordatorio cita (SMS)',
        'tipo': 'sms',
        'contenido': 'Ocaso Armilla: Le recordamos su cita del {fecha}. Oficina C/ Real 12, Armilla. Tfno: 958 123 456'
    }
]


@comunicaciones_bp.route('/')
@login_required
def index():
    # Ensure default templates exist
    _seed_plantillas()
    plantillas = PlantillaComunicacion.query.order_by(PlantillaComunicacion.tipo, PlantillaComunicacion.nombre).all()
    return render_template('comunicaciones/index.html', plantillas=plantillas)


@comunicaciones_bp.route('/usar/<int:id>')
@login_required
def usar_plantilla(id):
    plantilla = PlantillaComunicacion.query.get_or_404(id)
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    return render_template('comunicaciones/usar.html',
                           plantilla=plantilla,
                           clientes=clientes)


@comunicaciones_bp.route('/previsualizar', methods=['POST'])
@login_required
def previsualizar():
    plantilla_id = request.form.get('plantilla_id', type=int)
    cliente_id = request.form.get('cliente_id', type=int)

    plantilla = PlantillaComunicacion.query.get_or_404(plantilla_id)
    cliente = Cliente.query.get_or_404(cliente_id) if cliente_id else None

    contenido = plantilla.contenido
    if cliente:
        contenido = contenido.replace('{nombre}', cliente.nombre)
        contenido = contenido.replace('{poliza}', '000-000')
        contenido = contenido.replace('{importe}', '0.00')
        contenido = contenido.replace('{fecha}', 'DD/MM/AAAA')
        contenido = contenido.replace('{enlace}', '#')

    # Generate WhatsApp link if applicable
    whatsapp_link = None
    if plantilla.tipo == 'whatsapp' and cliente and cliente.telefono:
        msg_encoded = contenido.replace(' ', '%20').replace('\n', '%0A')
        whatsapp_link = f"https://wa.me/34{cliente.telefono}?text={msg_encoded}"

    mailto_link = None
    if plantilla.tipo == 'email' and cliente and cliente.email:
        import urllib.parse
        asunto = plantilla.asunto or ''
        mailto_link = f"mailto:{cliente.email}?subject={urllib.parse.quote(asunto)}&body={urllib.parse.quote(contenido)}"

    return jsonify({
        'contenido': contenido,
        'whatsapp_link': whatsapp_link,
        'mailto_link': mailto_link,
        'cliente_nombre': cliente.nombre if cliente else '',
        'asunto': plantilla.asunto or ''
    })


@comunicaciones_bp.route('/enviar', methods=['POST'])
@login_required
def enviar():
    plantilla_id = request.form.get('plantilla_id', type=int)
    cliente_id = request.form.get('cliente_id', type=int)
    plantilla = PlantillaComunicacion.query.get_or_404(plantilla_id)
    cliente = Cliente.query.get_or_404(cliente_id)

    contenido_personalizado = request.form.get('contenido', plantilla.contenido)

    com = Comunicacion(
        cliente_id=cliente_id,
        tipo=plantilla.tipo,
        plantilla=plantilla.nombre,
        contenido=contenido_personalizado,
        enviado=True
    )
    db.session.add(com)
    db.session.commit()

    flash(f'Comunicación registrada para {cliente.nombre}', 'success')
    return redirect(url_for('comunicaciones.index'))


@comunicaciones_bp.route('/nueva-plantilla', methods=['POST'])
@login_required
def nueva_plantilla():
    plantilla = PlantillaComunicacion(
        nombre=request.form.get('nombre'),
        tipo=request.form.get('tipo'),
        asunto=request.form.get('asunto'),
        contenido=request.form.get('contenido')
    )
    db.session.add(plantilla)
    db.session.commit()
    flash('Plantilla creada', 'success')
    return redirect(url_for('comunicaciones.index'))


@comunicaciones_bp.route('/plantilla/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_plantilla(id):
    plantilla = PlantillaComunicacion.query.get_or_404(id)
    db.session.delete(plantilla)
    db.session.commit()
    flash('Plantilla eliminada', 'success')
    return redirect(url_for('comunicaciones.index'))


def _seed_plantillas():
    if PlantillaComunicacion.query.count() == 0:
        for p in PLANTILLAS_PREDEFINIDAS + EMAIL_PLANTILLAS + SMS_PLANTILLAS:
            db.session.add(PlantillaComunicacion(
                nombre=p['nombre'],
                tipo=p['tipo'],
                asunto=p.get('asunto', ''),
                contenido=p['contenido']
            ))
        db.session.commit()
