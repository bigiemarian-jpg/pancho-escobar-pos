from flask_sqlalchemy import SQLAlchemy
import json

db = SQLAlchemy()

class Producto(db.Model):
    __tablename__ = 'productos'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    ingredientes = db.Column(db.Text, nullable=True)
    stock = db.Column(db.Integer, default=50)
    disponible = db.Column(db.Boolean, default=True)
    imagen = db.Column(db.String(150), default='default_pancho.png')

    def to_dict(self):
        lista_ingredientes = []
        if self.ingredientes:
            try:
                if isinstance(self.ingredientes, str):
                    lista_ingredientes = json.loads(self.ingredientes)
                elif isinstance(self.ingredientes, list):
                    lista_ingredientes = self.ingredientes
            except Exception:
                lista_ingredientes = [self.ingredientes]

        return {
            'id': self.id,
            'nombre': self.nombre,
            'precio': self.precio,
            'categoria': self.categoria,
            'ingredientes': lista_ingredientes,
            'stock': self.stock,
            'disponible': self.disponible,
            'imagen': self.imagen
        }

class Pedido(db.Model):
    __tablename__ = 'pedidos'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_orden = db.Column(db.String(20), unique=True, nullable=False)
    cliente_nombre = db.Column(db.String(100), nullable=False)
    tipo_entrega = db.Column(db.String(50), nullable=False)
    direccion_envio = db.Column(db.String(200), nullable=True)
    zona_envio = db.Column(db.String(100), nullable=True)
    costo_envio = db.Column(db.Float, default=0.0)
    telefono = db.Column(db.String(50), nullable=True)
    total = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(30), default='Pendiente')
    detalles = db.relationship('DetallePedido', backref='pedido', cascade='all, delete-orphan')

    def to_dict(self):
        detalles_lista = [d.to_dict() for d in self.detalles]
        return {
            'id': self.id,
            'numero_orden': self.numero_orden,
            'cliente_nombre': self.cliente_nombre,
            'tipo_entrega': self.tipo_entrega,
            'direccion_envio': self.direccion_envio,
            'zona_envio': self.zona_envio,
            'costo_envio': self.costo_envio,
            'telefono': self.telefono,
            'total': self.total,
            'estado': self.estado,
            'detalles': detalles_lista,
            'items': detalles_lista  # 💡 Agregado como 'items' para que la cocina lo lea perfectamente
        }

class DetallePedido(db.Model):
    __tablename__ = 'detalles_pedido'
    
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    personalizacion = db.Column(db.Text, nullable=True)
    producto = db.relationship('Producto')

    def to_dict(self):
        return {
            'id': self.id,
            'producto_nombre': self.producto.nombre if self.producto else 'Desconocido',
            'nombre': self.producto.nombre if self.producto else 'Desconocido', # 💡 Compatibilidad con 'nombre'
            'cantidad': self.cantidad,
            'subtotal': self.subtotal,
            'personalizacion': self.personalizacion
        }

class Adicional(db.Model):
    __tablename__ = 'adicionales'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    disponible = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'precio': self.precio,
            'disponible': self.disponible
        }

class ZonaEnvio(db.Model):
    __tablename__ = 'zonas_envio'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    costo = db.Column(db.Float, nullable=False)
    disponible = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'costo': self.costo,
            'disponible': self.disponible
        }

class TurnoCaixa(db.Model):
    __tablename__ = 'turno_caja'
    
    id = db.Column(db.Integer, primary_key=True)
    empleado = db.Column(db.String(100), nullable=False, default='Cajero Principal')
    monto_inicial = db.Column(db.Float, nullable=False, default=0.0)
    monto_final = db.Column(db.Float, nullable=True)
    total_ventas_efectivo = db.Column(db.Float, default=0.0)
    total_ventas_otros = db.Column(db.Float, default=0.0)
    diferencia = db.Column(db.Float, nullable=True)
    estado = db.Column(db.String(20), default='Abierta')
    fecha_apertura = db.Column(db.DateTime, default=db.func.current_timestamp())
    fecha_cierre = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'empleado': self.empleado,
            'monto_inicial': self.monto_inicial,
            'monto_final': self.monto_final,
            'total_ventas_efectivo': self.total_ventas_efectivo,
            'total_ventas_otros': self.total_ventas_otros,
            'diferencia': self.diferencia,
            'estado': self.estado,
            'fecha_apertura': str(self.fecha_apertura),
            'fecha_cierre': str(self.fecha_cierre) if self.fecha_cierre else None
        }