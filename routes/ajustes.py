import os
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from models import db, Configuracion, TarifaCalculadora, DocumentoConocimiento, ChunkConocimiento, MensajeAsistente
from datetime import datetime

ajustes_bp = Blueprint('ajustes', __name__)


@ajustes_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        seccion = request.form.get('seccion', '')

        if seccion == 'general':
            _guardar_config('objetivo_mensual', request.form.get('objetivo_mensual', '15000'))
            _guardar_config('oficina_nombre', request.form.get('oficina_nombre', ''))
            _guardar_config('oficina_direccion', request.form.get('oficina_direccion', ''))
            _guardar_config('oficina_telefono', request.form.get('oficina_telefono', ''))
            _guardar_config('oficina_email', request.form.get('oficina_email', ''))
            _guardar_config('whatsapp_empresa', request.form.get('whatsapp_empresa', ''))
            _guardar_config('dias_alerta_siniestro', request.form.get('dias_alerta_siniestro', '15'))
            db.session.commit()
            flash('Configuracion general guardada', 'success')

        elif seccion == 'api':
            api_key = request.form.get('deepseek_api_key', '').strip()
            if api_key:
                _guardar_config('deepseek_api_key', api_key)
                db.session.commit()
                flash('API Key de Deepseek guardada', 'success')
            else:
                flash('La API Key no puede estar vacia', 'warning')

        elif seccion == 'tarifa':
            tarifa = TarifaCalculadora(
                ramo=request.form.get('ramo'),
                tramo=request.form.get('tramo'),
                prima_min=float(request.form.get('prima_min', 0)),
                prima_max=float(request.form.get('prima_max', 0)),
                prima_base=float(request.form.get('prima_base', 0)),
                factor=float(request.form.get('factor', 1.0))
            )
            db.session.add(tarifa)
            db.session.commit()
            flash('Tarifa anadida', 'success')

        return redirect(url_for('ajustes.index'))

    # Load current config
    config = {}
    for c in Configuracion.query.all():
        config[c.clave] = c.valor

    # Load tariffs
    tarifas = TarifaCalculadora.query.order_by(TarifaCalculadora.ramo, TarifaCalculadora.tramo).all()

    # AI stats
    docs_count = DocumentoConocimiento.query.count()
    chunks_count = ChunkConocimiento.query.count()
    mensajes_count = MensajeAsistente.query.count()
    key_from_env = bool(os.environ.get('DEEPSEEK_API_KEY', ''))
    key_from_db = bool(config.get('deepseek_api_key', ''))
    api_key_configured = key_from_env or key_from_db

    return render_template('ajustes/index.html',
                           config=config,
                           tarifas=tarifas,
                           docs_count=docs_count,
                           chunks_count=chunks_count,
                           mensajes_count=mensajes_count,
                           api_key_configured=api_key_configured,
                           key_from_env=key_from_env,
                           key_from_db=key_from_db)


@ajustes_bp.route('/tarifa/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_tarifa(id):
    tarifa = TarifaCalculadora.query.get_or_404(id)
    db.session.delete(tarifa)
    db.session.commit()
    flash('Tarifa eliminada', 'success')
    return redirect(url_for('ajustes.index'))


def _guardar_config(clave, valor):
    conf = Configuracion.query.filter_by(clave=clave).first()
    if conf:
        conf.valor = valor.strip() if valor else ''
    else:
        if valor:
            db.session.add(Configuracion(clave=clave, valor=valor.strip()))
