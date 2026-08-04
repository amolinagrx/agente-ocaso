"""Analysis engine: detect altas, bajas, and renumeraciones."""
from models import db, CarteraFichero, CarteraPoliza, CarteraBaja, CarteraAlta


def run_analysis(fichero):
    """Run full analysis for a newly uploaded file.

    Detects: altas, bajas, renumeraciones.
    """
    mes = fichero.mes
    anio = fichero.anio

    # Get previous month's policies
    mes_ant = mes - 1 if mes > 1 else 12
    anio_ant = anio if mes > 1 else anio - 1
    fichero_ant = CarteraFichero.query.filter_by(mes=mes_ant, anio=anio_ant).first()

    # Current policies
    current_pols = CarteraPoliza.query.filter_by(fichero_id=fichero.id).all()
    current_set = {(p.poliza_base, p.certificado) for p in current_pols}
    current_map = {(p.poliza_base, p.certificado): p for p in current_pols}

    # Previous policies
    prev_set = set()
    prev_map = {}
    if fichero_ant:
        prev_pols = CarteraPoliza.query.filter_by(fichero_id=fichero_ant.id).all()
        prev_set = {(p.poliza_base, p.certificado) for p in prev_pols}
        prev_map = {(p.poliza_base, p.certificado): p for p in prev_pols}

    # Delete old analysis for this month
    CarteraAlta.query.filter_by(mes_hasta=mes, anio_hasta=anio).delete()
    CarteraBaja.query.filter_by(mes_hasta=mes, anio_hasta=anio).delete()

    # Detect altas (in current but not in previous)
    altas = current_set - prev_set
    for key in altas:
        p = current_map[key]
        db.session.add(CarteraAlta(
            mes_desde=mes_ant, anio_desde=anio_ant,
            mes_hasta=mes, anio_hasta=anio,
            poliza_base=p.poliza_base, certificado=p.certificado,
            producto=p.producto, tipo_recibo=p.tipo_recibo,
            prima_neta=p.prima_neta
        ))

    # Detect bajas + renumeraciones
    bajas = prev_set - current_set
    for baja_key in bajas:
        p_prev = prev_map[baja_key]

        # Check if it was renumerada (same product + same prima appears in current)
        renumerada = False
        renumerada_a = None
        for alta_key in altas:
            p_curr = current_map[alta_key]
            if (p_curr.producto == p_prev.producto and
                    abs(p_curr.prima_neta - p_prev.prima_neta) < 0.02):
                renumerada = True
                renumerada_a = p_curr.poliza_base
                break

        db.session.add(CarteraBaja(
            mes_desde=mes_ant, anio_desde=anio_ant,
            mes_hasta=mes, anio_hasta=anio,
            poliza_base=p_prev.poliza_base, certificado=p_prev.certificado,
            producto=p_prev.producto, tipo_recibo=p_prev.tipo_recibo,
            prima_neta=p_prev.prima_neta,
            renumerada=renumerada,
            poliza_renumerada_a=renumerada_a
        ))

    db.session.commit()

    return {
        'altas': len(altas),
        'bajas': sum(1 for _ in CarteraBaja.query.filter_by(mes_hasta=mes, anio_hasta=anio)),
        'bajas_renumeradas': CarteraBaja.query.filter_by(mes_hasta=mes, anio_hasta=anio, renumerada=True).count(),
        'bajas_sospechosas': CarteraBaja.query.filter_by(mes_hasta=mes, anio_hasta=anio, renumerada=False).count(),
    }
