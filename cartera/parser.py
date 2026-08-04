"""Excel parser for Ocaso portfolio files."""
import hashlib
from datetime import datetime
from cartera import normalizar_poliza


def parse_cartera_xlsx(filepath):
    """Parse an Ocaso portfolio XLSX file.

    Returns dict with: rows, polizas, prima_neta_total, hash_md5, errors
    """
    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath, data_only=True)
        ws = wb.active
    except Exception as e:
        return {'error': f'No se pudo abrir el archivo: {e}'}

    rows = list(ws.iter_rows(min_row=3, values_only=True))
    if not rows:
        return {'error': 'Archivo vacio o sin datos desde fila 3'}

    polizas_raw = []
    errors = []

    for i, row in enumerate(rows):
        try:
            # Column A=MES, D=POLIZA, E=PRODUCTO, H=TIPO_RECIBO, I=PRIMA_NETA, J=PRIMA_COMISIONABLE
            # K=PRODUCCION, L=CONSERVACION, M=POL_CORR, N=ASEG
            poliza_raw = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ''

            # Skip empty policies
            if not poliza_raw or poliza_raw.lower() in ('nan', 'none', ''):
                continue

            # Skip marker policy 9999999
            if poliza_raw == '9999999':
                continue

            producto = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ''
            tipo_recibo = str(row[7]).strip() if len(row) > 7 and row[7] is not None else ''

            # Exclude "Comisiones Agente de Zona"
            if 'comision' in tipo_recibo.lower() and 'zona' in tipo_recibo.lower():
                continue

            prima_neta = _to_float(row[8]) if len(row) > 8 else 0
            prima_comisionable = _to_float(row[9]) if len(row) > 9 else 0
            produccion = _to_float(row[10]) if len(row) > 10 else 0
            conservacion = _to_float(row[11]) if len(row) > 11 else 0
            pol_corr = _to_float(row[12]) if len(row) > 12 else 0
            aseg = str(row[13]).strip() if len(row) > 13 and row[13] is not None else ''

            poliza_base, certificado = normalizar_poliza(poliza_raw)

            polizas_raw.append({
                'poliza_base': poliza_base,
                'certificado': certificado,
                'producto': producto,
                'tipo_recibo': tipo_recibo,
                'prima_neta': prima_neta,
                'prima_comisionable': prima_comisionable,
                'produccion': produccion,
                'conservacion': conservacion,
                'pol_corr': pol_corr,
                'aseg': aseg,
            })
        except Exception as e:
            errors.append(f'Fila {i+3}: {e}')

    # Deduplicate exact matches
    seen = set()
    unique = []
    for p in polizas_raw:
        key = (p['poliza_base'], p['certificado'], p['prima_neta'])
        if key not in seen:
            seen.add(key)
            unique.append(p)

    # Calculate hash
    with open(filepath, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()

    prima_total = sum(p['prima_neta'] for p in unique)

    return {
        'rows': unique,
        'num_polizas': len(unique),
        'prima_neta_total': round(prima_total, 2),
        'hash_md5': file_hash,
        'errors': errors,
    }


def _to_float(val):
    """Safely convert to float."""
    if val is None:
        return 0.0
    try:
        return float(str(val).replace(',', '.').strip())
    except (ValueError, TypeError):
        return 0.0
