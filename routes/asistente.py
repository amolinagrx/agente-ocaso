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
    file = request.files.get('documento')
    if not file:
        flash('No se selecciono archivo', 'danger')
        return redirect(url_for('asistente.index'))

    filename = file.filename
    upload_dir = current_app.config['UPLOAD_FOLDER']
    filepath = os.path.join(upload_dir, f'doc_{datetime.utcnow().strftime("%Y%m%d%H%M%S")}_{filename}')
    file.save(filepath)

    # Extract text
    texto = extract_text_from_file(filepath, filename)
    if not texto or texto.startswith('ERROR'):
        os.remove(filepath)
        flash(f'Error al procesar el archivo: {texto}', 'danger')
        return redirect(url_for('asistente.index'))

    # Create document
    doc = DocumentoConocimiento(
        nombre=filename,
        tipo=filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'txt',
        contenido_raw=texto[:50000]
    )
    db.session.add(doc)
    db.session.flush()

    # Generate summary
    summary = summarize_document(texto[:6000])
    if summary:
        doc_summary = DocumentoConocimiento(
            nombre=f'[RESUMEN] {filename}',
            tipo='txt',
            contenido_raw=summary
        )
        db.session.add(doc_summary)
        db.session.flush()

        summary_chunk = ChunkConocimiento(
            documento_id=doc_summary.id,
            texto=summary,
            indice=0
        )
        db.session.add(summary_chunk)

    # Chunk and embed
    chunks = chunk_text(texto)
    chunk_count = 0
    for i, chunk_text_content in enumerate(chunks):
        embedding = generate_embedding(chunk_text_content)
        chunk_obj = ChunkConocimiento(
            documento_id=doc.id,
            texto=chunk_text_content,
            embedding=json.dumps(embedding) if embedding else None,
            indice=i
        )
        db.session.add(chunk_obj)
        chunk_count += 1

    doc.num_chunks = chunk_count
    db.session.commit()

    flash(f'Documento "{filename}" procesado: {chunk_count} fragmentos indexados', 'success')
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
