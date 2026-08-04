"""Policy number normalization for Cartera analysis."""


def normalizar_poliza(numero):
    """Normalize a policy number and extract base + certificate.

    Returns (poliza_base, certificado).
    """
    if not numero:
        return '', ''

    # Convert to string and strip whitespace
    s = str(numero).strip()

    # Remove leading zeros
    s = s.lstrip('0')

    if not s:
        return '', ''

    if len(s) <= 7:
        return s, ''
    else:
        base = s[:7]
        certificado = s[7:]
        return base, certificado
