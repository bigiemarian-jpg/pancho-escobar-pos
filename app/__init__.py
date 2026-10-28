from flask import Flask
from flask_socketio import SocketIO
from .models import db, Producto

socketio = SocketIO()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'clave_secreta_pancheria_dev'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pancheria.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    socketio.init_app(app)

    with app.app_context():
        db.create_all()
        _seed_database()

    # Registrar los Blueprints de la API y de las Vistas Web
    from .routes import api_bp, views_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    # Importar eventos de socketio para que se registren
    from . import events

    return app

def _seed_database():
    """Inserta datos iniciales de prueba si la base de datos está vacía."""
    if Producto.query.count() == 0:
        productos_iniciales = [
            Producto(nombre="Pancho Simple (Largo)", precio=1800.0, categoria="pancho"),
            Producto(nombre="Pancho Completo (Papas Pai + Cheddar)", precio=2500.0, categoria="pancho"),
            Producto(nombre="Mega Panchero Doble Salchicha", precio=3200.0, categoria="pancho"),
            Producto(nombre="Combo Panchero + Gaseosa 500ml", precio=3500.0, categoria="combo"),
            Producto(nombre="Gaseosa Línea 500ml", precio=1200.0, categoria="bebida"),
            Producto(nombre="Porción de Papas Fritas con Cheddar", precio=2200.0, categoria="extra")
        ]
        db.session.add_all(productos_iniciales)
        db.session.commit()
        print("[DB SEED] Productos iniciales cargados correctamente.")