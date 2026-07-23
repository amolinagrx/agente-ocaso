import os
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from models import db, Configuracion, DocumentoConocimiento, ChunkConocimiento, MensajeAsistente
from datetime import datetime

ajustes_bp = Blueprint('ajustes', __name__)


@ajustes_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        seccion = request.form.get('seccion', '')

        if seccion == 'general':
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

        return redirect(url_for('ajustes.index'))

    # Load current config
    config = {}
    for c in Configuracion.query.all():
        config[c.clave] = c.valor

    # AI stats
    docs_count = DocumentoConocimiento.query.count()
    chunks_count = ChunkConocimiento.query.count()
    mensajes_count = MensajeAsistente.query.count()
    key_from_env = bool(os.environ.get('DEEPSEEK_API_KEY', ''))
    key_from_db = bool(config.get('deepseek_api_key', ''))
    api_key_configured = key_from_env or key_from_db

    return render_template('ajustes/index.html',
                           config=config,
                           docs_count=docs_count,
                           chunks_count=chunks_count,
                           mensajes_count=mensajes_count,
                           api_key_configured=api_key_configured,
                           key_from_env=key_from_env,
                           key_from_db=key_from_db)


def _guardar_config(clave, valor):
    conf = Configuracion.query.filter_by(clave=clave).first()
    if conf:
        conf.valor = valor.strip() if valor else ''
    else:
        if valor:
            db.session.add(Configuracion(clave=clave, valor=valor.strip()))


@ajustes_bp.route('/exportar-backup')
@login_required
def exportar_backup():
    """Download the SQLite database as backup."""
    import shutil
    import tempfile
    from flask import send_file, current_app

    db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    if not os.path.exists(db_path):
        flash('No se encuentra la base de datos', 'danger')
        return redirect(url_for('ajustes.index'))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    shutil.copy2(db_path, tmp.name)
    tmp.close()

    from datetime import date
    filename = f'ocaso_backup_{date.today().strftime("%Y%m%d")}.db'

    return send_file(tmp.name, as_attachment=True, download_name=filename,
                     mimetype='application/octet-stream')


@ajustes_bp.route('/importar-backup', methods=['POST'])
@login_required
def importar_backup():
    """Restore database from uploaded backup file."""
    from flask import current_app
    import shutil

    file = request.files.get('backup_file')
    if not file or not file.filename.endswith('.db'):
        flash('Selecciona un archivo .db valido', 'danger')
        return redirect(url_for('ajustes.index'))

    db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    backup_path = db_path + '.backup_previo'

    # Backup current DB just in case
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_path)

    try:
        file.save(db_path)
        flash('Backup restaurado correctamente. La aplicacion se reiniciara al recargar.', 'success')
    except Exception as e:
        # Restore previous DB if import fails
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, db_path)
        flash(f'Error al restaurar: {e}', 'danger')

    return redirect(url_for('ajustes.index'))


@ajustes_bp.route('/reset-all', methods=['POST'])
@login_required
def reset_all():
    """Delete all data after confirming security code."""
    codigo = request.form.get('codigo_seguridad', '')
    confirmacion = request.form.get('confirmacion', '')

    if codigo != 'rudtb8vx':
        flash('Codigo de seguridad incorrecto', 'danger')
        return redirect(url_for('ajustes.index'))

    if confirmacion != 'BORRAR TODO':
        flash('Debes escribir "BORRAR TODO" para confirmar', 'danger')
        return redirect(url_for('ajustes.index'))

    try:
        # Drop all tables and recreate
        db.drop_all()
        db.create_all()

        # Re-seed user
        from models import User
        db.session.add(User(username='admin', password='ocaso2025'))
        db.session.commit()

        flash('Todos los datos han sido eliminados. La aplicacion esta limpia.', 'success')
    except Exception as e:
        flash(f'Error al resetear: {e}', 'danger')

    return redirect(url_for('ajustes.index'))
