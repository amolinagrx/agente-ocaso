from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from itsdangerous import URLSafeTimedSerializer
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
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.activo:
                flash('Usuario desactivado. Contacta con el administrador.', 'danger')
                return render_template('login.html')

            if user.totp_enabled:
                # Check if this device is remembered
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
            return redirect(next_page or url_for('dashboard.index'))

        flash('Usuario o contrasena incorrectos', 'danger')
    return render_template('login.html')


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
