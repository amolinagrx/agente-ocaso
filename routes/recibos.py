from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models import db, Recibo, Cliente, Poliza
from datetime import datetime, date
import pandas as pd
import io

recibos_bp = Blueprint('recibos', __name__)


@recibos_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 20

    query = Recibo.query

    estado = request.args.get('estado')
    if estado:
        query = query.filter(Recibo.estado == estado)

    compania = request.args.get('compania')
    if compania:
        query = query.filter(Recibo.compania == compania)

    mes = request.args.get('mes')
    anio = request.args.get('anio')
    if mes and anio:
        try:
            m, y = int(mes), int(anio)
            query = query.filter(
                db.extract('month', Recibo.fecha_emision) == m,
                db.extract('year', Recibo.fecha_emision) == y
            )
        except ValueError:
            pass

    buscar = request.args.get('buscar')
    if buscar:
        query = query.join(Cliente).filter(
            db.or_(
                Cliente.nombre.ilike(f'%{buscar}%'),
                Cliente.dni.ilike(f'%{buscar}%'),
                Recibo.numero_poliza.ilike(f'%{buscar}%'),
                Recibo.concepto.ilike(f'%{buscar}%')
            )
        )

    sort = request.args.get('sort', 'fecha_emision')
    order = request.args.get('order', 'desc')
    sort_col = getattr(Recibo, sort, Recibo.fecha_emision)
    if order == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    recibos = pagination.items

    return render_template('recibos/index.html',
                           recibos=recibos,
                           pagination=pagination,
                           estado=estado,
                           compania=compania,
                           mes=mes,
                           anio=anio,
                           buscar=buscar,
                           sort=sort,
                           order=order)


@recibos_bp.route('/gestionar/<int:id>', methods=['POST'])
@login_required
def gestionar(id):
    recibo = Recibo.query.get_or_404(id)
    recibo.estado_gestion = request.form.get('estado_gestion')
    recibo.notas = request.form.get('notas')
    db.session.commit()
    flash('Recibo actualizado correctamente', 'success')
    return redirect(request.referrer or url_for('recibos.index'))


@recibos_bp.route('/cambiar-estado/<int:id>', methods=['POST'])
@login_required
def cambiar_estado(id):
    recibo = Recibo.query.get_or_404(id)
    nuevo_estado = request.form.get('estado')
    if nuevo_estado in ('cobrado', 'devuelto', 'pendiente'):
        recibo.estado = nuevo_estado
        if nuevo_estado == 'devuelto':
            _actualizar_alerta_cliente(recibo.cliente_id)
        db.session.commit()
        flash(f'Estado cambiado a {nuevo_estado}', 'success')
    return redirect(request.referrer or url_for('recibos.index'))


@recibos_bp.route('/importar', methods=['GET', 'POST'])
@login_required
def importar():
    if request.method == 'POST':
        file = request.files.get('archivo')
        if not file:
            flash('No se seleccionó archivo', 'danger')
            return redirect(url_for('recibos.importar'))

        try:
            if file.filename.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(file.read()), sep=None, engine='python')
            else:
                df = pd.read_excel(io.BytesIO(file.read()))

            mapeo = request.form.get('mapeo', 'auto')

            if mapeo == 'auto':
                column_map = _auto_map_columns(df.columns.tolist())
            else:
                column_map = {
                    'cliente_nombre': request.form.get('col_cliente', 'cliente'),
                    'dni': request.form.get('col_dni', 'dni'),
                    'poliza': request.form.get('col_poliza', 'poliza'),
                    'concepto': request.form.get('col_concepto', 'concepto'),
                    'importe': request.form.get('col_importe', 'importe'),
                    'fecha_emision': request.form.get('col_fecha', 'fecha'),
                    'estado': request.form.get('col_estado', 'estado'),
                }

            importados = 0
            for _, row in df.iterrows():
                nombre = str(row.get(column_map.get('cliente_nombre', 'cliente'), ''))
                dni = str(row.get(column_map.get('dni', 'dni'), ''))
                num_poliza = str(row.get(column_map.get('poliza', 'poliza'), ''))

                if not nombre or pd.isna(_safe_get(row, column_map.get('importe', 'importe'))):
                    continue

                cliente = Cliente.query.filter_by(dni=dni).first()
                if not cliente:
                    cliente = Cliente(nombre=nombre, dni=dni)
                    db.session.add(cliente)
                    db.session.flush()

                try:
                    importe_val = float(_safe_get(row, column_map.get('importe', 'importe')))
                except (ValueError, TypeError):
                    importe_val = 0

                fecha_val = _parse_date(_safe_get(row, column_map.get('fecha_emision', 'fecha')))
                estado_val = str(_safe_get(row, column_map.get('estado', 'estado'))).lower()
                if estado_val not in ('cobrado', 'devuelto', 'pendiente'):
                    estado_val = 'pendiente'

                recibo = Recibo(
                    cliente_id=cliente.id,
                    numero_poliza=num_poliza,
                    concepto=str(_safe_get(row, column_map.get('concepto', 'concepto'))),
                    importe=importe_val,
                    fecha_emision=fecha_val,
                    fecha_cargo=fecha_val,
                    estado=estado_val,
                    compania=_safe_get(row, 'compania') or 'Ocaso'
                )
                db.session.add(recibo)
                importados += 1

            db.session.commit()
            flash(f'{importados} recibos importados correctamente', 'success')
            return redirect(url_for('recibos.index'))

        except Exception:
            flash('Error al importar. Verifica el formato del archivo.', 'danger')

    return render_template('recibos/importar.html')


def _auto_map_columns(cols):
    mapping = {}
    for col in cols:
        cl = col.lower()
        if any(x in cl for x in ['nombre', 'cliente']):
            mapping['cliente_nombre'] = col
        elif 'dni' in cl or 'nif' in cl:
            mapping['dni'] = col
        elif 'poliza' in cl or 'póliza' in cl:
            mapping['poliza'] = col
        elif 'concepto' in cl or 'descrip' in cl:
            mapping['concepto'] = col
        elif 'importe' in cl or 'prima' in cl or 'total' in col:
            mapping['importe'] = col
        elif 'fecha' in cl:
            mapping['fecha_emision'] = col
        elif 'estado' in cl:
            mapping['estado'] = col
    return {k: v for k, v in mapping.items() if v}


def _safe_get(row, key):
    try:
        val = row[key]
        if pd.isna(val):
            return ''
        return val
    except (KeyError, TypeError):
        return ''


def _parse_date(val):
    if not val:
        return date.today()
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return date.today()


def _actualizar_alerta_cliente(cliente_id):
    from sqlalchemy import func
    count = Recibo.query.filter_by(cliente_id=cliente_id, estado='devuelto').count()
    cliente = Cliente.query.get(cliente_id)
    if cliente:
        cliente.alerta_devoluciones = count >= 2
        db.session.commit()
