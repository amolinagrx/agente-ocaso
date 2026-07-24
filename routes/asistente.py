import os
import json
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, flash
from flask_login import login_required
from models import db, DocumentoConocimiento, ChunkConocimiento, MensajeAsistente
from utils.ai import (
    extract_text_from_file, chunk_text, generate_embedding,
    search_relevant_chunks, get_platform_context, chat_with_context,
    summarize_document, build_system_prompt
)
from datetime import datetime

asistente_bp = Blueprint('asistente', __name__)


@asistente_bp.route('/')
@login_required
def index():
    documentos = DocumentoConocimiento.query.order_by(
        DocumentoConocimiento.created_at.desc()
    ).all()
    mensajes = MensajeAsistente.query.order_by(
        MensajeAsistente.created_at.asc()
    ).limit(100).all()
    return render_template('asistente/index.html',
                           documentos=documentos,
                           mensajes=mensajes)


@asistente_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    pregunta = request.form.get('mensaje', '').strip()
    if not pregunta:
        return jsonify({'respuesta': '', 'error': 'Mensaje vacio'})

    # Save user message
    user_msg = MensajeAsistente(rol='user', contenido=pregunta)
    db.session.add(user_msg)
    db.session.commit()

    # Search relevant knowledge chunks
    chunks = ChunkConocimiento.query.all()
    relevant = search_relevant_chunks(pregunta, chunks, top_k=6) if chunks else []

    # Get platform context
    platform_ctx = get_platform_context(pregunta)

    # Build message history (last 20 messages for context)
    historico = MensajeAsistente.query.order_by(
        MensajeAsistente.created_at.asc()
    ).limit(30).all()

    api_messages = []
    for m in historico:
        role = m.rol
        if role == 'system':
            continue
        api_messages.append({'role': role, 'content': m.contenido})

    # Get response from Deepseek
    respuesta = chat_with_context(api_messages, relevant, platform_ctx)

    # Save assistant message
    ctx_summary = ''
    if relevant:
        ctx_summary = f'Fuentes: {", ".join(set(c.documento.nombre for c in relevant[:5]))}'
    if platform_ctx:
        ctx_summary += '\n[Usados datos de plataforma]'

    assistant_msg = MensajeAsistente(
        rol='assistant',
        contenido=respuesta,
        contexto_usado=ctx_summary
    )
    db.session.add(assistant_msg)
    db.session.commit()

    return jsonify({
        'respuesta': respuesta,
        'contexto': ctx_summary
    })


@asistente_bp.route('/subir-documento', methods=['POST'])
@login_required
def subir_documento():
    files = request.files.getlist('documento')
    if not files or (len(files) == 1 and not files[0].filename):
        flash('No se selecciono ningun archivo', 'danger')
        return redirect(url_for('asistente.index'))

    upload_dir = current_app.config['UPLOAD_FOLDER']
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_CHUNKS = 200
    procesados = 0
    errores = 0

    for file in files:
        if not file or not file.filename:
            continue

        filename = file.filename

        # Check file size
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > MAX_SIZE:
            flash(f'{filename}: supera los 10MB, no se procesa.', 'warning')
            errores += 1
            continue

        # Check extension
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ('pdf', 'md', 'txt'):
            flash(f'{filename}: formato no soportado.', 'warning')
            errores += 1
            continue

        try:
            filepath = os.path.join(upload_dir, f'doc_{datetime.utcnow().strftime("%Y%m%d%H%M%S")}_{filename}')
            file.save(filepath)

            texto = extract_text_from_file(filepath, filename)
            if not texto or texto.startswith('ERROR'):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
                errores += 1
                continue

            doc = DocumentoConocimiento(
                nombre=filename,
                tipo=ext,
                contenido_raw=texto[:50000]
            )
            db.session.add(doc)
            db.session.flush()

            chunks = chunk_text(texto, chunk_size=600, overlap=50)
            batch = 0
            for i, chunk_text_content in enumerate(chunks[:MAX_CHUNKS]):
                db.session.add(ChunkConocimiento(
                    documento_id=doc.id,
                    texto=chunk_text_content,
                    embedding=None,
                    indice=i
                ))
                batch += 1
                if batch >= 50:
                    db.session.commit()
                    batch = 0

            if batch > 0:
                db.session.commit()

            doc.num_chunks = min(len(chunks), MAX_CHUNKS)
            db.session.commit()
            procesados += 1

        except Exception as e:
            db.session.rollback()
            try:
                os.remove(filepath)
            except Exception:
                pass
            flash(f'Error procesando {filename}', 'danger')
            errores += 1

    if procesados > 0:
        flash(f'{procesados} documento(s) procesado(s).', 'success')
    if errores > 0:
        flash(f'{errores} archivo(s) con error.', 'warning')

    return redirect(url_for('asistente.index'))


@asistente_bp.route('/documento/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_documento(id):
    doc = DocumentoConocimiento.query.get_or_404(id)
    db.session.delete(doc)
    db.session.commit()
    flash(f'Documento "{doc.nombre}" eliminado', 'success')
    return redirect(url_for('asistente.index'))


@asistente_bp.route('/limpiar-chat', methods=['POST'])
@login_required
def limpiar_chat():
    MensajeAsistente.query.delete()
    db.session.commit()
    flash('Chat limpiado', 'success')
    return redirect(url_for('asistente.index'))


@asistente_bp.route('/configuracion')
@login_required
def configuracion():
    key_configured = bool(os.environ.get('DEEPSEEK_API_KEY', ''))
    docs_count = DocumentoConocimiento.query.count()
    chunks_count = ChunkConocimiento.query.count()
    mensajes_count = MensajeAsistente.query.count()
    return render_template('asistente/configuracion.html',
                           key_configured=key_configured,
                           docs_count=docs_count,
                           chunks_count=chunks_count,
                           mensajes_count=mensajes_count)
