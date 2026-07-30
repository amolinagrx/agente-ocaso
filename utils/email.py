"""Email utility using SMTP."""
import os
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def get_smtp_config():
    from models import Configuracion
    return {
        'host': Configuracion.query.filter_by(clave='smtp_host').first(),
        'port': Configuracion.query.filter_by(clave='smtp_port').first(),
        'user': Configuracion.query.filter_by(clave='smtp_user').first(),
        'pass': Configuracion.query.filter_by(clave='smtp_pass').first(),
        'from': Configuracion.query.filter_by(clave='smtp_from').first(),
    }


def _get_config_val(key, default=''):
    from models import Configuracion
    c = Configuracion.query.filter_by(clave=key).first()
    return c.valor if c else default


def send_email(to, subject, body_html):
    """Send HTML email via configured SMTP. Returns True on success."""
    host = _get_config_val('smtp_host')
    port = _get_config_val('smtp_port', '587')
    user = _get_config_val('smtp_user')
    password = _get_config_val('smtp_pass')
    from_addr = _get_config_val('smtp_from', user)

    if not host or not user:
        print('SMTP no configurado')
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = to
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        port_int = int(port) if port else 587
        if port_int == 465:
            server = smtplib.SMTP_SSL(host, port_int, timeout=10)
        else:
            server = smtplib.SMTP(host, port_int, timeout=10)
            server.starttls()

        server.login(user, password)
        server.sendmail(from_addr, [to], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f'Error enviando email: {e}')
        return False


def send_new_user_email(email_to, username, password):
    """Send welcome email with credentials."""
    html = f'''
    <div style="font-family:Arial;max-width:600px;margin:0 auto;border:1px solid #ddd;border-radius:8px;overflow:hidden">
        <div style="background:#003396;color:white;padding:20px;text-align:center">
            <h2 style="margin:0">Ocaso Seguros - Armilla</h2>
        </div>
        <div style="padding:20px">
            <h3>Bienvenido a Ocaso Gestion</h3>
            <p>Se ha creado tu cuenta en el sistema de gestion de Ocaso Armilla.</p>
            <p><strong>Usuario:</strong> {username}</p>
            <p><strong>Contrasena:</strong> <code>{password}</code></p>
            <p>Accede en: <a href="http://gestion.ocasoarmilla.es">gestion.ocasoarmilla.es</a></p>
            <p style="color:#e0002b;font-size:12px">Cambia tu contrasena tras el primer acceso.</p>
        </div>
        <div style="background:#f5f5f5;padding:10px;text-align:center;font-size:11px;color:#666">
            Ocaso Seguros - Oficina Armilla (Granada)
        </div>
    </div>'''
    return send_email(email_to, 'Bienvenido a Ocaso Gestion - Armilla', html)


def send_recovery_email(email_to, username, code):
    """Send password recovery code."""
    html = f'''
    <div style="font-family:Arial;max-width:600px;margin:0 auto;border:1px solid #ddd;border-radius:8px;overflow:hidden">
        <div style="background:#003396;color:white;padding:20px;text-align:center">
            <h2 style="margin:0">Ocaso Seguros - Recuperacion</h2>
        </div>
        <div style="padding:20px">
            <h3>Recuperacion de contrasena</h3>
            <p>Hola <strong>{username}</strong>, has solicitado recuperar tu contrasena.</p>
            <p>Usa este codigo para restablecerla:</p>
            <h2 style="text-align:center;letter-spacing:5px;font-size:32px;margin:20px 0">{code}</h2>
            <p style="color:#666;font-size:12px">Este codigo caduca en 15 minutos. Si no lo solicitaste, ignora este mensaje.</p>
        </div>
    </div>'''
    return send_email(email_to, 'Recuperacion de contrasena - Ocaso Gestion', html)


def send_verification_email(email_to, username, code):
    """Send email verification code."""
    html = f'''
    <div style="font-family:Arial;max-width:600px;margin:0 auto;border:1px solid #ddd;border-radius:8px;overflow:hidden">
        <div style="background:#003396;color:white;padding:20px;text-align:center">
            <h2 style="margin:0">Ocaso Seguros - Verifica tu email</h2>
        </div>
        <div style="padding:20px">
            <p>Hola <strong>{username}</strong>, introduce este codigo para verificar tu correo:</p>
            <h2 style="text-align:center;letter-spacing:5px;font-size:32px;margin:20px 0">{code}</h2>
            <p style="color:#666;font-size:12px">Este codigo caduca en 10 minutos.</p>
        </div>
    </div>'''
    return send_email(email_to, 'Verifica tu email - Ocaso Gestion', html)


def generate_code(length=6):
    return ''.join(str(random.randint(0, 9)) for _ in range(length))
