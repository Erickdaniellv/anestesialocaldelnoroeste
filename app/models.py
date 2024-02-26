#C:\Users\Erick Lopez\Desktop\eccomerce\app\models.py
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import uuid
from datetime import datetime, timedelta



class Producto(db.Model):
    __tablename__ = 'productos'
    id_producto = db.Column(db.Integer, primary_key=True)
    codigo_articulo = db.Column(db.Text, nullable=False)
    nombre_art = db.Column(db.Text, nullable=False)
    marca = db.Column(db.Text, nullable=False)
    precio = db.Column(db.Float, nullable=False)
    existencia = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.Integer)
    precioOriginal = db.Column(db.Float)
    multiplo_venta = db.Column(db.Integer)
    equivalencia = db.Column(db.Text)
    posicion = db.Column(db.Text)
    esFavorito = db.Column(db.Boolean)
    ruta_imagen = db.Column(db.String(255), nullable=True)  # Nueva columna para la ruta de la imagen

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    nombre_usuario = db.Column(db.String(1000), nullable=False)
    password_hash = db.Column(db.String(255))
    es_administrador = db.Column(db.Boolean, default=False)
    es_vendedor = db.Column(db.Boolean, default=False)
    rfc = db.Column(db.String(100), nullable=True, unique=True)
    telefono = db.Column(db.String(20), nullable=True)
    direccion = db.Column(db.String(200), nullable=True)
    cp = db.Column(db.String(200), nullable=True)
    state = db.Column(db.String(200), nullable=True)
    pais = db.Column(db.String(200), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)



class Cartsession(db.Model):
    __tablename__ = 'cartsession'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(days=7))


class Cartitem(db.Model):
    __tablename__ = 'cartitem'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('productos.id_producto'))
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    quantity = db.Column(db.Integer, default=1)
    cartsession = db.Column(db.String(36), db.ForeignKey('cartsession.id'))
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True)
    product = db.relationship('Producto')
    user = db.relationship('Usuario')


class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)  # Ahora nullable
    guest_email = db.Column(db.String(100), nullable=True)  # Para usuarios no registrados
    status = db.Column(db.String(50), default='Pendiente')
    total = db.Column(db.Float)
    phone = db.Column(db.String(10))  # Número de teléfono de contacto
    shipping_address = db.relationship('ShippingAddress', backref='order')
    order_items = db.relationship('OrderItem', backref='order', lazy='dynamic')
    cartsession_id = db.Column(db.String(36), nullable=True)  # Asumiendo que usas un UUID como ID de sesión


class OrderItem(db.Model):
    __tablename__ = 'order_item'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('productos.id_producto'))
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)
    product = db.relationship('Producto', backref='order_items')


class ShippingAddress(db.Model):
    __tablename__ = 'shipping_address'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    postal_code = db.Column(db.String(5))
    state = db.Column(db.String(100))


from . import db

class Contacto(db.Model):
    __tablename__ = 'contactos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    mensaje = db.Column(db.Text, nullable=False)

    def __init__(self, nombre, telefono, email, mensaje):
        self.nombre = nombre
        self.telefono = telefono
        self.email = email
        self.mensaje = mensaje
