from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models import db, Cliente, Poliza, Recibo, Siniestro, HitoSiniestro, HistorialContacto, DocumentoCliente
from datetime import datetime, date

clientes_bp = Blueprint('clientes', __name__)


@clientes_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    buscar = request.args.get('buscar', '')

    query = Cliente.query
    if buscar:
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(f'%{buscar}%'),
                Cliente.dni.ilike(f'%{buscar}%'),
                Cliente.telefono.ilike(f'%{buscar}%'),
                Cliente.email.ilike(f'%{buscar}%')
            )
        )

    pagination = query.order_by(Cliente.nombre).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('clientes/index.html',
                           clientes=pagination.items,
                           pagination=pagination,
                           buscar=buscar)


@clientes_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    if request.method == 'POST':
        cliente = Cliente(
            nombre=request.form.get('nombre'),
            dni=request.form.get('dni'),
            direccion=request.form.get('direccion'),
            codigo_postal=request.form.get('codigo_postal'),
            poblacion=request.form.get('poblacion'),
            provincia=request.form.get('provincia'),
            telefono=request.form.get('telefono'),
            email=request.form.get('email'),
            fecha_nacimiento=request.form.get('fecha_nacimiento') or None,
            notas=request.form.get('notas')
        )
        db.session.add(cliente)
        db.session.commit()
        flash('Cliente creado correctamente', 'success')
        return redirect(url_for('clientes.ficha', id=cliente.id))
    return render_template('clientes/nuevo.html')


@clientes_bp.route('/<int:id>')
@login_required
def ficha(id):
    cliente = Cliente.query.get_or_404(id)
    polizas = cliente.polizas_activas
    recibos = cliente.recibos.order_by(Recibo.fecha_emision.desc()).limit(50).all()
    siniestros = cliente.siniestros.order_by(Siniestro.fecha_apertura.desc()).all()
    contactos = cliente.contactos.limit(30).all()
    documentos = DocumentoCliente.query.filter_by(cliente_id=cliente.id).order_by(DocumentoCliente.uploaded_at.desc()).all()
    return render_template('clientes/ficha.html',
                           cliente=cliente,
                           polizas=polizas,
                           recibos=recibos,
                           siniestros=siniestros,
                           contactos=contactos,
                           documentos=documentos)


@clientes_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        cliente.nombre = request.form.get('nombre')
        cliente.dni = request.form.get('dni')
        cliente.direccion = request.form.get('direccion')
        cliente.codigo_postal = request.form.get('codigo_postal')
        cliente.poblacion = request.form.get('poblacion')
        cliente.provincia = request.form.get('provincia')
        cliente.telefono = request.form.get('telefono')
        cliente.email = request.form.get('email')
        fecha_nac = request.form.get('fecha_nacimiento')
        cliente.fecha_nacimiento = fecha_nac if fecha_nac else None
        cliente.notas = request.form.get('notas')
        db.session.commit()
        flash('Cliente actualizado', 'success')
        return redirect(url_for('clientes.ficha', id=id))
    return render_template('clientes/editar.html', cliente=cliente)


@clientes_bp.route('/<int:id>/poliza/nueva', methods=['GET', 'POST'])
@login_required
def nueva_poliza(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        poliza = Poliza(
            cliente_id=id,
            numero_poliza=request.form.get('numero_poliza'),
            ramo=request.form.get('ramo'),
            compania=request.form.get('compania', 'Ocaso'),
            descripcion=request.form.get('descripcion'),
            capital_asegurado=float(request.form.get('capital_asegurado', 0)),
            prima_anual=float(request.form.get('prima_anual', 0)),
            fecha_efecto=request.form.get('fecha_efecto'),
            fecha_vencimiento=request.form.get('fecha_vencimiento'),
            marca=request.form.get('marca'),
            modelo=request.form.get('modelo'),
            anio=request.form.get('anio', type=int),
            matricula=request.form.get('matricula'),
            tipo_cobertura=request.form.get('tipo_cobertura'),
            tipo_vivienda=request.form.get('tipo_vivienda'),
            metros=request.form.get('metros', type=int),
            continente=float(request.form.get('continente', 0) or 0),
            contenido=float(request.form.get('contenido', 0) or 0),
            numero_cuenta=request.form.get('numero_cuenta', ''),
            unidades=request.form.get('unidades', 1, type=int) or 1,
            detalles=request.form.get('detalles', '')
        )
        db.session.add(poliza)
        db.session.commit()
        flash('Póliza creada correctamente', 'success')
        return redirect(url_for('clientes.ficha', id=id))
    return render_template('clientes/poliza_nueva.html', cliente=cliente)


@clientes_bp.route('/<int:id>/contacto', methods=['POST'])
@login_required
def agregar_contacto(id):
    cliente = Cliente.query.get_or_404(id)
    contacto = HistorialContacto(
        cliente_id=id,
        tipo=request.form.get('tipo'),
        notas=request.form.get('notas'),
        fecha=datetime.utcnow()
    )
    db.session.add(contacto)
    db.session.commit()
    flash('Contacto registrado', 'success')
    return redirect(url_for('clientes.ficha', id=id))


@clientes_bp.route('/<int:id>/subir-documento', methods=['POST'])
@login_required
def subir_documento(id):
    cliente = Cliente.query.get_or_404(id)
    file = request.files.get('documento')
    if file:
        from flask import current_app
        import os
        filename = f"cliente_{id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
        ruta = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(ruta)
        doc = DocumentoCliente(
            cliente_id=id,
            nombre=file.filename,
            tipo=request.form.get('tipo', 'otro'),
            ruta=ruta
        )
        db.session.add(doc)
        db.session.commit()
        flash('Documento subido', 'success')
    return redirect(url_for('clientes.ficha', id=id))


@clientes_bp.route('/<int:id>/poliza/<int:poliza_id>/editar', methods=['POST'])
@login_required
def editar_poliza(id, poliza_id):
    poliza = Poliza.query.get_or_404(poliza_id)
    poliza.numero_poliza = request.form.get('numero_poliza', poliza.numero_poliza)
    poliza.ramo = request.form.get('ramo', poliza.ramo)
    poliza.compania = request.form.get('compania', poliza.compania)
    poliza.descripcion = request.form.get('descripcion', poliza.descripcion)
    poliza.capital_asegurado = float(request.form.get('capital_asegurado', poliza.capital_asegurado or 0))
    poliza.prima_anual = float(request.form.get('prima_anual', poliza.prima_anual or 0))
    poliza.fecha_efecto = _parse_date(request.form.get('fecha_efecto')) or poliza.fecha_efecto
    poliza.fecha_vencimiento = _parse_date(request.form.get('fecha_vencimiento')) or poliza.fecha_vencimiento
    poliza.numero_cuenta = request.form.get('numero_cuenta', poliza.numero_cuenta)
    poliza.unidades = request.form.get('unidades', 1, type=int) or 1
    poliza.detalles = request.form.get('detalles', poliza.detalles)
    poliza.activa = request.form.get('activa', 'true') == 'true'

    if poliza.ramo == 'auto':
        poliza.marca = request.form.get('marca', poliza.marca)
        poliza.modelo = request.form.get('modelo', poliza.modelo)
        poliza.anio = request.form.get('anio', type=int) or poliza.anio
        poliza.matricula = request.form.get('matricula', poliza.matricula)
        poliza.tipo_cobertura = request.form.get('tipo_cobertura', poliza.tipo_cobertura)
    elif poliza.ramo == 'hogar':
        poliza.tipo_vivienda = request.form.get('tipo_vivienda', poliza.tipo_vivienda)
        poliza.metros = request.form.get('metros', type=int) or poliza.metros
        poliza.continente = float(request.form.get('continente', 0) or 0)
        poliza.contenido = float(request.form.get('contenido', 0) or 0)

    db.session.commit()
    flash('Poliza actualizada', 'success')
    return redirect(url_for('clientes.ficha', id=id))


@clientes_bp.route('/<int:id>/poliza/<int:poliza_id>/baja', methods=['POST'])
@login_required
def dar_baja_poliza(id, poliza_id):
    poliza = Poliza.query.get_or_404(poliza_id)
    poliza.activa = False
    poliza.fecha_baja = date.today()
    db.session.commit()
    flash(f'Poliza {poliza.numero_poliza} dada de baja', 'warning')
    return redirect(url_for('clientes.ficha', id=id))


@clientes_bp.route('/<int:id>/recibo/nuevo', methods=['POST'])
@login_required
def nuevo_recibo(id):
    cliente = Cliente.query.get_or_404(id)
    recibo = Recibo(
        cliente_id=id,
        poliza_id=request.form.get('poliza_id', type=int) or None,
        numero_poliza=request.form.get('numero_poliza', ''),
        concepto=request.form.get('concepto', ''),
        importe=float(request.form.get('importe', 0)),
        fecha_emision=_parse_date(request.form.get('fecha_emision')) or date.today(),
        fecha_cargo=_parse_date(request.form.get('fecha_cargo')) or date.today(),
        estado=request.form.get('estado', 'pendiente'),
        compania=request.form.get('compania', 'Ocaso'),
        notas=request.form.get('notas', '')
    )
    db.session.add(recibo)
    db.session.commit()
    flash(f'Recibo de {recibo.importe:.2f}€ creado', 'success')
    return redirect(url_for('clientes.ficha', id=id))


@clientes_bp.route('/<int:id>/siniestro/nuevo', methods=['POST'])
@login_required
def nuevo_siniestro(id):
    cliente = Cliente.query.get_or_404(id)
    siniestro = Siniestro(
        cliente_id=id,
        poliza_id=request.form.get('poliza_id', type=int) or None,
        numero_expediente=request.form.get('numero_expediente', ''),
        tipo=request.form.get('tipo', ''),
        descripcion=request.form.get('descripcion', ''),
        fecha_ocurrencia=_parse_date(request.form.get('fecha_ocurrencia')) or date.today(),
        fecha_apertura=_parse_date(request.form.get('fecha_apertura')) or date.today(),
        estado='abierto',
        fecha_ultima_actualizacion=datetime.utcnow(),
        importe_estimado=float(request.form.get('importe_estimado', 0) or 0)
    )
    db.session.add(siniestro)
    db.session.flush()

    hito = HitoSiniestro(
        siniestro_id=siniestro.id,
        fecha=datetime.utcnow(),
        estado='abierto',
        notas=request.form.get('notas_iniciales', 'Apertura de siniestro desde ficha de cliente')
    )
    db.session.add(hito)
    db.session.commit()
    flash('Siniestro registrado correctamente', 'success')
    return redirect(url_for('clientes.ficha', id=id))


@clientes_bp.route('/<int:id>/polizas-json')
@login_required
def polizas_json(id):
    polizas = Poliza.query.filter_by(cliente_id=id).order_by(Poliza.activa.desc()).all()
    return jsonify([{
        'id': p.id,
        'numero_poliza': p.numero_poliza,
        'ramo': p.ramo,
        'prima_anual': p.prima_anual,
        'activa': p.activa
    } for p in polizas])


def _parse_date(val):
    """Parse a date string to a Python date object."""
    if not val or (isinstance(val, str) and not val.strip()):
        return None
    if isinstance(val, date):
        return val
    try:
        from datetime import datetime as dt
        return dt.strptime(str(val), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None
