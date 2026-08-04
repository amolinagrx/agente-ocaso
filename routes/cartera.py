import os
from datetime import datetime, date
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from flask_login import login_required, current_user
from models import db, CarteraFichero, CarteraPoliza, CarteraBaja, CarteraAlta
from cartera.parser import parse_cartera_xlsx
from cartera.analysis import run_analysis

cartera_bp = Blueprint('cartera', __name__)

MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

CARTERA_DIR = '/data/cartera_ficheros'


@cartera_bp.route('/')
@login_required
def index():
    ficheros = CarteraFichero.query.order_by(CarteraFichero.anio.desc(), CarteraFichero.mes.desc()).all()

    # KPIs
    ultimo = ficheros[0] if ficheros else None
    variacion_mensual = 0
    variacion_anual = 0
    if ultimo:
        prev = CarteraFichero.query.filter_by(
            mes=ultimo.mes - 1 if ultimo.mes > 1 else 12,
            anio=ultimo.anio if ultimo.mes > 1 else ultimo.anio - 1
        ).first()
        if prev and prev.num_polizas:
            variacion_mensual = round((ultimo.num_polizas - prev.num_polizas) / prev.num_polizas * 100, 1)
        prev_year = CarteraFichero.query.filter_by(mes=ultimo.mes, anio=ultimo.anio - 1).first()
        if prev_year and prev_year.num_polizas:
            variacion_anual = round((ultimo.num_polizas - prev_year.num_polizas) / prev_year.num_polizas * 100, 1)

    # Chart data
    chart_labels = []
    chart_polizas = []
    chart_prima = []
    for f in reversed(ficheros):
        chart_labels.append(f'{MESES[f.mes][:3]} {f.anio}')
        chart_polizas.append(f.num_polizas or 0)
        chart_prima.append(f.prima_neta_total or 0)

    return render_template('cartera/index.html', ficheros=ficheros, meses=MESES,
                           ultimo=ultimo, variacion_mensual=variacion_mensual,
                           variacion_anual=variacion_anual,
                           labels=chart_labels, polizas=chart_polizas, prima=chart_prima)


@cartera_bp.route('/subir', methods=['POST'])
@login_required
def subir():
    file = request.files.get('archivo')
    mes = request.form.get('mes', type=int)
    anio = request.form.get('anio', type=int)
    reemplazar = request.form.get('reemplazar') == '1'

    if not file or not mes or not anio:
        flash('Archivo, mes y ano requeridos', 'danger')
        return redirect(url_for('cartera.index'))

    # Check if already exists
    existente = CarteraFichero.query.filter_by(mes=mes, anio=anio).first()
    if existente and not reemplazar:
        flash(f'Ya existe cartera para {MESES[mes]} {anio}. Marca "Reemplazar" para sobrescribir.', 'warning')
        return redirect(url_for('cartera.index'))

    os.makedirs(CARTERA_DIR, exist_ok=True)
    filename = f'{anio}-{mes:02d}.xlsx'
    filepath = os.path.join(CARTERA_DIR, filename)
    file.save(filepath)

    # Parse
    resultado = parse_cartera_xlsx(filepath)
    if 'error' in resultado:
        flash(f'Error al procesar: {resultado["error"]}', 'danger')
        return redirect(url_for('cartera.index'))

    # Delete old if replacing
    if existente:
        db.session.delete(existente)
        db.session.flush()

    fichero = CarteraFichero(
        mes=mes, anio=anio, nombre_fichero=filename, ruta=filepath,
        hash_md5=resultado['hash_md5'], num_filas=len(resultado['rows']),
        num_polizas=resultado['num_polizas'], prima_neta_total=resultado['prima_neta_total'],
        user_id=current_user.id
    )
    db.session.add(fichero)
    db.session.flush()

    # Save policies
    for p in resultado['rows']:
        db.session.add(CarteraPoliza(fichero_id=fichero.id, **p))

    db.session.commit()

    # Run analysis
    stats = run_analysis(fichero)

    flash(f'{MESES[mes]} {anio}: {resultado["num_polizas"]} polizas, '
          f'{round(resultado["prima_neta_total"], 0)}€ prima. '
          f'{stats["altas"]} altas, {stats["bajas"]} bajas '
          f'({stats["bajas_renumeradas"]} renumeradas, {stats["bajas_sospechosas"]} sospechosas)',
          'success')
    return redirect(url_for('cartera.index'))


@cartera_bp.route('/detalle/<int:id>')
@login_required
def detalle_mes(id):
    fichero = CarteraFichero.query.get_or_404(id)
    altas = CarteraAlta.query.filter_by(mes_hasta=fichero.mes, anio_hasta=fichero.anio).all()
    bajas = CarteraBaja.query.filter_by(mes_hasta=fichero.mes, anio_hasta=fichero.anio).all()
    bajas_renumeradas = [b for b in bajas if b.renumerada]
    bajas_sospechosas = [b for b in bajas if not b.renumerada]
    polizas = fichero.polizas.all()
    # Group by producto
    by_producto = {}
    for p in polizas:
        prod = p.producto or 'Sin producto'
        if prod not in by_producto:
            by_producto[prod] = {'count': 0, 'prima': 0}
        by_producto[prod]['count'] += 1
        by_producto[prod]['prima'] += p.prima_neta

    return render_template('cartera/detalle_mes.html', fichero=fichero, meses=MESES,
                           altas=altas, bajas=bajas, bajas_renumeradas=bajas_renumeradas,
                           bajas_sospechosas=bajas_sospechosas, by_producto=by_producto)


@cartera_bp.route('/bajas-sospechosas')
@login_required
def bajas_sospechosas():
    mes = request.args.get('mes', type=int)
    anio = request.args.get('anio', type=int)
    producto = request.args.get('producto', '')

    query = CarteraBaja.query.filter_by(renumerada=False)
    if mes:
        query = query.filter_by(mes_hasta=mes)
    if anio:
        query = query.filter_by(anio_hasta=anio)
    if producto:
        query = query.filter(CarteraBaja.producto.ilike(f'%{producto}%'))

    bajas = query.order_by(CarteraBaja.prima_neta.desc()).limit(500).all()

    return render_template('cartera/bajas_sospechosas.html', bajas=bajas, meses=MESES,
                           mes=mes, anio=anio, producto=producto)


@cartera_bp.route('/comparativa-anual')
@login_required
def comparativa_anual():
    fichas = CarteraFichero.query.order_by(CarteraFichero.anio, CarteraFichero.mes).all()
    by_year_month = {}
    for f in fichas:
        key = (f.anio, f.mes)
        by_year_month[key] = f

    years = sorted(set(f.anio for f in fichas))
    months_avail = sorted(set(f.mes for f in fichas))

    comp_data = []
    for m in months_avail:
        row = {'mes': m, 'mes_nombre': MESES[m]}
        for y in years:
            f = by_year_month.get((y, m))
            row[y] = f.num_polizas if f else None
            row[f'{y}_prima'] = f.prima_neta_total if f else None
        # Calculate diff between last two years
        if len(years) >= 2:
            y1, y2 = years[-1], years[-2]
            v1 = row.get(y1)
            v2 = row.get(y2)
            if v1 and v2:
                row['diff'] = round((v1 - v2) / v2 * 100, 1) if v2 else 0
            else:
                row['diff'] = None
        comp_data.append(row)

    return render_template('cartera/comparativa_anual.html', comp_data=comp_data,
                           years=years, meses=MESES)


@cartera_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar(id):
    fichero = CarteraFichero.query.get_or_404(id)
    try:
        os.remove(fichero.ruta)
    except Exception:
        pass
    db.session.delete(fichero)
    db.session.commit()
    flash('Registro eliminado', 'success')
    return redirect(url_for('cartera.index'))
