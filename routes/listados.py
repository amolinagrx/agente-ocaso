from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from models import db, Poliza, Recibo, Cliente, Siniestro, Renovacion
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

listados_bp = Blueprint('listados', __name__)


@listados_bp.route('/')
@login_required
def index():
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)
    total_polizas_mes = Poliza.query.filter(Poliza.fecha_efecto >= inicio_mes).count()
    total_recibos_pendientes = Recibo.query.filter(Recibo.estado == 'pendiente').count()
    total_siniestros_abiertos = Siniestro.query.filter(
        ~Siniestro.estado.in_(['cerrado', 'resuelto'])
    ).count()
    total_clientes = Cliente.query.count()

    return render_template('listados/index.html',
                           total_polizas_mes=total_polizas_mes,
                           total_recibos_pendientes=total_recibos_pendientes,
                           total_siniestros_abiertos=total_siniestros_abiertos,
                           total_clientes=total_clientes)


@listados_bp.route('/polizas')
@login_required
def polizas():
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    ramo = request.args.get('ramo', '')
    estado = request.args.get('estado', 'todas')
    buscar = request.args.get('buscar', '')

    query = db.session.query(Poliza, Cliente).join(Cliente)

    if fecha_desde:
        query = query.filter(Poliza.fecha_efecto >= _parse_date(fecha_desde))
    if fecha_hasta:
        query = query.filter(Poliza.fecha_efecto <= _parse_date(fecha_hasta))
    if ramo:
        query = query.filter(Poliza.ramo == ramo)
    if estado == 'activas':
        query = query.filter(Poliza.activa == True)
    elif estado == 'bajas':
        query = query.filter(Poliza.activa == False)
    if buscar:
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(f'%{buscar}%'),
                Poliza.numero_poliza.ilike(f'%{buscar}%')
            )
        )

    resultados = query.order_by(Poliza.fecha_efecto.desc()).limit(200).all()

    totales = {
        'count': len(resultados),
        'prima_total': sum(p.prima_anual for p, c in resultados),
        'capital_total': sum(p.capital_asegurado for p, c in resultados),
    }

    return render_template('listados/polizas.html',
                           resultados=resultados,
                           fecha_desde=fecha_desde,
                           fecha_hasta=fecha_hasta,
                           ramo=ramo,
                           estado=estado,
                           buscar=buscar,
                           totales=totales)


@listados_bp.route('/recibos')
@login_required
def recibos():
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    estado = request.args.get('estado', 'todos')
    buscar = request.args.get('buscar', '')

    query = db.session.query(Recibo, Cliente).join(Cliente)

    if fecha_desde:
        query = query.filter(Recibo.fecha_emision >= _parse_date(fecha_desde))
    if fecha_hasta:
        query = query.filter(Recibo.fecha_emision <= _parse_date(fecha_hasta))
    if estado and estado != 'todos':
        query = query.filter(Recibo.estado == estado)
    if buscar:
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(f'%{buscar}%'),
                Recibo.numero_poliza.ilike(f'%{buscar}%')
            )
        )

    resultados = query.order_by(Recibo.fecha_emision.desc()).limit(300).all()

    totales = {
        'count': len(resultados),
        'importe_total': sum(r.importe for r, c in resultados),
        'cobrados': sum(r.importe for r, c in resultados if r.estado == 'cobrado'),
        'devueltos': sum(r.importe for r, c in resultados if r.estado == 'devuelto'),
        'pendientes': sum(r.importe for r, c in resultados if r.estado == 'pendiente'),
    }

    return render_template('listados/recibos.html',
                           resultados=resultados,
                           fecha_desde=fecha_desde,
                           fecha_hasta=fecha_hasta,
                           estado=estado,
                           buscar=buscar,
                           totales=totales)


@listados_bp.route('/produccion')
@login_required
def produccion():
    """Produccion por ramo y mes"""
    anio = request.args.get('anio', '', type=int) or date.today().year
    mes = request.args.get('mes', '', type=int) or None

    # Produccion por ramo (todo el año o mes)
    query = db.session.query(
        Poliza.ramo,
        db.func.count(Poliza.id).label('cantidad'),
        db.func.sum(Poliza.prima_anual).label('total_prima'),
        db.func.sum(Poliza.capital_asegurado).label('total_capital')
    ).filter(Poliza.activa == True)

    if mes:
        inicio = date(anio, mes, 1)
        fin = (inicio + relativedelta(months=1)) - timedelta(days=1)
        query = query.filter(Poliza.fecha_efecto >= inicio, Poliza.fecha_efecto <= fin)

    resultados = query.group_by(Poliza.ramo).order_by(db.text('total_prima DESC')).all()

    # Monthly breakdown for chart
    monthly = []
    for m in range(1, 13):
        inicio = date(anio, m, 1)
        fin = (inicio + relativedelta(months=1)) - timedelta(days=1)
        new_count = Poliza.query.filter(
            Poliza.fecha_efecto >= inicio, Poliza.fecha_efecto <= fin
        ).count()
        new_prima = db.session.query(db.func.sum(Poliza.prima_anual)).filter(
            Poliza.fecha_efecto >= inicio, Poliza.fecha_efecto <= fin
        ).scalar() or 0

        canc_count = Poliza.query.filter(
            Poliza.fecha_baja >= inicio, Poliza.fecha_baja <= fin
        ).count() if hasattr(Poliza, 'fecha_baja') else 0

        monthly.append({
            'mes': f'{m:02d}',
            'nuevas': new_count,
            'prima': int(new_prima),
            'canceladas': canc_count
        })

    totales = {
        'total_polizas': sum(r.cantidad for r in resultados),
        'total_prima': sum(r.total_prima or 0 for r in resultados),
        'total_capital': sum(r.total_capital or 0 for r in resultados),
    }

    return render_template('listados/produccion.html',
                           resultados=resultados,
                           monthly=monthly,
                           anio=anio,
                           mes=mes or '',
                           totales=totales)


@listados_bp.route('/siniestros')
@login_required
def siniestros():
    estado = request.args.get('estado', 'abiertos')
    tipo = request.args.get('tipo', '')
    buscar = request.args.get('buscar', '')

    query = db.session.query(Siniestro, Cliente, Poliza).select_from(Siniestro).join(Cliente).outerjoin(Poliza)

    if estado == 'abiertos':
        query = query.filter(~Siniestro.estado.in_(['cerrado', 'resuelto']))
    elif estado == 'cerrados':
        query = query.filter(Siniestro.estado.in_(['cerrado', 'resuelto']))
    if tipo:
        query = query.filter(Siniestro.tipo == tipo)
    if buscar:
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(f'%{buscar}%'),
                Siniestro.numero_expediente.ilike(f'%{buscar}%')
            )
        )

    resultados = query.order_by(Siniestro.fecha_apertura.desc()).limit(200).all()

    totales = {
        'count': len(resultados),
        'importe_estimado': sum(s.importe_estimado or 0 for s, c, p in resultados),
    }

    return render_template('listados/siniestros.html',
                           resultados=resultados,
                           estado=estado,
                           tipo=tipo,
                           buscar=buscar,
                           totales=totales)


def _parse_date(val):
    if not val:
        return None
    try:
        from datetime import datetime
        return datetime.strptime(str(val), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None
