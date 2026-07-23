from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models import db, TarifaCalculadora, Cliente
from utils.pdf import generar_pdf_presupuesto
import os, json

calculadora_bp = Blueprint('calculadora', __name__)

RAMOS = ['auto', 'hogar', 'vida', 'decesos', 'accidentes', 'comercio']


@calculadora_bp.route('/')
@login_required
def index():
    return render_template('calculadora/index.html')


@calculadora_bp.route('/formulario/<ramo>')
@login_required
def formulario(ramo):
    if ramo not in RAMOS:
        flash('Ramo no válido', 'danger')
        return redirect(url_for('calculadora.index'))
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    return render_template(f'calculadora/formulario.html', ramo=ramo, clientes=clientes)


@calculadora_bp.route('/calcular', methods=['POST'])
@login_required
def calcular():
    ramo = request.form.get('ramo')
    if ramo not in RAMOS:
        return jsonify({'error': 'Ramo no válido'}), 400

    tarifas = TarifaCalculadora.query.filter_by(ramo=ramo).all()
    if not tarifas:
        # Defaults if no tariffs
        return render_template('calculadora/resultado.html',
                               ramo=ramo,
                               prima_anual=0,
                               prima_mensual=0,
                               error='No hay tarifas configuradas para este ramo.')

    # Pick the best matching tariff
    prima = 0
    for t in tarifas:
        if t.prima_base > 0:
            prima = t.prima_base * t.factor
            break

    # Apply multipliers based on form data
    if ramo == 'auto':
        tipo_cobertura = request.form.get('tipo_cobertura')
        if tipo_cobertura == 'terceros':
            prima *= 0.6
        elif tipo_cobertura == 'terceros_ampliado':
            prima *= 0.8
        elif tipo_cobertura == 'todo_riesgo':
            prima *= 1.0
        capitales = float(request.form.get('capitales', 0) or 0)
        if capitales > 50000:
            prima *= 1.1

    elif ramo == 'hogar':
        continente = float(request.form.get('continente', 0) or 0)
        contenido = float(request.form.get('contenido', 0) or 0)
        prima = (continente * 0.0015 + contenido * 0.003) if (continente + contenido) > 0 else prima
        coberturas = request.form.getlist('coberturas')
        prima *= (1 + len(coberturas) * 0.05)

    prima_anual = round(prima, 2)
    prima_mensual = round(prima / 12, 2)

    return render_template('calculadora/resultado.html',
                           ramo=ramo,
                           prima_anual=prima_anual,
                           prima_mensual=prima_mensual,
                           datos_form=request.form)


@calculadora_bp.route('/presupuesto-pdf', methods=['POST'])
@login_required
def presupuesto_pdf():
    datos = {
        'ramo': request.form.get('ramo'),
        'cliente_nombre': request.form.get('cliente_nombre', ''),
        'cliente_dni': request.form.get('cliente_dni', ''),
        'prima_anual': request.form.get('prima_anual'),
        'prima_mensual': request.form.get('prima_mensual'),
        'tipo_cobertura': request.form.get('tipo_cobertura', ''),
        'marca': request.form.get('marca', ''),
        'modelo': request.form.get('modelo', ''),
        'capitales': request.form.get('capitales', ''),
    }
    return generar_pdf_presupuesto(datos)


# Simple config page for tariffs
@calculadora_bp.route('/configuracion')
@login_required
def configuracion():
    tarifas = TarifaCalculadora.query.order_by(TarifaCalculadora.ramo, TarifaCalculadora.tramo).all()
    return render_template('calculadora/configuracion.html', tarifas=tarifas, ramos=RAMOS)


@calculadora_bp.route('/configuracion/nueva', methods=['POST'])
@login_required
def nueva_tarifa():
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
    flash('Tarifa añadida', 'success')
    return redirect(url_for('calculadora.configuracion'))


@calculadora_bp.route('/configuracion/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_tarifa(id):
    tarifa = TarifaCalculadora.query.get_or_404(id)
    db.session.delete(tarifa)
    db.session.commit()
    flash('Tarifa eliminada', 'success')
    return redirect(url_for('calculadora.configuracion'))
