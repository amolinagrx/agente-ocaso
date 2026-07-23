import io
from datetime import date
from flask import make_response

try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False


def generar_pdf_renovaciones(resultados):
    if not HAS_WEASYPRINT:
        return "WeasyPrint no instalado", 500

    hoy = date.today().strftime('%d/%m/%Y')
    rows = ''
    for r, p, c in resultados:
        dias = (r.fecha_vencimiento - date.today()).days if r.fecha_vencimiento else 0
        color = '#198754' if dias > 60 else '#ffc107' if dias > 30 else '#CC0000'
        rows += f'''
        <tr>
            <td>{c.nombre}</td>
            <td>{p.numero_poliza}</td>
            <td>{p.ramo.title()}</td>
            <td>{r.fecha_vencimiento.strftime('%d/%m/%Y')}</td>
            <td style="color:{color};font-weight:bold">{dias} días</td>
            <td>{r.prima:.2f}€</td>
            <td>{r.estado.replace('_', ' ').title()}</td>
        </tr>'''

    html_content = f'''
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; color: #333; }}
        .header {{ text-align: center; border-bottom: 3px solid #CC0000; padding-bottom: 10px; margin-bottom: 20px; }}
        .header h1 {{ color: #CC0000; margin: 0; font-size: 18px; }}
        .header p {{ margin: 5px 0; font-size: 12px; color: #666; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
        th {{ background: #CC0000; color: white; padding: 8px; text-align: left; }}
        td {{ padding: 6px 8px; border-bottom: 1px solid #ddd; }}
        .footer {{ margin-top: 20px; font-size: 10px; color: #999; text-align: center; }}
    </style></head>
    <body>
    <div class="header">
        <h1>OCASO SEGUROS - Oficina Armilla</h1>
        <p>Agenda de Renovaciones | Fecha: {hoy}</p>
    </div>
    <table>
        <thead><tr>
            <th>Cliente</th><th>Póliza</th><th>Ramo</th><th>Vencimiento</th><th>Días</th><th>Prima</th><th>Estado</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table>
    <div class="footer">Documento generado el {hoy} - Ocaso Seguros Armilla</div>
    </body></html>'''

    pdf = HTML(string=html_content).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=renovaciones_{hoy.replace("/", "_")}.pdf'
    return response


def generar_pdf_presupuesto(datos):
    if not HAS_WEASYPRINT:
        return "WeasyPrint no instalado", 500

    hoy = date.today()
    validez = hoy.replace(year=hoy.year + 1) if hoy.month == 1 else hoy.replace(month=hoy.month + 1)
    ramo_nombres = {
        'auto': 'Seguro de Automóvil', 'hogar': 'Seguro de Hogar',
        'vida': 'Seguro de Vida', 'decesos': 'Seguro de Decesos',
        'accidentes': 'Seguro de Accidentes', 'comercio': 'Seguro de Comercio'
    }

    coberturas_auto = {
        'terceros': 'Responsabilidad Civil (Terceros)',
        'terceros_ampliado': 'Terceros Ampliado',
        'todo_riesgo': 'Todo Riesgo'
    }

    ramo = datos.get('ramo', '')
    cobertura = coberturas_auto.get(datos.get('tipo_cobertura', ''), datos.get('tipo_cobertura', ''))

    html_content = f'''
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 30px; color: #333; }}
        .membrete {{ border: 3px solid #CC0000; padding: 20px; margin-bottom: 20px; }}
        .membrete h1 {{ color: #CC0000; margin: 0 0 10px 0; font-size: 22px; }}
        .membrete p {{ margin: 3px 0; font-size: 12px; }}
        .section {{ margin: 20px 0; }}
        .section h2 {{ color: #CC0000; font-size: 16px; border-bottom: 1px solid #CC0000; padding-bottom: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        td {{ padding: 6px 10px; border-bottom: 1px solid #eee; }}
        td.label {{ font-weight: bold; width: 40%; }}
        .total {{ background: #CC0000; color: white; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        .total td {{ border: none; color: white; }}
        .validez {{ font-size: 11px; color: #999; margin-top: 20px; }}
    </style></head>
    <body>
    <div class="membrete">
        <h1>OCASO SEGUROS</h1>
        <p>Oficina de Armilla</p>
        <p>C/ Real, 12 - 18100 Armilla (Granada)</p>
        <p>Tel: 958 123 456 | Email: armilla@ocaso.es</p>
        <p>NIF/CIF Agencia: B-12345678</p>
    </div>

    <div class="section">
        <h2>{ramo_nombres.get(ramo, ramo.title())}</h2>
        <table>
            <tr><td class="label">Cliente:</td><td>{datos.get('cliente_nombre', '')}</td></tr>
            <tr><td class="label">DNI/NIF:</td><td>{datos.get('cliente_dni', '')}</td></tr>
            <tr><td class="label">Tipo de seguro:</td><td>{ramo_nombres.get(ramo, ramo.title())}</td></tr>
            <tr><td class="label">Cobertura:</td><td>{cobertura}</td></tr>'''

    if datos.get('marca'):
        html_content += f'<tr><td class="label">Vehículo:</td><td>{datos.get("marca")} {datos.get("modelo", "")}</td></tr>'

    html_content += f'''
        </table>
    </div>

    <table class="total">
        <tr><td style="font-size:18px;font-weight:bold">PRIMA ANUAL</td>
            <td style="text-align:right;font-size:18px;font-weight:bold">{datos.get("prima_anual", "0")}€</td></tr>
        <tr><td>PRIMA MENSUAL ESTIMADA</td>
            <td style="text-align:right">{datos.get("prima_mensual", "0")}€/mes</td></tr>
    </table>

    <div class="validez">
        <p>Presupuesto válido hasta: {validez.strftime('%d/%m/%Y')}</p>
        <p>Este presupuesto es orientativo y está sujeto a la valoración final de la compañía aseguradora.</p>
        <p>Documento generado el {hoy.strftime('%d/%m/%Y')} por la Oficina Ocaso Armilla.</p>
    </div>
    </body></html>'''

    pdf = HTML(string=html_content).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=presupuesto_{hoy.strftime("%Y%m%d")}.pdf'
    return response
