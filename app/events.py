from . import socketio
from flask_socketio import emit

@socketio.on('connect')
def handle_connect():
    print("🔌 [SOCKET.IO] Un cliente (Cocina / App / Monitor) se ha conectado.")
    emit('conexion_exitosa', {'status': 'Conectado al servidor POS de la Panchería'})

@socketio.on('disconnect')
def handle_disconnect():
    print("❌ [SOCKET.IO] Un cliente se ha desconectado.")

@socketio.on('cocina_accion')
def handle_cocina_accion(data):
    """
    Permite escuchar acciones directas desde pantallas táctiles de cocina 
    si se interactúa vía WebSockets en lugar de HTTP puro.
    """
    print(f"🍳 [KDS Event] Acción recibida: {data}")
    # Aquí puedes procesar lógica en tiempo real adicional si lo requieres