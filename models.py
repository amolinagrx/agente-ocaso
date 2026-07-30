from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

COMPANIAS_ESPANA = [
    'Ocaso',
    'Mapfre',
    'Mutua Madrilena',
    'Allianz',
    'AXA',
    'Generali',
    'Zurich',
    'Santalucia',
    'Catalana Occidente',
    'Pelayo',
    'Reale',
    'Helvetia',
    'FIATC',
    'Linea Directa',
    'Verti',
    'Qualitas Auto',
    'Liberty',
    'Caser',
    'Asisa',
    'Adeslas',
    'Sanitas',
    'DKV',
    'Asemfa',
    'MGS',
    'Prevision Medica',
    'Aegon',
    'MetLife',
    'Vidacaixa',
    'Ibercaja',
    'Unicorp Vida',
    'Asefa',
    'Plus Ultra',
    'Mussap',
    'SegurCaixa',
    'RGA',
    'Bansabadell',
    'Bilbao',
    'Lagun Aro',
    'Previsora General',
    'Premaat',
    'Otra',
]

RAMOS_ESPANA = [
    'Auto',
    'Hogar',
    'Vida',
    'Vida Riesgo',
    'Vida Ahorro',
    'Decesos',
    'Accidentes',
    'Salud',
    'Asistencia Sanitaria',
    'Comercio',
    'Negocio',
    'Responsabilidad Civil',
    'Comunidades',
    'Empresas',
    'PYME',
    'Transportes',
    'Flotas',
    'Embarcaciones',
    'Caza',
    'Pesca',
    'Mascotas',
    'Agricola',
    'Industrial',
    'Construccion',
    'Todo Riesgo Construccion',
    'Credito',
    'Caucion',
    'Defensa Juridica',
    'Asistencia en Viaje',
    'Dependencia',
    'Jubilacion',
    'Planes de Pensiones',
    'Multirriesgo',
    'Aeronaves',
    'Ciberriesgo',
    'Proteccion de Pagos',
    'Baja Laboral',
]


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    nombre = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    activo = db.Column(db.Boolean, default=True)
    permisos = db.Column(db.Text, default='{}')
    totp_secret = db.Column(db.String(64))
    totp_enabled = db.Column(db.Boolean, default=False)  # JSON: {"modulo": "rw"|"r"|"none"}

    def set_password(self, raw):
        self.password = generate_password_hash(raw, method='pbkdf2:sha256')

    def check_password(self, raw):
        return check_password_hash(self.password, raw)

    def tiene_permiso(self, modulo, nivel='r'):
        """Verifica si el usuario tiene al menos nivel de permiso en un modulo."""
        if self.is_admin:
            return True
        import json
        try:
            p = json.loads(self.permisos or '{}')
        except json.JSONDecodeError:
            return False
        perm = p.get(modulo, 'none')
        if perm == 'rw':
            return True
        if perm == 'r' and nivel == 'r':
            return True
        return False


class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    dni = db.Column(db.String(20), unique=True)
    direccion = db.Column(db.String(300))
    codigo_postal = db.Column(db.String(10))
    poblacion = db.Column(db.String(100))
    provincia = db.Column(db.String(100))
    telefono = db.Column(db.String(30))
    email = db.Column(db.String(120))
    fecha_nacimiento = db.Column(db.Date)
    fecha_alta = db.Column(db.DateTime, default=datetime.utcnow)
    notas = db.Column(db.Text)
    alerta_devoluciones = db.Column(db.Boolean, default=False)

    polizas = db.relationship('Poliza', backref='cliente', lazy='dynamic', cascade='all, delete-orphan')
    recibos = db.relationship('Recibo', backref='cliente', lazy='dynamic', cascade='all, delete-orphan')
    siniestros = db.relationship('Siniestro', backref='cliente', lazy='dynamic', cascade='all, delete-orphan')
    contactos = db.relationship('HistorialContacto', backref='cliente', lazy='dynamic', cascade='all, delete-orphan',
                                order_by='HistorialContacto.fecha.desc()')
    comunicaciones = db.relationship('Comunicacion', backref='cliente', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def devoluciones_count(self):
        return self.recibos.filter(Recibo.estado == 'devuelto').count()

    @property
    def polizas_activas(self):
        return self.polizas.filter(Poliza.activa == True).all()


class Poliza(db.Model):
    __tablename__ = 'polizas'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    numero_poliza = db.Column(db.String(50), unique=True, nullable=False)
    ramo = db.Column(db.String(50), nullable=False)
    compania = db.Column(db.String(50), default='Ocaso')
    descripcion = db.Column(db.String(300))
    capital_asegurado = db.Column(db.Float, default=0)
    prima_anual = db.Column(db.Float, default=0)
    fecha_efecto = db.Column(db.Date, nullable=False)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    activa = db.Column(db.Boolean, default=True)
    fecha_baja = db.Column(db.Date)
    numero_cuenta = db.Column(db.String(34))
    unidades = db.Column(db.Integer, default=1)
    detalles = db.Column(db.Text)

    # Vehicle-specific fields
    marca = db.Column(db.String(50))
    modelo = db.Column(db.String(50))
    anio = db.Column(db.Integer)
    matricula = db.Column(db.String(20))
    tipo_cobertura = db.Column(db.String(50))

    # Home-specific fields
    tipo_vivienda = db.Column(db.String(50))
    metros = db.Column(db.Integer)
    continente = db.Column(db.Float)
    contenido = db.Column(db.Float)

    siniestros = db.relationship('Siniestro', backref='poliza', lazy='dynamic',
                                 cascade='all, delete-orphan')
    renovaciones = db.relationship('Renovacion', backref='poliza', lazy='dynamic',
                                   cascade='all, delete-orphan')


class Recibo(db.Model):
    __tablename__ = 'recibos'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    poliza_id = db.Column(db.Integer, db.ForeignKey('polizas.id'))
    numero_poliza = db.Column(db.String(50))
    concepto = db.Column(db.String(200))
    importe = db.Column(db.Float, nullable=False)
    fecha_emision = db.Column(db.Date)
    fecha_cargo = db.Column(db.Date)
    estado = db.Column(db.String(20), default='pendiente')  # cobrado, devuelto, pendiente
    estado_gestion = db.Column(db.String(30))  # contactado, transferencia, anulado, pendiente_revision
    notas = db.Column(db.Text)
    compania = db.Column(db.String(50), default='Ocaso')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    poliza_rel = db.relationship('Poliza', backref='recibos')


class Renovacion(db.Model):
    __tablename__ = 'renovaciones'
    id = db.Column(db.Integer, primary_key=True)
    poliza_id = db.Column(db.Integer, db.ForeignKey('polizas.id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    prima = db.Column(db.Float, default=0)
    estado = db.Column(db.String(30), default='no_contactado')
    # no_contactado, contactado, presupuesto_enviado, confirmado
    notas = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Siniestro(db.Model):
    __tablename__ = 'siniestros'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    poliza_id = db.Column(db.Integer, db.ForeignKey('polizas.id'))
    numero_expediente = db.Column(db.String(50), unique=True, nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text)
    fecha_ocurrencia = db.Column(db.Date)
    fecha_apertura = db.Column(db.Date, default=date.today)
    estado = db.Column(db.String(30), default='abierto')
    # abierto, documentacion_enviada, perito_asignado, en_taller,
    # en_valoracion, pendiente_resolucion, resuelto, cerrado
    fecha_ultima_actualizacion = db.Column(db.DateTime, default=datetime.utcnow)
    importe_estimado = db.Column(db.Float, default=0)

    hitos = db.relationship('HitoSiniestro', backref='siniestro', lazy='dynamic',
                            cascade='all, delete-orphan', order_by='HitoSiniestro.fecha.desc()')
    documentos = db.relationship('DocumentoSiniestro', backref='siniestro', lazy='dynamic',
                                 cascade='all, delete-orphan')


class HitoSiniestro(db.Model):
    __tablename__ = 'hitos_siniestro'
    id = db.Column(db.Integer, primary_key=True)
    siniestro_id = db.Column(db.Integer, db.ForeignKey('siniestros.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(30))
    notas = db.Column(db.Text)


class DocumentoSiniestro(db.Model):
    __tablename__ = 'documentos_siniestro'
    id = db.Column(db.Integer, primary_key=True)
    siniestro_id = db.Column(db.Integer, db.ForeignKey('siniestros.id'), nullable=False)
    nombre = db.Column(db.String(300))
    tipo = db.Column(db.String(50))  # parte_amistoso, presupuesto, informe_pericial, otro
    ruta = db.Column(db.String(500))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class HistorialContacto(db.Model):
    __tablename__ = 'historial_contacto'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    tipo = db.Column(db.String(30))  # llamada, whatsapp, email, visita
    notas = db.Column(db.Text)


class DocumentoCliente(db.Model):
    __tablename__ = 'documentos_cliente'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    nombre = db.Column(db.String(300))
    tipo = db.Column(db.String(50))
    ruta = db.Column(db.String(500))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Comunicacion(db.Model):
    __tablename__ = 'comunicaciones'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    tipo = db.Column(db.String(30))  # whatsapp, email, sms
    plantilla = db.Column(db.String(100))
    contenido = db.Column(db.Text)
    enviado = db.Column(db.Boolean, default=False)


class PlantillaComunicacion(db.Model):
    __tablename__ = 'plantillas_comunicacion'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(30))  # whatsapp, email, sms
    asunto = db.Column(db.String(200))
    contenido = db.Column(db.Text, nullable=False)


class Configuracion(db.Model):
    __tablename__ = 'configuracion'
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.String(500))


class DocumentoConocimiento(db.Model):
    __tablename__ = 'documentos_conocimiento'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(300), nullable=False)
    tipo = db.Column(db.String(10))
    contenido_raw = db.Column(db.Text)
    num_chunks = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    chunks = db.relationship('ChunkConocimiento', backref='documento', lazy='dynamic',
                             cascade='all, delete-orphan')


class ChunkConocimiento(db.Model):
    __tablename__ = 'chunks_conocimiento'
    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey('documentos_conocimiento.id'), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.Text)
    indice = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MensajeAsistente(db.Model):
    __tablename__ = 'mensajes_asistente'
    id = db.Column(db.Integer, primary_key=True)
    rol = db.Column(db.String(20), nullable=False)  # user, assistant, system
    contenido = db.Column(db.Text, nullable=False)
    contexto_usado = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Agenda(db.Model):
    __tablename__ = 'agenda'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    titulo = db.Column(db.String(300), nullable=False)
    notas = db.Column(db.Text)
    tipo = db.Column(db.String(30), default='nota')  # nota, llamada, reunion, tarea
    completado = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    telefono = db.Column(db.String(30))
    email = db.Column(db.String(120))
    dni = db.Column(db.String(20))
    direccion = db.Column(db.String(300))
    codigo_postal = db.Column(db.String(10))
    poblacion = db.Column(db.String(100))
    provincia = db.Column(db.String(100))
    ramo_interes = db.Column(db.String(100))
    origen = db.Column(db.String(50), default='web')  # web, telefono, presencial, recomendacion, otro
    estado = db.Column(db.String(30), default='nuevo')  # nuevo, contactado, presupuesto, ganado, perdido
    notas = db.Column(db.Text)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApiKey(db.Model):
    __tablename__ = 'api_keys'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    activo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
