from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from models import db, Recibo, Poliza, Cliente
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)
    fin_mes = (inicio_mes + relativedelta(months=1)) - relativedelta(days=1)

    # KPIs del mes
    recibos_mes = Recibo.query.filter(
        Recibo.fecha_emision >= inicio_mes,
        Recibo.fecha_emision <= fin_mes
    ).all()

    primas_nuevas = sum(r.importe for r in recibos_mes if r.estado == 'cobrado')
    num_nuevas = len([r for r in recibos_mes if r.estado == 'cobrado'])
    devueltos = sum(r.importe for r in recibos_mes if r.estado == 'devuelto')
    num_devueltos = len([r for r in recibos_mes if r.estado == 'devuelto'])
    pendientes = sum(r.importe for r in recibos_mes if r.estado == 'pendiente')

    # Polizas nuevas del mes
    polizas_nuevas_mes = Poliza.query.filter(
        Poliza.fecha_efecto >= inicio_mes,
        Poliza.fecha_efecto <= fin_mes
    ).count()

    polizas_activas = Poliza.query.filter(Poliza.activa == True).count()
    total_clientes = Cliente.query.count()

    # Monthly evolution chart data (last 12 months)
    monthly_data = []
    for i in range(11, -1, -1):
        mes_inicio = (hoy.replace(day=1) - relativedelta(months=i))
        mes_fin = (mes_inicio + relativedelta(months=1)) - relativedelta(days=1)
        mes_label = mes_inicio.strftime('%b %y')

        r_cobrados = Recibo.query.filter(
            Recibo.fecha_emision >= mes_inicio,
            Recibo.fecha_emision <= mes_fin,
            Recibo.estado == 'cobrado'
        ).all()
        r_devueltos = Recibo.query.filter(
            Recibo.fecha_emision >= mes_inicio,
            Recibo.fecha_emision <= mes_fin,
            Recibo.estado == 'devuelto'
        ).all()
        r_pendientes = Recibo.query.filter(
            Recibo.fecha_emision >= mes_inicio,
            Recibo.fecha_emision <= mes_fin,
            Recibo.estado == 'pendiente'
        ).all()

        monthly_data.append({
            'label': mes_label,
            'cobrados': round(sum(r.importe for r in r_cobrados), 2),
            'devueltos': round(sum(r.importe for r in r_devueltos), 2),
            'pendientes': round(sum(r.importe for r in r_pendientes), 2)
        })

    # Ranking by ramo
    ramos_data = db.session.query(
        Poliza.ramo,
        db.func.sum(Poliza.prima_anual).label('total')
    ).filter(Poliza.activa == True).group_by(Poliza.ramo).order_by(db.text('total DESC')).all()

    # Top 10 clients by volume
    top_clientes = db.session.query(
        Cliente.nombre,
        db.func.sum(Poliza.prima_anual).label('total')
    ).join(Poliza).filter(Poliza.activa == True).group_by(Cliente.id).order_by(
        db.text('total DESC')
    ).limit(10).all()

    # Objetivo mensual (configurable, default 15000)
    from models import Configuracion
    objetivo_conf = Configuracion.query.filter_by(clave='objetivo_mensual').first()
    objetivo = float(objetivo_conf.valor) if objetivo_conf else 15000
    cumplimiento = round(primas_nuevas / objetivo * 100, 1) if objetivo > 0 else 0

    return render_template('dashboard/index.html',
                           primas_nuevas=round(primas_nuevas, 2),
                           num_nuevas=num_nuevas,
                           devueltos=round(devueltos, 2),
                           num_devueltos=num_devueltos,
                           pendientes=round(pendientes, 2),
                           polizas_nuevas_mes=polizas_nuevas_mes,
                           polizas_activas=polizas_activas,
                           total_clientes=total_clientes,
                           monthly_data=monthly_data,
                           ramos_data=ramos_data,
                           top_clientes=top_clientes,
                           objetivo=objetivo,
                           cumplimiento=cumplimiento,
                           mes=hoy.strftime('%B %Y'))
