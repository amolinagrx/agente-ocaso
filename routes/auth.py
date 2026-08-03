from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from itsdangerous import URLSafeTimedSerializer
from datetime import timedelta, datetime
import os
import pyotp

auth_bp = Blueprint('auth', __name__)

TOTP_ISSUER = 'Ocaso Armilla'
REMEMBER_DAYS = 7


def _get_serializer():
    from flask import current_app
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _check_remember_cookie(user_id):
    """Check if there's a valid remember_2fa cookie for this user."""
    cookie_val = request.cookies.get('remember_2fa')
    if not cookie_val:
        return False
    try:
        s = _get_serializer()
        data = s.loads(cookie_val, max_age=REMEMBER_DAYS * 86400)
        return str(data.get('user_id')) == str(user_id)
    except Exception:
        return False


def _set_remember_cookie(response, user_id):
    """Set a signed 7-day cookie to remember this device."""
    s = _get_serializer()
    token = s.dumps({'user_id': user_id})
    response.set_cookie(
        'remember_2fa', token,
        max_age=REMEMBER_DAYS * 86400,
        httponly=True,
        secure=request.is_secure,
        samesite='Lax',
        path='/'
    )


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Rate limiting: 10 attempts/min
        rate_key = f'_rl_{request.remote_addr}'
        now = datetime.utcnow()
        data = session.get(rate_key, {'c': 0, 't': now.isoformat()})
        last = datetime.fromisoformat(data['t']) if data.get('t') else now
        if (now - last).seconds < 60 and data.get('c', 0) >= 10:
            flash('Demasiados intentos. Espera un minuto.', 'danger')
            return render_template('login.html')
        session[rate_key] = {'c': data.get('c', 0) + 1 if (now - last).seconds < 60 else 1, 't': now.isoformat()}

        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.activo:
                flash('Usuario o contrasena incorrectos', 'danger')
                return render_template('login.html')

            if user.password_temporal:
                session['pending_user_id'] = user.id
                session['must_change_password'] = True
                return redirect(url_for('auth.cambiar_password'))

            if user.totp_enabled:
                if _check_remember_cookie(user.id):
                    resp = make_response(redirect(url_for('dashboard.index')))
                    login_user(user)
                    return resp

                session['pending_user_id'] = user.id
                return redirect(url_for('auth.verify_2fa'))

            login_user(user)
            next_page = request.args.get('next')
            if next_page and not next_page.startswith('/'):
                next_page = None
            if next_page and '//' in next_page:
                next_page = None
            return redirect(next_page or url_for('dashboard.index'))

        flash('Usuario o contrasena incorrectos', 'danger')
    return render_template('login.html')


@auth_bp.route('/recuperar', methods=['GET', 'POST'])
def recuperar():
    if request.method == 'POST':
        # Option 1: Secret key
        clave = request.form.get('clave_secreta', '')
        master_key = os.environ.get('RECOVERY_MASTER_KEY', 'ybw12dNv.rudtv8vx.2026')
        if clave and master_key and clave == master_key:
            session['recuperar_autorizado'] = True
            usuarios = User.query.order_by(User.username).all()
            return render_template('recuperar.html', paso=2, usuarios=usuarios)

        # Option 2: Email recovery
        email = request.form.get('email', '').strip()
        if email:
            user = User.query.filter_by(email=email, activo=True).first()
            if user:
                import secrets
                code = ''.join(str(secrets.randbelow(10)) for _ in range(6))
                user.recovery_code = code
                user.recovery_code_expires = datetime.utcnow() + timedelta(minutes=15)
                db.session.commit()
                from utils.email import send_recovery_email
                send_recovery_email(email, user.username, code)
                flash('Si el email existe, recibiras un codigo de verificacion', 'success')
            else:
                flash('Si el email existe, recibiras un codigo de verificacion', 'success')

        # Option 3: Verify recovery code
        rec_code = request.form.get('recovery_code', '')
        if rec_code:
            user = User.query.filter_by(recovery_code=rec_code, activo=True).first()
            if user and user.recovery_code_expires and user.recovery_code_expires > datetime.utcnow():
                user.recovery_code = None
                user.recovery_code_expires = None
                db.session.commit()
                session['recovery_user_id'] = user.id
                return render_template('recuperar.html', paso=3, recovery_user=user)
            else:
                flash('Codigo invalido o caducado', 'danger')

        return render_template('recuperar.html', paso=1)

    return render_template('recuperar.html', paso=1)


@auth_bp.route('/recuperar/cambiar', methods=['POST'])
def recuperar_cambiar():
    user_id = request.form.get('user_id', type=int)
    new_password = request.form.get('password', '')

    # Recovery code path (individual user)
    if not user_id:
        user_id = session.get('recovery_user_id')

    if not user_id or len(new_password) < 3:
        flash('Selecciona un usuario y pon una contrasena valida', 'danger')
        return redirect(url_for('auth.recuperar'))

    # Check authorization
    if not session.get('recuperar_autorizado') and session.get('recovery_user_id') != user_id:
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('auth.recuperar'))

    user = User.query.get(user_id)
    if not user:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('auth.recuperar'))

    user.set_password(new_password)
    db.session.commit()
    session.pop('recuperar_autorizado', None)
    session.pop('recovery_user_id', None)

    flash(f'Contrasena de {user.username} cambiada correctamente', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/cambiar-password', methods=['GET', 'POST'])
def cambiar_password():
    user_id = session.get('pending_user_id')
    if not user_id or not session.get('must_change_password'):
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        new_pass = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if len(new_pass) < 4:
            flash('La contrasena debe tener al menos 4 caracteres', 'danger')
        elif new_pass != confirm:
            flash('Las contrasenas no coinciden', 'danger')
        else:
            user.set_password(new_pass)
            user.password_temporal = False
            db.session.commit()
            session.pop('must_change_password', None)
            session.pop('pending_user_id', None)
            login_user(user)
            flash('Contrasena cambiada correctamente', 'success')
            return redirect(url_for('dashboard.index'))

    return render_template('cambiar_password.html', username=user.username)


@auth_bp.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    user_id = session.get('pending_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    if not user:
        session.pop('pending_user_id', None)
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('totp_code', '').strip()
        totp = pyotp.TOTP(user.totp_secret)

        if totp.verify(code, valid_window=1):
            session.pop('pending_user_id', None)
            login_user(user)

            remember = request.form.get('remember_device') == 'on'
            session['set_remember_2fa'] = remember

            next_page = request.args.get('next') or url_for('dashboard.index')
            return redirect(next_page)

        flash('Codigo de verificacion incorrecto', 'danger')

    return render_template('login_2fa.html', username=user.username)


@auth_bp.route('/logout')
@login_required
def logout():
    session.pop('pending_user_id', None)
    resp = make_response(redirect(url_for('auth.login')))
    resp.delete_cookie('remember_2fa', path='/')
    logout_user()
    return resp


@auth_bp.route('/set-remember-cookie')
@login_required
def set_remember_cookie_endpoint():
    """Set remember_2fa cookie after successful login with 2FA."""
    remember = session.pop('set_remember_2fa', False)
    if not remember:
        return '', 204
    resp = make_response('', 200)
    _set_remember_cookie(resp, current_user.id)
    return resp


def generate_totp_secret():
    return pyotp.random_base32()


def get_totp_uri(user):
    return pyotp.totp.TOTP(user.totp_secret).provisioning_uri(
        name=user.username, issuer_name=TOTP_ISSUER
    )
