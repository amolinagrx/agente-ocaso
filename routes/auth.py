from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
import pyotp

auth_bp = Blueprint('auth', __name__)

TOTP_ISSUER = 'Ocaso Armilla'


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            if not user.activo:
                flash('Usuario desactivado. Contacta con el administrador.', 'danger')
                return render_template('login.html')

            if user.totp_enabled:
                session['pending_user_id'] = user.id
                return redirect(url_for('auth.verify_2fa'))

            login_user(user)
            next_page = request.args.get('next')
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
            return redirect(url_for('dashboard.index'))

        flash('Codigo de verificacion incorrecto', 'danger')

    return render_template('login_2fa.html', username=user.username)


@auth_bp.route('/logout')
@login_required
def logout():
    session.pop('pending_user_id', None)
    logout_user()
    return redirect(url_for('auth.login'))


def generate_totp_secret():
    return pyotp.random_base32()


def get_totp_uri(user):
    return pyotp.totp.TOTP(user.totp_secret).provisioning_uri(
        name=user.username, issuer_name=TOTP_ISSUER
    )
