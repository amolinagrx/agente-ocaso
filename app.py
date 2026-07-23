import os
from flask import Flask
from flask_login import LoginManager
from models import db, User


def create_app():
    app = Flask(__name__)

    @app.route('/')
    def root():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ocaso-secret-key-2025')
    data_dir = os.environ.get('DATA_DIR', '/data')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{data_dir}/ocaso.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = f'{data_dir}/uploads'

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    from routes.renovaciones import renovaciones_bp
    from routes.siniestros import siniestros_bp
    from routes.calculadora import calculadora_bp
    from routes.dashboard import dashboard_bp
    from routes.comunicaciones import comunicaciones_bp
    from routes.whatsapp import whatsapp_bp
    from routes.asistente import asistente_bp
    from routes.ajustes import ajustes_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(recibos_bp, url_prefix='/recibos')
    app.register_blueprint(clientes_bp, url_prefix='/clientes')
    app.register_blueprint(renovaciones_bp, url_prefix='/renovaciones')
    app.register_blueprint(siniestros_bp, url_prefix='/siniestros')
    app.register_blueprint(calculadora_bp, url_prefix='/calculadora')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(comunicaciones_bp, url_prefix='/comunicaciones')
    app.register_blueprint(whatsapp_bp, url_prefix='/whatsapp')
    app.register_blueprint(asistente_bp, url_prefix='/asistente')
    app.register_blueprint(ajustes_bp, url_prefix='/ajustes')
    app.register_blueprint(api_bp, url_prefix='/api')

    with app.app_context():
        db.create_all()
        _seed_user(app)
        _auto_seed_if_empty(app)

    return app


def _seed_user(app):
    username = os.environ.get('OCASO_USER', 'admin')
    password = os.environ.get('OCASO_PASS', 'ocaso2025')
    if not User.query.filter_by(username=username).first():
        db.session.add(User(username=username, password=password))
        db.session.commit()
        print(f'User created: {username}')


def _auto_seed_if_empty(app):
    from models import Cliente
    if Cliente.query.count() == 0:
        print('Empty database detected. Running seed data...')
        try:
            from seed import run_seed
            run_seed()
            print('Seed data loaded successfully.')
        except Exception as e:
            print(f'Seed error (non-fatal): {e}')


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5050, debug=True)
