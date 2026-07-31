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

    # Get previous month for comparison
    mes_ant = cartera.mes - 1 if cartera.mes > 1 else 12
    anio_ant = cartera.anio if cartera.mes > 1 else cartera.anio - 1
    previa = Cartera.query.filter_by(mes=mes_ant, anio=anio_ant).first()

    prompt = """Eres un analista de seguros. Analiza los datos de cartera de la oficina Ocaso en Armilla.

INSTRUCCIONES:
1. Extrae del texto: numero de polizas activas, numero de asegurados, prima total, polizas nuevas, polizas canceladas
2. Compara con el mes anterior si hay datos
3. Indica si la cartera CRECE, se MANTIENE o DISMINUYE
4. Identifica patrones: ¿que ramos crecen mas? ¿hay fugas en algun ramo?
5. Da recomendaciones practicas

Formato: usa negritas (**texto**) para datos clave. Se breve y directo."""

    knowledge = f'--- {MESES[cartera.mes]} {cartera.anio} ---\n{cartera.contenido_texto[:8000]}'

    if previa and previa.contenido_texto:
        knowledge += f'\n\n--- MES ANTERIOR ({MESES[previa.mes]} {previa.anio}) ---\n{previa.contenido_texto[:4000]}'
        prompt += '\n\nDATOS DEL MES ANTERIOR PARA COMPARAR incluidos arriba. Compara obligatoriamente.'

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
