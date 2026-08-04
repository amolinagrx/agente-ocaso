import os
from datetime import datetime, date
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify, make_response
from flask_login import login_required, current_user
from models import db, CarteraFichero, CarteraPoliza, CarteraBaja, CarteraAlta
from cartera.parser import parse_cartera_xlsx
from cartera.analysis import run_analysis
from utils.ai import get_client, DEEPSEEK_CHAT_MODEL

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


# ========== PDF generation helper ==========

def _generar_pdf(html, filename):
    try:
        from weasyprint import HTML
        import os as _os
        data_dir = current_app.config.get('UPLOAD_FOLDER', '/data/uploads')
        tmp_path = _os.path.join(data_dir, f'_pdf_{filename}')
        HTML(string=html).write_pdf(tmp_path)
        with open(tmp_path, 'rb') as f:
            pdf = f.read()
        _os.remove(tmp_path)
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename={filename}'
        return response
    except ImportError:
        flash('WeasyPrint no instalado', 'danger')
        return redirect(url_for('cartera.index'))
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Error PDF: {str(e)[:150]}', 'danger')
        return redirect(url_for('cartera.index'))


# ========== PDF routes ==========

@cartera_bp.route('/bajas-sospechosas/pdf')
@login_required
def bajas_pdf():
    mes = request.args.get('mes', type=int)
    anio = request.args.get('anio', type=int)
    producto = request.args.get('producto', '')

    query = CarteraBaja.query.filter_by(renumerada=False)
    if mes: query = query.filter_by(mes_hasta=mes)
    if anio: query = query.filter_by(anio_hasta=anio)
    if producto: query = query.filter(CarteraBaja.producto.ilike(f'%{producto}%'))
    bajas = query.order_by(CarteraBaja.prima_neta.desc()).all()

    # Build filter description
    filtros = []
    if mes: filtros.append(MESES[mes])
    if anio: filtros.append(str(anio))
    if producto: filtros.append(producto)
    filtro_titulo = ' - '.join(filtros) if filtros else 'Todos'

    rows = ''
    for b in bajas:
        rows += f'<tr><td>{b.poliza_base}</td><td>{b.producto}</td><td>{b.tipo_recibo}</td><td>{b.prima_neta:.0f}€</td><td>{MESES[b.mes_hasta]} {b.anio_hasta}</td></tr>'

    html = f'''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><style>
        @page {{ margin: 1.5cm; size: A4 landscape; }}
        body {{ font-family: Arial, sans-serif; font-size: 10px; }}
        .header {{ text-align:center; border-bottom:2px solid #003396; padding-bottom:8px; margin-bottom:12px; }}
        .header h2 {{ color:#003396; margin:0; font-size:16px; }}
        table {{ width:100%; border-collapse:collapse; }}
        th {{ background:#003396; color:white; padding:4px; text-align:left; font-size:9px; }}
        td {{ padding:3px 4px; border-bottom:1px solid #ddd; }}
        tr {{ page-break-inside:avoid; }}
    </style></head><body>
    <div class="header"><h2>OCASO SEGUROS - Armilla</h2><p>Bajas Sospechosas (no renumeradas) | {filtro_titulo}</p></div>
    <table><tr><th>Poliza</th><th>Producto</th><th>Tipo</th><th>Prima</th><th>Desaparecio</th></tr>{rows}</table>
    </body></html>'''
    return _generar_pdf(html, f'bajas_{anio or "todo"}.pdf')


@cartera_bp.route('/comparativa-anual/pdf')
@login_required
def comparativa_anual_pdf():
    fichas = CarteraFichero.query.order_by(CarteraFichero.anio, CarteraFichero.mes).all()
    by_year_month = {}
    for f in fichas:
        by_year_month[(f.anio, f.mes)] = f
    years = sorted(set(f.anio for f in fichas))
    months_avail = sorted(set(f.mes for f in fichas))

    rows = ''
    for m in months_avail:
        row = ''
        for y in years:
            f = by_year_month.get((y, m))
            row += f'<td>{f.num_polizas if f else "-"}</td><td>{f.prima_neta_total:.0f}€</td>' if f else '<td>-</td><td>-</td>'
        diff = ''
        if len(years) >= 2:
            f1 = by_year_month.get((years[-1], m))
            f2 = by_year_month.get((years[-2], m))
            if f1 and f2 and f2.num_polizas:
                pct = round((f1.num_polizas - f2.num_polizas) / f2.num_polizas * 100, 1)
                color = '#27ae60' if pct >= 0 else '#e74c3c'
                diff = f'<td style="color:{color}">{pct:+.1f}%</td>'
        rows += f'<tr><td><b>{MESES[m]}</b></td>{row}{diff}</tr>'

    header_cols = ''.join(f'<th colspan="2">{y}</th>' for y in years)

    html = f'''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><style>
        @page {{ margin: 1.5cm; size: A4 landscape; }}
        body {{ font-family: Arial, sans-serif; font-size: 10px; }}
        .header {{ text-align:center; border-bottom:2px solid #003396; padding-bottom:8px; margin-bottom:12px; }}
        .header h2 {{ color:#003396; margin:0; font-size:16px; }}
        table {{ width:100%; border-collapse:collapse; }}
        th {{ background:#003396; color:white; padding:4px; text-align:left; font-size:9px; }}
        td {{ padding:3px 4px; border-bottom:1px solid #ddd; }}
        tr {{ page-break-inside:avoid; }}
    </style></head><body>
    <div class="header"><h2>OCASO SEGUROS - Armilla</h2><p>Comparativa Anual de Cartera</p></div>
    <table><tr><th>Mes</th>{header_cols}{'<th>% Dif.</th>' if len(years)>=2 else ''}</tr>{rows}</table>
    </body></html>'''
    return _generar_pdf(html, 'comparativa_anual.pdf')


# ========== Informe Ejecutivo ==========

@cartera_bp.route('/informe')
@login_required
def informe():
    fichas = CarteraFichero.query.order_by(CarteraFichero.anio, CarteraFichero.mes).all()

    if not fichas:
        flash('Sin datos para generar informe', 'warning')
        return redirect(url_for('cartera.index'))

    return render_template('cartera/informe.html', fichas=fichas, meses=MESES,
                           kpis=_calcular_kpis(fichas),
                           resumen=_generar_resumen_ia(fichas))


@cartera_bp.route('/informe/pdf')
@login_required
def informe_pdf():
    fichas = CarteraFichero.query.order_by(CarteraFichero.anio, CarteraFichero.mes).all()
    if not fichas:
        return redirect(url_for('cartera.index'))

    kpis = _calcular_kpis(fichas)
    resumen = _generar_resumen_ia(fichas)

    # Build monthly table
    tabla_rows = ''
    for f in fichas:
        tabla_rows += f'<tr><td>{MESES[f.mes]} {f.anio}</td><td>{f.num_polizas}</td><td>{f.prima_neta_total:.0f}€</td></tr>'

    bajas_total = CarteraBaja.query.filter_by(renumerada=False).count()
    total_meses = len(fichas)

    first = fichas[0]
    last = fichas[-1]
    periodo = f'{MESES[first.mes]} {first.anio} - {MESES[last.mes]} {last.anio}'

    html = f'''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><style>
        @page {{ margin: 2cm; size: A4; }}
        body {{ font-family: Arial, sans-serif; font-size: 11px; line-height:1.5; color:#333; }}
        .portada {{ text-align:center; padding:60px 0; page-break-after:always; }}
        .portada h1 {{ color:#003396; font-size:28px; margin-bottom:10px; }}
        .portada .kpi {{ display:inline-block; width:45%; margin:10px; padding:15px; border:2px solid #003396; border-radius:8px; }}
        .portada .kpi h3 {{ margin:0; font-size:24px; color:#003396; }}
        .header {{ text-align:center; border-bottom:2px solid #003396; padding-bottom:8px; margin-bottom:15px; }}
        .header h2 {{ color:#003396; margin:0; }}
        table {{ width:100%; border-collapse:collapse; margin:10px 0; }}
        th {{ background:#003396; color:white; padding:5px; text-align:left; }}
        td {{ padding:4px 5px; border-bottom:1px solid #ddd; }}
        tr {{ page-break-inside:avoid; }}
        h3 {{ color:#003396; border-bottom:1px solid #003396; padding-bottom:3px; margin-top:20px; }}
        .footer {{ margin-top:20px; text-align:center; font-size:8px; color:#999; border-top:1px solid #ddd; padding-top:10px; }}
    </style></head><body>
    <div class="portada">
        <h1>OCASO SEGUROS - Armilla</h1>
        <h2 style="color:#003396">Informe Ejecutivo de Cartera</h2>
        <p>Periodo: {periodo} | Generado: {date.today().strftime('%d/%m/%Y')}</p>
        <div class="kpi"><h3>{kpis['polizas_last']}</h3><small>Polizas ({MESES[last.mes]})</small></div>
        <div class="kpi"><h3>{kpis['prima_last']:.0f}€</h3><small>Prima ({MESES[last.mes]})</small></div>
        <div class="kpi"><h3>{total_meses}</h3><small>Meses analizados</small></div>
        <div class="kpi"><h3>{bajas_total}</h3><small>Bajas sin renumerar</small></div>
    </div>

    <h3>Resumen Ejecutivo</h3>
    <p>{resumen['summary']}</p>
    <p><strong>Variacion:</strong> Polizas: {kpis['var_polizas_anual']:+.1f}% | Prima: {kpis['var_prima_anual']:+.1f}%</p>

    <h3>Metodologia</h3>
    <p>Analisis realizado sobre ficheros Excel mensuales de Ocaso. Se normalizan numeros de poliza (sin ceros a la izquierda, base 7 digitos + certificado). Se excluyen comisiones de agente de zona. Las polizas que desaparecen y reaparecen con mismo producto y prima (&lt;0,02€ tolerancia) se consideran renumeradas, no bajas reales. Las bajas NO renumeradas son las que requieren atencion.</p>

    <h3>Evolucion Mensual</h3>
    <table><tr><th>Periodo</th><th>Polizas</th><th>Prima Neta</th></tr>{tabla_rows}</table>

    <h3>Conclusiones</h3>
    <p>{resumen['conclusion']}</p>

    <div class="footer">Informe generado por Ocaso Gestion - Oficina Armilla (Granada)</div>
    </body></html>'''
    return _generar_pdf(html, f'informe_cartera_{date.today().strftime("%Y%m%d")}.pdf')


# ========== Helper functions ==========

def _calcular_kpis(fichas):
    if not fichas: return {}
    last = fichas[-1]
    # Year over year comparison
    prev_year = CarteraFichero.query.filter_by(mes=last.mes, anio=last.anio - 1).first()
    var_polizas = 0
    var_prima = 0
    if prev_year and prev_year.num_polizas:
        var_polizas = round((last.num_polizas - prev_year.num_polizas) / prev_year.num_polizas * 100, 1)
    if prev_year and prev_year.prima_neta_total:
        var_prima = round((last.prima_neta_total - prev_year.prima_neta_total) / prev_year.prima_neta_total * 100, 1)
    return {
        'polizas_last': last.num_polizas,
        'prima_last': last.prima_neta_total,
        'var_polizas_anual': var_polizas,
        'var_prima_anual': var_prima,
    }


def _generar_resumen_ia(fichas):
    kpis = _calcular_kpis(fichas)
    bajas_total = CarteraBaja.query.filter_by(renumerada=False).count()
    last = fichas[-1]

    # Build data for AI
    data_text = f"Ultimo mes: {MESES[last.mes]} {last.anio}. Polizas: {last.num_polizas}. Prima: {last.prima_neta_total:.0f}€.\n"
    data_text += f"Variacion anual: polizas {kpis['var_polizas_anual']:+.1f}%, prima {kpis['var_prima_anual']:+.1f}%.\n"
    data_text += f"Total bajas no renumeradas acumuladas: {bajas_total}.\n"

    client = get_client()
    if not client:
        return {
            'summary': f'Cartera analizada con {len(fichas)} meses de datos. Ultimo mes: {last.num_polizas} polizas, {last.prima_neta_total:.0f}€. Variacion anual: {kpis["var_polizas_anual"]:+.1f}%. Se han detectado {bajas_total} bajas sin renumerar que requieren atencion.',
            'conclusion': f'Se recomienda revisar las {bajas_total} bajas no renumeradas y verificar con Ocaso si corresponden a polizas retiradas sin aviso.'
        }

    prompt = "Eres analista de seguros. Redacta en espanol, tono profesional.\n\n"
    prompt += "1. RESUMEN EJECUTIVO (1 parrafo): Describe el estado de la cartera con los datos proporcionados. Indica si crece o decrece.\n"
    prompt += "2. CONCLUSIONES (1 parrafo): Recomendacion practica sobre las bajas sin renumerar.\n"
    prompt += "Responde en JSON: {\"summary\": \"...\", \"conclusion\": \"...\"}"

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_CHAT_MODEL,
            messages=[{'role':'system','content':prompt}, {'role':'user','content':data_text}],
            temperature=0.3, max_tokens=500
        )
        import json, re
        text = resp.choices[0].message.content
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {'summary': text[:500], 'conclusion': text[500:1000] if len(text) > 500 else ''}
    except Exception:
        return {
            'summary': f'Analisis de {len(fichas)} meses. Ultimo: {last.num_polizas} polizas, {last.prima_neta_total:.0f}€. Variacion anual polizas: {kpis["var_polizas_anual"]:+.1f}%.',
            'conclusion': f'Revisar {bajas_total} bajas no renumeradas.'
        }
