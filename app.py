import os
import secrets
from flask import Flask, session
from flask_login import LoginManager
from models import db, User


def create_app():
    app = Flask(__name__)

    @app.context_processor
    def inject_globals():
        from models import COMPANIAS_ESPANA, RAMOS_ESPANA
        return {'companias': COMPANIAS_ESPANA, 'ramos_list': RAMOS_ESPANA,
                'today': __import__('datetime').date.today()}

    @app.route('/')
    def root():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    data_dir = os.environ.get('DATA_DIR', '/data')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{data_dir}/ocaso.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = f'{data_dir}/uploads'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from routes.auth import auth_bp
    from routes.recibos import recibos_bp
    from routes.clientes import clientes_bp
    from routes.polizas import polizas_bp
    from routes.renovaciones import renovaciones_bp
    from routes.siniestros import siniestros_bp
    from routes.dashboard import dashboard_bp
    from routes.comunicaciones import comunicaciones_bp
    from routes.whatsapp import whatsapp_bp
    from routes.listados import listados_bp
    from routes.asistente import asistente_bp
    from routes.ajustes import ajustes_bp
    from routes.usuarios import usuarios_bp
    from routes.agenda import agenda_bp
    from routes.leads import leads_bp
    from routes.api_externa import api_externa_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(recibos_bp, url_prefix='/recibos')
    app.register_blueprint(clientes_bp, url_prefix='/clientes')
    app.register_blueprint(polizas_bp, url_prefix='/polizas')
    app.register_blueprint(renovaciones_bp, url_prefix='/renovaciones')
    app.register_blueprint(siniestros_bp, url_prefix='/siniestros')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(comunicaciones_bp, url_prefix='/comunicaciones')
    app.register_blueprint(whatsapp_bp, url_prefix='/whatsapp')
    app.register_blueprint(listados_bp, url_prefix='/listados')
    app.register_blueprint(asistente_bp, url_prefix='/asistente')
    app.register_blueprint(ajustes_bp, url_prefix='/ajustes')
    app.register_blueprint(usuarios_bp, url_prefix='/usuarios')
    app.register_blueprint(agenda_bp, url_prefix='/agenda')
    app.register_blueprint(leads_bp, url_prefix='/leads')
    app.register_blueprint(api_externa_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    with app.app_context():
        db.create_all()
        _migrar_schema()
        _seed_user(app)
        _auto_seed_if_empty(app)

    return app


def _seed_user(app):
    username = os.environ.get('OCASO_USER', 'admin')
    password = os.environ.get('OCASO_PASS', 'ocaso2025')
    if not User.query.filter_by(username=username).first():
        user = User(username=username, password='pending', nombre='Administrador', is_admin=True,
                     permisos='{}', activo=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f'User created: {username}')
    else:
        user = User.query.filter_by(username=username).first()
        if not user.is_admin and user.username == 'admin':
            user.is_admin = True
            user.nombre = user.nombre or 'Administrador'
            db.session.commit()
        # Migrate plaintext password to hash if needed
        if user.password == 'ocaso2025':
            user.set_password('ocaso2025')
            db.session.commit()


def _auto_seed_if_empty(app):
    """Only seed in development mode."""
    if os.environ.get('OCASO_ENV', 'production') != 'development':
        return
    from models import Cliente
    if Cliente.query.count() == 0:
        print('Empty database detected. Running seed data...')
        try:
            from seed import run_seed
            run_seed()
            print('Seed data loaded successfully.')
        except Exception as e:
            print(f'Seed error (non-fatal): {e}')


def _migrar_schema():
    """Add missing columns to existing tables without data loss."""
    import sqlite3
    from flask import current_app

    db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(users)")
        user_cols = {row[1] for row in cursor.fetchall()}

        for col, col_type in [
            ('nombre', 'VARCHAR(200)'),
            ('is_admin', 'BOOLEAN DEFAULT 0'),
            ('activo', 'BOOLEAN DEFAULT 1'),
            ('permisos', 'TEXT DEFAULT \'{}\''),
            ('totp_secret', 'VARCHAR(64)'),
            ('totp_enabled', 'BOOLEAN DEFAULT 0'),
        ]:
            if col not in user_cols:
                cursor.execute(f'ALTER TABLE users ADD COLUMN {col} {col_type}')
                print(f'Migracion: anadida columna {col} a users')

        cursor.execute("PRAGMA table_info(clientes)")
        cliente_cols = {row[1] for row in cursor.fetchall()}
        for col, col_type in [
            ('codigo_postal', 'VARCHAR(10)'),
            ('poblacion', 'VARCHAR(100)'),
            ('provincia', 'VARCHAR(100)'),
        ]:
            if col not in cliente_cols:
                cursor.execute(f'ALTER TABLE clientes ADD COLUMN {col} {col_type}')
                print(f'Migracion: anadida columna {col} a clientes')

        cursor.execute("PRAGMA table_info(polizas)")
        cols = {row[1] for row in cursor.fetchall()}

        migrations = [
            ('numero_cuenta', 'VARCHAR(34)'),
            ('fecha_baja', 'DATE'),
            ('unidades', 'INTEGER DEFAULT 1'),
            ('detalles', 'TEXT'),
        ]

        for col, col_type in migrations:
            if col not in cols:
                try:
                    cursor.execute(f'ALTER TABLE polizas ADD COLUMN {col} {col_type}')
                    print(f'Migracion: anadida columna {col} a polizas')
                except Exception as e:
                    print(f'Migracion polizas.{col}: {e}')

        conn.commit()
        conn.close()
    except Exception as e:
        print(f'Error en migracion (no critico): {e}')


if __name__ == '__main__':
    app = create_app()
    debug = os.environ.get('OCASO_ENV', 'production') == 'development'
    app.run(host='0.0.0.0', port=5050, debug=debug)
