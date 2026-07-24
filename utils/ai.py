"""
AI utilities for Ocaso assistant.
Handles Deepseek API integration, document processing, and RAG.
"""

import os
import json
import hashlib
import re
from datetime import date
from openai import OpenAI

DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
DEEPSEEK_CHAT_MODEL = 'deepseek-chat'

_client = None


def _get_api_key():
    """Get API key from env or DB config."""
    key = os.environ.get('DEEPSEEK_API_KEY', '')
    if key:
        return key
    try:
        from models import Configuracion
        conf = Configuracion.query.filter_by(clave='deepseek_api_key').first()
        if conf and conf.valor:
            return conf.valor
    except Exception:
        pass
    return ''


def get_client():
    global _client
    key = _get_api_key()
    if _client is None and key:
        _client = OpenAI(api_key=key, base_url=DEEPSEEK_BASE_URL)
    return _client


def extract_text_from_file(filepath, filename):
    """Extract text from PDF or MD file."""
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''

    if ext == 'md':
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

    elif ext == 'pdf':
        try:
            from pypdf import PdfReader
            reader = PdfReader(filepath)
            text = ''
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + '\n'
            return text.strip()
        except ImportError:
            return 'ERROR: pypdf not installed. Install with: pip install pypdf'
        except Exception as e:
            return f'ERROR reading PDF: {str(e)}'

    elif ext == 'txt':
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

    return f'Unsupported file type: {ext}'


def chunk_text(text, chunk_size=800, overlap=100):
    """Split text into overlapping chunks."""
    if not text:
        return []

    chunks = []
    start = 0
    text = text.strip()

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            # Try to break at a paragraph or sentence boundary
            for break_char in ['\n\n', '\n', '. ']:
                pos = text.rfind(break_char, start, end)
                if pos > start + chunk_size // 2:
                    end = pos + len(break_char)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk[:chunk_size + 200])

        start = end - overlap
        if start >= end:
            start = end

    return chunks


def generate_embedding(text):
    """Generate embedding vector for text using Deepseek API."""
    client = get_client()
    if not client:
        return None

    try:
        resp = client.embeddings.create(
            model='deepseek-chat',
            input=text[:8000]
        )
        return resp.data[0].embedding
    except Exception as e:
        print(f'Embedding error: {e}')
        return None


def cosine_similarity(v1, v2):
    if not v1 or not v2:
        return 0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = sum(a * a for a in v1) ** 0.5
    norm2 = sum(b * b for b in v2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0
    return dot / (norm1 * norm2)


def search_relevant_chunks(question, chunks, top_k=8):
    """Find most relevant chunks for a question using embeddings."""
    if not chunks:
        return []

    q_embedding = generate_embedding(question)
    if not q_embedding:
        # Fallback: keyword search
        return _keyword_search(question, chunks, top_k)

    scored = []
    for chunk in chunks:
        if chunk.embedding:
            try:
                chunk_embedding = json.loads(chunk.embedding)
                score = cosine_similarity(q_embedding, chunk_embedding)
                scored.append((score, chunk))
            except (json.JSONDecodeError, TypeError):
                pass

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


def _keyword_search(question, chunks, top_k=8):
    """Fallback keyword-based search."""
    keywords = set(question.lower().split())
    keywords.discard('de')
    keywords.discard('la')
    keywords.discard('el')
    keywords.discard('en')
    keywords.discard('un')
    keywords.discard('una')
    keywords.discard('que')
    keywords.discard('los')
    keywords.discard('las')
    keywords.discard('y')
    keywords.discard('o')
    keywords.discard('a')
    keywords.discard('es')
    keywords.discard('por')
    keywords.discard('para')
    keywords.discard('con')
    keywords.discard('del')

    scored = []
    for chunk in chunks:
        text_lower = chunk.texto.lower()
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


def get_platform_context(question):
    """Extract relevant platform data (clients, policies) from the question."""
    from models import db, Cliente, Poliza, Recibo, Siniestro

    info_parts = []

    # Check for client references: names, DNI patterns
    clientes = Cliente.query.all()
    mentioned_clients = []

    q_lower = question.lower()

    for c in clientes:
        if c.nombre.lower() in q_lower:
            mentioned_clients.append(c)
        elif c.dni and c.dni.lower() in q_lower:
            mentioned_clients.append(c)

    for cliente in mentioned_clients[:3]:  # Limit to 3 clients
        info_parts.append(f'--- Cliente: {cliente.nombre} ---')
        info_parts.append(f'DNI: {cliente.dni or "N/A"}')
        info_parts.append(f'Tel: {cliente.telefono or "N/A"}')
        info_parts.append(f'Alerta devoluciones: {"SI" if cliente.alerta_devoluciones else "NO"}')

        polizas_activas = cliente.polizas.filter(Poliza.activa == True).all()
        if polizas_activas:
            info_parts.append('Polizas activas:')
            for p in polizas_activas[:10]:
                info_parts.append(
                    f'  - {p.numero_poliza} | Ramo: {p.ramo} | '
                    f'Prima: {p.prima_anual:.0f}€/año | '
                    f'Vence: {p.fecha_vencimiento.strftime("%d/%m/%Y") if p.fecha_vencimiento else "?"}'
                )

        # Recent siniestros
        siniestros = cliente.siniestros.order_by(Siniestro.fecha_apertura.desc()).limit(3).all()
        if siniestros:
            info_parts.append('Ultimos siniestros:')
            for s in siniestros:
                info_parts.append(
                    f'  - Exp: {s.numero_expediente} | Tipo: {s.tipo} | '
                    f'Estado: {s.estado} | Fecha: {s.fecha_ocurrencia.strftime("%d/%m/%Y") if s.fecha_ocurrencia else "?"}'
                )

        # Recent recibos
        recibos = Recibo.query.filter_by(cliente_id=cliente.id).order_by(
            Recibo.fecha_emision.desc()
        ).limit(5).all()
        if recibos:
            info_parts.append('Ultimos recibos:')
            for r in recibos:
                estado = 'COBRADO' if r.estado == 'cobrado' else ('DEVUELTO' if r.estado == 'devuelto' else 'PENDIENTE')
                info_parts.append(
                    f'  - {r.fecha_emision.strftime("%d/%m/%Y") if r.fecha_emision else "?"} | '
                    f'{r.importe:.2f}€ | {estado} | {r.concepto or ""}'
                )

    # General stats
    if not mentioned_clients and any(kw in q_lower for kw in ['cuantos', 'total', 'resumen', 'estadisticas', 'numero']):
        total_clientes = Cliente.query.count()
        total_polizas = Poliza.query.filter(Poliza.activa == True).count()
        total_siniestros = Siniestro.query.filter(
            ~Siniestro.estado.in_(['cerrado', 'resuelto'])
        ).count()
        devoluciones = Recibo.query.filter(Recibo.estado == 'devuelto').count()

        info_parts.append('--- Datos generales de la plataforma ---')
        info_parts.append(f'Total clientes: {total_clientes}')
        info_parts.append(f'Polizas activas: {total_polizas}')
        info_parts.append(f'Siniestros abiertos: {total_siniestros}')
        info_parts.append(f'Recibos devueltos: {devoluciones}')

        primas_ramo = db.session.query(
            Poliza.ramo, db.func.sum(Poliza.prima_anual)
        ).filter(Poliza.activa == True).group_by(Poliza.ramo).all()
        if primas_ramo:
            info_parts.append('Primas por ramo:')
            for ramo, total in primas_ramo:
                info_parts.append(f'  - {ramo}: {total:.0f}€/año')

    return '\n'.join(info_parts) if info_parts else ''


def build_system_prompt():
    """Build the system prompt for the assistant."""
    return """Eres Asistente Ocaso, un agente de IA para uso interno de la oficina de seguros
Ocaso en Armilla (Granada). Ayudas al equipo con informacion sobre productos de seguros,
gestion de clientes, y resolucion de dudas operativas.

CAPACIDADES:
1. Respondes preguntas sobre productos de seguros basandote en la documentacion subida.
2. Puedes consultar datos reales de clientes, polizas, recibos y siniestros del sistema.
3. Ayudas a redactar comunicaciones, analizar datos y hacer recomendaciones.
4. Si no tienes suficiente informacion, lo indicas claramente.

REGLAS:
- Se conciso y directo. Esto es una herramienta de trabajo, no un chatbot de atencion al cliente.
- Cuando cites datos de un cliente, incluye la fuente (ej: "segun los datos del sistema...").
- Si la pregunta es sobre productos, cita la documentacion cuando sea posible.
- Para calculos de primas, usa la calculadora de la plataforma; tu solo orientas.
- NUNCA inventes datos. Si no sabes algo, dilo.
- NO compartas esta informacion con clientes externos. Es solo para uso interno.
- Responde en español, con tono profesional pero cercano."""


def chat_with_context(messages, knowledge_chunks=None, platform_context='', knowledge_text=''):
    """Send chat completion to Deepseek with RAG context."""
    client = get_client()
    if not client:
        return 'Error: Deepseek API key no configurada. Configura DEEPSEEK_API_KEY en las variables de entorno.'

    system_content = build_system_prompt()
    if knowledge_text:
        system_content += f'\n\nDocumentacion de productos:\n{knowledge_text[:8000]}'
    if platform_context:
        system_content += f'\n\nDatos de la plataforma relevantes para esta consulta:\n{platform_context[:4000]}'

    api_messages = [{'role': 'system', 'content': system_content}]
    api_messages.extend(messages)

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_CHAT_MODEL,
            messages=api_messages,
            temperature=0.3,
            max_tokens=2000
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f'Error al conectar con Deepseek: {str(e)}'


def summarize_document(text):
    """Generate a summary of a document using Deepseek."""
    client = get_client()
    if not client or not text:
        return text[:500] + '...' if len(text) > 500 else text

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_CHAT_MODEL,
            messages=[
                {'role': 'system', 'content': 'Genera un resumen conciso en 3-5 lineas del siguiente documento de productos de seguros. En español.'},
                {'role': 'user', 'content': text[:4000]}
            ],
            temperature=0.2,
            max_tokens=300
        )
        return resp.choices[0].message.content
    except Exception:
        return text[:500] + '...' if len(text) > 500 else text
