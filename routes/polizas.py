from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from models import db, Poliza, Cliente, Siniestro
from datetime import date, datetime

polizas_bp = Blueprint('polizas', __name__)


@polizas_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 25

    query = db.session.query(Poliza, Cliente).join(Cliente)

    ramo = request.args.get('ramo', '')
    if ramo:
        query = query.filter(Poliza.ramo == ramo)

    estado = request.args.get('estado', 'todas')
    if estado == 'activas':
        query = query.filter(Poliza.activa == True)
    elif estado == 'bajas':
        query = query.filter(Poliza.activa == False)

    compania = request.args.get('compania', '')
    if compania:
        query = query.filter(Poliza.compania == compania)

    vencimiento = request.args.get('vencimiento', '')
    hoy = date.today()
    if vencimiento == '30dias':
        from datetime import timedelta
        limite = hoy + timedelta(days=30)
        query = query.filter(Poliza.fecha_vencimiento <= limite, Poliza.fecha_vencimiento >= hoy)
    elif vencimiento == '60dias':
        from datetime import timedelta
        limite = hoy + timedelta(days=60)
        query = query.filter(Poliza.fecha_vencimiento <= limite, Poliza.fecha_vencimiento >= hoy)
    elif vencimiento == 'vencidas':
        query = query.filter(Poliza.fecha_vencimiento < hoy, Poliza.activa == True)

    buscar = request.args.get('buscar', '')
    if buscar:
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(f'%{buscar}%'),
                Cliente.dni.ilike(f'%{buscar}%'),
                Poliza.numero_poliza.ilike(f'%{buscar}%'),
                Poliza.matricula.ilike(f'%{buscar}%')
            )
        )

    sort = request.args.get('sort', 'fecha_efecto')
    order = request.args.get('order', 'desc')

    if sort == 'prima':
        col = Poliza.prima_anual
    elif sort == 'vencimiento':
        col = Poliza.fecha_vencimiento
    elif sort == 'ramo':
        col = Poliza.ramo
    elif sort == 'cliente':
        col = Cliente.nombre
    else:
        col = Poliza.fecha_efecto

    if order == 'asc':
        query = query.order_by(col.asc())
    else:
        query = query.order_by(col.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    totales = {
        'activas': Poliza.query.filter(Poliza.activa == True).count(),
        'bajas': Poliza.query.filter(Poliza.activa == False).count(),
        'prima_total': db.session.query(db.func.sum(Poliza.prima_anual)).filter(Poliza.activa == True).scalar() or 0,
    }

    return render_template('polizas/index.html',
                           resultados=pagination.items,
                           pagination=pagination,
                           ramo=ramo, estado=estado, compania=compania,
                           vencimiento=vencimiento, buscar=buscar,
                           sort=sort, order=order,
                           totales=totales,
                           today=date.today())
