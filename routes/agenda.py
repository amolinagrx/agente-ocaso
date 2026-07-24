from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, Agenda
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

agenda_bp = Blueprint('agenda', __name__)

TIPOS = {
    'nota': 'Nota', 'llamada': 'Llamada',
    'reunion': 'Reunion', 'tarea': 'Tarea'
}


@agenda_bp.route('/')
@login_required
def index():
    hoy = date.today()
    vista = request.args.get('vista', 'lista')
    mes = request.args.get('mes', '', type=int) or hoy.month
    anio = request.args.get('anio', '', type=int) or hoy.year

    if vista == 'calendario':
        return _vista_calendario(mes, anio)

    # List view: show entries for selected date or today
    fecha_str = request.args.get('fecha', hoy.isoformat())
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        fecha = hoy

    entradas = Agenda.query.filter_by(
        user_id=current_user.id
    ).filter(
        Agenda.fecha == fecha
    ).order_by(Agenda.created_at.desc()).all()

    fecha_anterior = (fecha - timedelta(days=1)).isoformat()
    fecha_siguiente = (fecha + timedelta(days=1)).isoformat()

    # Next 5 days with entries
    proximos = []
    for i in range(1, 8):
        d = hoy + timedelta(days=i)
        count = Agenda.query.filter_by(user_id=current_user.id).filter(
            Agenda.fecha == d
        ).count()
        if count > 0:
            proximos.append({'fecha': d, 'count': count})

    return render_template('agenda/index.html',
                           entradas=entradas, fecha=fecha,
                           fecha_str=fecha_str, proximos=proximos,
                           fecha_anterior=fecha_anterior,
                           fecha_siguiente=fecha_siguiente,
                           tipos=TIPOS, vista='lista')


def _vista_calendario(mes, anio):
    hoy = date.today()
    inicio = date(anio, mes, 1)
    if mes == 12:
        fin = date(anio + 1, 1, 1) - timedelta(days=1)
    else:
        fin = date(anio, mes + 1, 1) - timedelta(days=1)

    # Get all entries for the month
    entradas = Agenda.query.filter_by(
        user_id=current_user.id
    ).filter(
        Agenda.fecha >= inicio, Agenda.fecha <= fin
    ).order_by(Agenda.fecha).all()

    entradas_por_dia = {}
    for e in entradas:
        dia = e.fecha.day
        if dia not in entradas_por_dia:
            entradas_por_dia[dia] = []
        entradas_por_dia[dia].append(e)

    # Build calendar grid
    semanas = []
    primer_dia_semana = inicio.weekday()  # 0=lunes
    dia_actual = 1
    dias_en_mes = fin.day

    for _ in range(6):
        semana = []
        for w in range(7):
            if (len(semanas) == 0 and w < primer_dia_semana) or dia_actual > dias_en_mes:
                semana.append(None)
            else:
                fecha_dia = date(anio, mes, dia_actual)
                semana.append({
                    'dia': dia_actual,
                    'fecha': fecha_dia,
                    'hoy': fecha_dia == hoy,
                    'entradas': entradas_por_dia.get(dia_actual, [])
                })
                dia_actual += 1
        semanas.append(semana)
        if dia_actual > dias_en_mes:
            break

    mes_anterior = mes - 1 if mes > 1 else 12
    anio_anterior = anio if mes > 1 else anio - 1
    mes_siguiente = mes + 1 if mes < 12 else 1
    anio_siguiente = anio if mes < 12 else anio + 1

    meses_es = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

    return render_template('agenda/index.html',
                           semanas=semanas, mes=mes, anio=anio,
                           mes_nombre=meses_es[mes],
                           mes_anterior=mes_anterior, anio_anterior=anio_anterior,
                           mes_siguiente=mes_siguiente, anio_siguiente=anio_siguiente,
                           tipos=TIPOS, vista='calendario', hoy=hoy)


@agenda_bp.route('/nuevo', methods=['POST'])
@login_required
def nuevo():
    fecha_str = request.form.get('fecha', date.today().isoformat())
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        fecha = date.today()

    entrada = Agenda(
        user_id=current_user.id,
        fecha=fecha,
        titulo=request.form.get('titulo', ''),
        notas=request.form.get('notas', ''),
        tipo=request.form.get('tipo', 'nota')
    )
    db.session.add(entrada)
    db.session.commit()
    flash('Entrada anadida a la agenda', 'success')
    return redirect(url_for('agenda.index', fecha=fecha_str))


@agenda_bp.route('/<int:id>/toggle', methods=['POST'])
@login_required
def toggle(id):
    entrada = Agenda.query.get_or_404(id)
    if entrada.user_id != current_user.id:
        flash('No tienes permiso', 'danger')
        return redirect(url_for('agenda.index'))
    entrada.completado = not entrada.completado
    db.session.commit()
    return redirect(request.referrer or url_for('agenda.index'))


@agenda_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar(id):
    entrada = Agenda.query.get_or_404(id)
    if entrada.user_id != current_user.id:
        flash('No tienes permiso', 'danger')
        return redirect(url_for('agenda.index'))
    db.session.delete(entrada)
    db.session.commit()
    flash('Entrada eliminada', 'success')
    return redirect(request.referrer or url_for('agenda.index'))
