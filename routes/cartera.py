import os
from datetime import datetime, date
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from models import db, Cartera
from utils.ai import get_client, DEEPSEEK_CHAT_MODEL, extract_text_from_file

cartera_bp = Blueprint('cartera', __name__)

MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']


@cartera_bp.route('/')
@login_required
def index():
    registros = Cartera.query.order_by(Cartera.anio.desc(), Cartera.mes.desc()).all()

    # Build chart data for trends
    chart_labels = []
    chart_polizas = []
    chart_prima = []
    chart_asegurados = []
    for r in reversed(registros):
        chart_labels.append(f'{MESES[r.mes][:3]} {r.anio}')
        chart_polizas.append(r.num_polizas or 0)
        chart_prima.append(r.prima_total or 0)
        chart_asegurados.append(r.num_asegurados or 0)

    return render_template('cartera/index.html',
                           registros=registros, meses=MESES,
                           labels=chart_labels, polizas=chart_polizas,
                           prima=chart_prima, asegurados=chart_asegurados)


@cartera_bp.route('/subir', methods=['POST'])
@login_required
def subir():
    file = request.files.get('archivo')
    mes = request.form.get('mes', type=int)
    anio = request.form.get('anio', type=int)

    if not file or not mes or not anio:
        flash('Archivo, mes y año requeridos', 'danger')
        return redirect(url_for('cartera.index'))

    filename = file.filename
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'],
                            f'cartera_{anio}_{mes:02d}_{filename}')
    file.save(filepath)

    texto = extract_text_from_file(filepath, filename)
    if texto and texto.startswith('ERROR'):
        os.remove(filepath)
        flash(f'Error al leer archivo: {texto}', 'danger')
        return redirect(url_for('cartera.index'))

    if not texto or len(texto.strip()) < 50:
        os.remove(filepath)
        flash('No se pudo extraer texto del archivo. Asegurate de que es un PDF o XLSX valido.', 'danger')
        return redirect(url_for('cartera.index'))

    # Delete previous entry for same month/year
    Cartera.query.filter_by(mes=mes, anio=anio).delete()

    cartera = Cartera(
        mes=mes, anio=anio, nombre_archivo=filename,
        ruta_archivo=filepath, user_id=current_user.id,
        contenido_texto=texto or ''
    )
    db.session.add(cartera)
    db.session.commit()

    flash(f'Cartera {MESES[mes]} {anio} cargada correctamente', 'success')
    return redirect(url_for('cartera.index'))


@cartera_bp.route('/analizar/<int:id>', methods=['POST'])
@login_required
def analizar(id):
    cartera = Cartera.query.get_or_404(id)

    client = get_client()
    if not client:
        flash('API Deepseek no configurada', 'danger')
        return redirect(url_for('cartera.index'))

    # Get ALL previous months for yearly comparison
    todos = Cartera.query.order_by(Cartera.anio, Cartera.mes).all()

    mes_ant = cartera.mes - 1 if cartera.mes > 1 else 12
    anio_ant = cartera.anio if cartera.mes > 1 else cartera.anio - 1
    previa = Cartera.query.filter_by(mes=mes_ant, anio=anio_ant).first()

    prompt = """Eres un analista de seguros experto en control de cartera. Analiza los datos de la oficina Ocaso Armilla.

OBJETIVO DEL ANALISIS:
1. EVOLUCION MENSUAL: Compara este mes con el mes anterior. ¿Ha subido o bajado?
2. EVOLUCION ANUAL: Compara con el mismo mes del año anterior si hay datos. ¿Crece o decrece la cartera interanualmente?
3. POLIZAS PERDIDAS: Identifica que polizas o tipos de seguro han desaparecido respecto al periodo anterior.
4. NUEVAS POLIZAS: Detecta nuevas altas que no estaban en el periodo anterior.
5. ASEGURADOS: ¿Cuantos asegurados hay ahora vs antes? ¿Cuantos se han perdido?
6. TENDENCIA: ¿La cartera esta en crecimiento, estable o en declive? Proyecta a 3-6 meses.

FORMATO DE RESPUESTA:
Usa este formato EXACTO con secciones claras:

**RESUMEN:** (2 lineas con los datos clave: polizas totales, asegurados, prima total)

**EVOLUCION MENSUAL:**
- Polizas: X → Y (diferencia: +/-Z)
- Asegurados: X → Y (+/-Z)  
- Prima: X€ → Y€ (+/-Z€)

**EVOLUCION ANUAL (vs mismo mes año anterior):**
(Misma estructura si hay datos, si no indica 'Sin datos del año anterior')

**POLIZAS PERDIDAS** (si las hay)
- Lista de polizas/ramos que han desaparecido

**NUEVAS INCORPORACIONES**
- Lista de nuevas polizas/ramos detectados

**CONCLUSION Y RECOMENDACION:**
- Estado general de la cartera (CRECE / ESTABLE / DECRECE)
- Recomendacion practica para la oficina

Responde en español, se conciso y directo. Usa **negritas** para datos clave."""

    knowledge = f'--- {MESES[cartera.mes]} {cartera.anio} ---\n{cartera.contenido_texto[:8000]}'

    if previa and previa.contenido_texto:
        knowledge += f'\n\n--- MES ANTERIOR ({MESES[previa.mes]} {previa.anio}) ---\n{previa.contenido_texto[:4000]}'

    if todos:
        # Same month last year
        last_year = Cartera.query.filter_by(mes=cartera.mes, anio=cartera.anio - 1).first()
        if last_year and last_year.contenido_texto:
            knowledge += f'\n\n--- MISMO MES AÑO ANTERIOR ({MESES[last_year.mes]} {last_year.anio}) ---\n{last_year.contenido_texto[:4000]}'

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_CHAT_MODEL,
            messages=[
                {'role': 'system', 'content': prompt},
                {'role': 'user', 'content': knowledge}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        analisis = resp.choices[0].message.content
        cartera.analisis_ia = analisis
        db.session.commit()
        flash(f'Analisis completado para {MESES[cartera.mes]} {cartera.anio}', 'success')
    except Exception as e:
        flash(f'Error: {str(e)[:200]}', 'danger')

    return redirect(url_for('cartera.index'))


@cartera_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar(id):
    cartera = Cartera.query.get_or_404(id)
    try:
        os.remove(cartera.ruta_archivo)
    except Exception:
        pass
    db.session.delete(cartera)
    db.session.commit()
    flash('Registro de cartera eliminado', 'success')
    return redirect(url_for('cartera.index'))

@cartera_bp.route('/analizar-todo', methods=['POST'])
@login_required
def analizar_todo():
    client = get_client()
    if not client:
        flash('API Deepseek no configurada', 'danger')
        return redirect(url_for('cartera.index'))
    reanalizar = request.form.get('reanalizar') == '1'
    query = Cartera.query
    if not reanalizar:
        query = query.filter((Cartera.analisis_ia == None) | (Cartera.analisis_ia == ''))
    pendientes = query.order_by(Cartera.anio, Cartera.mes).all()
    if not pendientes:
        flash('Todos los meses ya estan analizados', 'info')
        return redirect(url_for('cartera.index'))
    analizados = 0
    for c in pendientes:
        try:
            analisis = _generar_rapido(c)
            if analisis:
                c.analisis_ia = analisis
                analizados += 1
        except Exception:
            pass
    db.session.commit()
    flash(f'{analizados} meses analizados', 'success')
    return redirect(url_for('cartera.index'))


def _generar_rapido(cartera):
    client = get_client()
    if not client: return None
    previa = Cartera.query.filter_by(mes=cartera.mes-1 if cartera.mes>1 else 12, anio=cartera.anio if cartera.mes>1 else cartera.anio-1).first()
    prompt = "Analiza evolucion cartera seguros. 1.Compara mes anterior 2.Compara mismo mes año anterior 3.Polizas perdidas/nuevas 4.Tendencia. Espanol, conciso, formato: RESUMEN, EVOLUCION, PERDIDAS, NUEVAS, CONCLUSION."
    knowledge = f'--- {MESES[cartera.mes]} {cartera.anio} ---\n{cartera.contenido_texto[:8000]}'
    if previa and previa.contenido_texto: knowledge += f'\n\n--- MES ANTERIOR ---\n{previa.contenido_texto[:3000]}'
    ly = Cartera.query.filter_by(mes=cartera.mes, anio=cartera.anio-1).first()
    if ly and ly.contenido_texto: knowledge += f'\n\n--- AÑO ANTERIOR ---\n{ly.contenido_texto[:3000]}'
    resp = client.chat.completions.create(model=DEEPSEEK_CHAT_MODEL, messages=[{'role':'system','content':prompt},{'role':'user','content':knowledge}], temperature=0.2, max_tokens=2000)
    return resp.choices[0].message.content


@cartera_bp.route('/informe')
@login_required
def informe():
    registros = Cartera.query.order_by(Cartera.anio, Cartera.mes).all()
    return render_template('cartera/informe.html', registros=registros, meses=MESES,
        labels=[f'{MESES[r.mes][:3]} {r.anio}' for r in registros],
        polizas_data=[r.num_polizas or 0 for r in registros],
        prima_data=[r.prima_total or 0 for r in registros],
        asegurados_data=[r.num_asegurados or 0 for r in registros])


@cartera_bp.route('/informe/pdf')
@login_required
def informe_pdf():
    from utils.pdf import generar_pdf_informe_cartera
    registros = Cartera.query.order_by(Cartera.anio, Cartera.mes).all()
    return generar_pdf_informe_cartera(registros, MESES)


@cartera_bp.route('/analisis-anual')
@login_required
def analisis_anual():
    """Year-over-year comparison and analysis."""
    client = get_client()
    if not client:
        flash('API Deepseek no configurada', 'danger')
        return redirect(url_for('cartera.index'))

    registros = Cartera.query.order_by(Cartera.anio, Cartera.mes).all()
    if len(registros) < 2:
        flash('Necesitas al menos 2 meses de datos', 'warning')
        return redirect(url_for('cartera.index'))

    # Group by year
    years = {}
    for r in registros:
        y = r.anio
        if y not in years:
            years[y] = {'polizas': 0, 'asegurados': 0, 'prima': 0, 'meses': [], 'textos': []}
        years[y]['polizas'] = max(years[y]['polizas'], r.num_polizas or 0)
        years[y]['asegurados'] = max(years[y]['asegurados'], r.num_asegurados or 0)
        years[y]['prima'] = max(years[y]['prima'], r.prima_total or 0)
        years[y]['meses'].append(r.mes)
        years[y]['textos'].append(r.contenido_texto or '')

    sorted_years = sorted(years.keys())

    # Build prompt with yearly data
    prompt = "Eres analista de seguros. Haz un ANALISIS ANUAL de la cartera de Ocaso Armilla.\n\n"
    prompt += "Para cada año, indica: polizas, asegurados, prima.\n"
    prompt += "Luego compara año contra año: ¿crece o decrece? ¿que cambio porcentual?\n"
    prompt += "Identifica TENDENCIAS a largo plazo.\n"
    prompt += "Formato: **AÑO XXXX**, **COMPARATIVA**, **TENDENCIA**, **RECOMENDACION**. Espanol, conciso."

    knowledge = "DATOS ANUALES:\n"
    for y in sorted_years:
        d = years[y]
        knowledge += f"\n**{y}**: {len(d['meses'])} meses. Max polizas: {d['polizas']}, Max asegurados: {d['asegurados']}, Max prima: {d['prima']:.0f}€\n"
        knowledge += '---\n' + '\n'.join(d['textos'][:3])[:2000] + '\n'

    resp = client.chat.completions.create(
        model=DEEPSEEK_CHAT_MODEL,
        messages=[{'role': 'system', 'content': prompt}, {'role': 'user', 'content': knowledge[:12000]}],
        temperature=0.2, max_tokens=2500
    )
    analisis = resp.choices[0].message.content

    return render_template('cartera/analisis_anual.html',
                           years=sorted_years, data=years, analisis=analisis)
