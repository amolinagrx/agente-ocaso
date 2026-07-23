from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models import db, Renovacion, Poliza, Cliente
from datetime import date, timedelta
from utils.pdf import generar_pdf_renovaciones

renovaciones_bp = Blueprint('renovaciones', __name__)

ESTADOS = {
    'no_contactado': 'No contactado',
    'contactado': 'Contactado',
    'presupuesto_enviado': 'Presupuesto enviado',
    'confirmado': 'Confirmado'
}


@renovaciones_bp.route('/')
@login_required
def index():
    hoy = date.today()
    limite = hoy + timedelta(days=90)

    query = db.session.query(Renovacion, Poliza, Cliente).join(
        Poliza, Renovacion.poliza_id == Poliza.id
    ).join(
        Cliente, Renovacion.cliente_id == Cliente.id
    ).filter(
        Renovacion.fecha_vencimiento <= limite
    )

    estado = request.args.get('estado')
    if estado:
        query = query.filter(Renovacion.estado == estado)

    ramo = request.args.get('ramo')
    if ramo:
        query = query.filter(Poliza.ramo == ramo)

    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    if fecha_desde:
        query = query.filter(Renovacion.fecha_vencimiento >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Renovacion.fecha_vencimiento <= fecha_hasta)

    buscar = request.args.get('buscar')
    if buscar:
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(f'%{buscar}%'),
                Poliza.numero_poliza.ilike(f'%{buscar}%')
            )
        )

    resultados = query.order_by(Renovacion.fecha_vencimiento).all()

    # Counters
    hoy_date = date.today()
    vencer_30 = [r for r, p, c in resultados if
                 r.fecha_vencimiento and (r.fecha_vencimiento - hoy_date).days <= 30]
    pendientes = [r for r, p, c in resultados if r.estado == 'no_contactado']
    confirmados = [r for r, p, c in resultados if r.estado == 'confirmado']

    return render_template('renovaciones/index.html',
                           resultados=resultados,
                           estado=estado,
                           ramo=ramo,
                           buscar=buscar,
                           estados=ESTADOS,
                           hoy=hoy_date,
                           cont_vencer_30=len(vencer_30),
                           cont_pendientes=len(pendientes),
                           cont_confirmados=len(confirmados))


@renovaciones_bp.route('/<int:id>/estado', methods=['POST'])
@login_required
def cambiar_estado(id):
    renovacion = Renovacion.query.get_or_404(id)
    nuevo_estado = request.form.get('estado')
    notas = request.form.get('notas', '')
    if nuevo_estado in ESTADOS:
        renovacion.estado = nuevo_estado
        if notas:
            renovacion.notas = (renovacion.notas or '') + f'\n[{date.today().isoformat()}] {notas}'
        db.session.commit()
        flash('Estado actualizado', 'success')
    return redirect(request.referrer or url_for('renovaciones.index'))


@renovaciones_bp.route('/exportar-pdf')
@login_required
def exportar_pdf():
    hoy = date.today()
    limite = hoy + timedelta(days=90)

    query = db.session.query(Renovacion, Poliza, Cliente).join(
        Poliza, Renovacion.poliza_id == Poliza.id
    ).join(
        Cliente, Renovacion.cliente_id == Cliente.id
    ).filter(
        Renovacion.fecha_vencimiento <= limite
    )

    estado = request.args.get('estado')
    if estado:
        query = query.filter(Renovacion.estado == estado)

    ramo = request.args.get('ramo')
    if ramo:
        query = query.filter(Poliza.ramo == ramo)

    resultados = query.order_by(Renovacion.fecha_vencimiento).all()

    return generar_pdf_renovaciones(resultados)
