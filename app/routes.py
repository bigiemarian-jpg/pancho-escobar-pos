from flask import Blueprint, jsonify, request, render_template, current_app, redirect, url_for
from .models import db, Producto, Pedido, DetallePedido, Adicional, ZonaEnvio, TurnoCaixa
from . import socketio
import random, json
import os
from werkzeug.utils import secure_filename
from PIL import Image

api_bp = Blueprint('api', __name__, url_prefix='/api')
UPLOAD_FOLDER = 'app/static/uploads'

@api_bp.route('/productos', methods=['GET'])
def listar_todos_los_productos():
    productos = Producto.query.all()
    return jsonify([p.to_dict() for p in productos]), 200

@api_bp.route('/productos/disponibles', methods=['GET'])
def listar_productos_disponibles():
    productos = Producto.query.filter_by(disponible=True).all()
    return jsonify([p.to_dict() for p in productos]), 200

@api_bp.route('/productos/<int:producto_id>', methods=['GET'])
def obtener_producto_individual_api(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    return jsonify(producto.to_dict()), 200

@api_bp.route('/pedidos', methods=['GET', 'POST'])
def gestionar_pedidos():
    if request.method == 'GET':
        pedidos = Pedido.query.all()
        return jsonify([p.to_dict() for p in pedidos]), 200

    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'error': 'Estructura de datos inválida'}), 400

    items = data.get('items', [])
    cliente_nombre = data.get('cliente_nombre', 'Cliente Anónimo')
    tipo_entrega = data.get('tipo_entrega', 'Para Comer Aquí')
    direccion_envio = data.get('direccion_envio', '')
    zona_envio = data.get('zona_envio', '')
    costo_envio = float(data.get('costo_envio', 0.0))
    telefono = data.get('telefono', '')

    if not items:
        return jsonify({'error': 'El pedido no contiene ítems'}), 400

    total_calculado = costo_envio
    detalles_a_crear = []

    for item in items:
        prod_id = item.get('producto_id')
        cantidad = item.get('cantidad', 0)
        personalizacion = item.get('personalizacion', '')

        if cantidad <= 0:
            return jsonify({'error': 'La cantidad debe ser mayor a cero'}), 400

        producto = Producto.query.get(prod_id)
        if not producto or not producto.disponible:
            return jsonify({'error': f'Producto ID {prod_id} no disponible'}), 404

        subtotal = producto.precio * cantidad
        total_calculado += subtotal

        detalles_a_crear.append({
            'producto_id': producto.id,
            'cantidad': cantidad,
            'subtotal': subtotal,
            'personalizacion': personalizacion
        })

    ultimo_pedido = Pedido.query.order_by(Pedido.id.desc()).first()
    if ultimo_pedido and ultimo_pedido.numero_orden and ultimo_pedido.numero_orden.startswith("P-"):
        try:
            siguiente_numero = int(ultimo_pedido.numero_orden.split("-")[1]) + 1
        except ValueError:
            siguiente_numero = Pedido.query.count() + 1
    else:
        siguiente_numero = Pedido.query.count() + 1

    numero_orden = f"P-{siguiente_numero:03d}"

    nuevo_pedido = Pedido(
        numero_orden=numero_orden,
        cliente_nombre=cliente_nombre,
        tipo_entrega=tipo_entrega,
        direccion_envio=direccion_envio,
        zona_envio=zona_envio,
        costo_envio=costo_envio,
        telefono=telefono,
        total=total_calculado,
        estado='Pendiente'
    )
    db.session.add(nuevo_pedido)
    db.session.commit()

    for d in detalles_a_crear:
        detalle = DetallePedido(
            pedido_id=nuevo_pedido.id,
            producto_id=d['producto_id'],
            cantidad=d['cantidad'],
            subtotal=d['subtotal'],
            personalizacion=d['personalizacion']
        )
        db.session.add(detalle)
    db.session.commit()

    pedido_serializado = nuevo_pedido.to_dict()
    socketio.emit('nuevo_pedido', pedido_serializado)

    return jsonify({
        'mensaje': 'Pedido creado con éxito',
        'pedido': pedido_serializado
    }), 201

@api_bp.route('/pedidos/activos', methods=['GET'])
def listar_pedidos_activos():
    pedidos = Pedido.query.filter(Pedido.estado != 'Entregado').order_by(Pedido.id.asc()).all()
    return jsonify([p.to_dict() for p in pedidos]), 200

@api_bp.route('/pedidos/pendientes', methods=['GET'])
def listar_pedidos_pendientes():
    pedidos = Pedido.query.filter_by(estado='Pendiente').order_by(Pedido.id.asc()).all()
    return jsonify([p.to_dict() for p in pedidos]), 200

@api_bp.route('/pedidos/<int:pedido_id>/estado', methods=['PATCH'])
def actualizar_estado_pedido(pedido_id):
    data = request.get_json() or {}
    nuevo_estado = data.get('estado')
    
    if not nuevo_estado:
        return jsonify({'error': 'No se especificó el estado'}), 400

    # Normalizar texto de forma segura
    estado_limpio = str(nuevo_estado).strip().title()
    
    # Manejo especial para espacios internos (Ej: "En Camino")
    if estado_limpio.lower() == 'en camino':
        estado_limpio = 'En Camino'

    estados_validos = ['Pendiente', 'Preparacion', 'Listo', 'En Camino', 'Entregado']
    if estado_limpio not in estados_validos:
        return jsonify({'error': f'Estado inválido: {estado_limpio}'}), 400

    pedido = Pedido.query.get_or_404(pedido_id)
    pedido.estado = estado_limpio
    db.session.commit()

    payload = {
        'id': pedido.id,
        'numero_orden': pedido.numero_orden,
        'estado': pedido.estado,
        'tipo_entrega': pedido.tipo_entrega
    }
    
    # Emitir por Socket.IO a todas las pantallas
    socketio.emit('actualizacion_estado', payload)

    return jsonify({'mensaje': 'Estado actualizado', 'pedido': payload}), 200

@api_bp.route('/productos/<int:producto_id>/disponibilidad', methods=['PATCH'])
def actualizar_disponibilidad(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    data = request.get_json()
    
    if 'disponible' in data:
        producto.disponible = bool(data['disponible'])
        db.session.commit()
        socketio.emit('cambio_disponibilidad', producto.to_dict())
        return jsonify({'mensaje': 'Disponibilidad actualizada', 'producto': producto.to_dict()}), 200

    return jsonify({'error': 'Campo "disponible" requerido'}), 400

@api_bp.route('/zonas', methods=['GET'])
def listar_zonas():
    zonas = ZonaEnvio.query.filter_by(disponible=True).all()
    return jsonify([z.to_dict() for z in zonas])

@api_bp.route('/zonas', methods=['POST'])
def crear_zona_envio():
    data = request.get_json()
    nombre = data.get('nombre')
    costo = data.get('costo')

    if not nombre or costo is None:
        return jsonify({'error': 'Nombre y costo son obligatorios'}), 400

    nueva_zona = ZonaEnvio(
        nombre=nombre.strip(),
        costo=float(costo),
        disponible=True
    )
    db.session.add(nueva_zona)
    db.session.commit()
    return jsonify({'mensaje': 'Zona creada con éxito', 'zona': nueva_zona.to_dict()}), 201

@api_bp.route('/zonas/<int:id>', methods=['DELETE'])
def eliminar_zona_envio(id):
    zona = ZonaEnvio.query.get_or_404(id)
    db.session.delete(zona)
    db.session.commit()
    return jsonify({'mensaje': 'Zona eliminada correctamente'}), 200

@api_bp.route('/adicionales', methods=['GET'])
def listar_adicionales():
    adicionales = Adicional.query.all()
    return jsonify([a.to_dict() for a in adicionales])

@api_bp.route('/adicionales', methods=['POST'])
def crear_adicional():
    data = request.get_json()
    nombre = data.get('nombre')
    precio = data.get('precio')

    if not nombre or precio is None:
        return jsonify({'error': 'Nombre y precio son obligatorios'}), 400

    nuevo_adicional = Adicional(
        nombre=nombre.strip(),
        precio=float(precio),
        disponible=True
    )
    db.session.add(nuevo_adicional)
    db.session.commit()
    return jsonify({'mensaje': 'Adicional creado con éxito', 'adicional': nuevo_adicional.to_dict()}), 201

@api_bp.route('/adicionales/<int:id>', methods=['PUT'])
def actualizar_adicional(id):
    adicional = Adicional.query.get_or_404(id)
    data = request.get_json()
    
    if 'nombre' in data:
        adicional.nombre = data['nombre'].strip()
    if 'precio' in data:
        adicional.precio = float(data['precio'])
        
    db.session.commit()
    return jsonify({'mensaje': 'Adicional actualizado con éxito', 'adicional': adicional.to_dict()})

@api_bp.route('/adicionales/<int:id>/disponibilidad', methods=['PATCH'])
def actualizar_disponibilidad_adicional(id):
    adicional = Adicional.query.get_or_404(id)
    data = request.get_json()
    
    if 'disponible' in data:
        adicional.disponible = bool(data['disponible'])
        db.session.commit()
        return jsonify({'mensaje': 'Disponibilidad actualizada', 'adicional': adicional.to_dict()})

    return jsonify({'error': 'Campo "disponible" requerido'}), 400

@api_bp.route('/adicionales/<int:id>', methods=['DELETE'])
def eliminar_adicional(id):
    adicional = Adicional.query.get_or_404(id)
    db.session.delete(adicional)
    db.session.commit()
    return jsonify({'mensaje': 'Adicional eliminado correctamente'}), 200

@api_bp.route('/caja/estado', methods=['GET'])
def estado_caja():
    turno_abierto = TurnoCaixa.query.filter_by(estado='Abierta').first()
    if not turno_abierto:
        return jsonify({'abierta': False}), 200
    
    pedidos_totales = Pedido.query.all()
    total_ventas_actuales = sum(p.total for p in pedidos_totales)
    
    turno_dict = turno_abierto.to_dict()
    turno_dict['total_ventas_en_vivo'] = total_ventas_actuales

    return jsonify({'abierta': True, 'turno': turno_dict}), 200

@api_bp.route('/caja/abrir', methods=['POST'])
def abrir_caja():
    turno_previo = TurnoCaixa.query.filter_by(estado='Abierta').first()
    if turno_previo:
        return jsonify({'error': 'Ya existe una caja abierta'}), 400
    
    data = request.get_json() or {}
    empleado = data.get('empleado', 'Cajero Anónimo').strip()
    monto_inicial = float(data.get('monto_inicial', 0.0))

    if not empleado:
        empleado = 'Cajero Anónimo'

    nuevo_turno = TurnoCaixa(
        empleado=empleado,
        monto_inicial=monto_inicial,
        estado='Abierta'
    )
    db.session.add(nuevo_turno)
    db.session.commit()
    return jsonify({'mensaje': 'Caja abierta con éxito', 'turno': nuevo_turno.to_dict()}), 201

@api_bp.route('/caja/cerrar', methods=['POST'])
def cerrar_caja():
    turno_abierto = TurnoCaixa.query.filter_by(estado='Abierta').first()
    if not turno_abierto:
        return jsonify({'error': 'No hay ninguna caja abierta'}), 400

    data = request.get_json() or {}
    monto_final_declarado = float(data.get('monto_final', 0.0))

    pedidos_turno = Pedido.query.all()
    total_ventas_calculado = sum(p.total for p in pedidos_turno)

    turno_abierto.total_ventas_efectivo = total_ventas_calculado
    turno_abierto.monto_final = monto_final_declarado
    turno_abierto.estado = 'Cerrada'
    turno_abierto.fecha_cierre = db.func.current_timestamp()
    
    esperado = turno_abierto.monto_inicial + turno_abierto.total_ventas_efectivo
    turno_abierto.diferencia = monto_final_declarado - esperado

    db.session.commit()
    return jsonify({
        'mensaje': 'Caja cerrada correctamente', 
        'turno': turno_abierto.to_dict(),
        'resumen': {
            'monto_inicial': turno_abierto.monto_inicial,
            'total_ventas': turno_abierto.total_ventas_efectivo,
            'esperado_en_caja': esperado,
            'declarado': monto_final_declarado,
            'diferencia': turno_abierto.diferencia
        }
    }), 200

@api_bp.route('/admin/ventas', methods=['GET'])
def obtener_historial_ventas():
    pedidos = Pedido.query.order_by(Pedido.id.desc()).all()
    return jsonify([p.to_dict() for p in pedidos]), 200

@api_bp.route('/admin/turnos', methods=['GET'])
def obtener_historial_turnos():
    turnos = TurnoCaixa.query.order_by(TurnoCaixa.id.desc()).all()
    return jsonify([t.to_dict() for t in turnos]), 200

views_bp = Blueprint('views', __name__)

@views_bp.route('/app', methods=['GET'])
def vista_cliente():
    return render_template('cliente.html')

@views_bp.route('/cocina', methods=['GET'])
def vista_cocina():
    return render_template('cocina.html')

@views_bp.route('/pantalla', methods=['GET'])
def vista_pantalla():
    return render_template('pantalla.html')

@views_bp.route('/admin', methods=['GET'])
def vista_admin():
    return render_template('admin.html')

@views_bp.route('/pedido/<numero_orden>', methods=['GET'])
def vista_seguimiento(numero_orden):
    return render_template('seguimiento.html')

@api_bp.route('/pedido/<numero_orden>', methods=['GET'])
def api_detalle_pedido(numero_orden):
    pedido = Pedido.query.filter((Pedido.numero_orden == numero_orden) | (Pedido.id == numero_orden)).first()
    if not pedido:
        return jsonify({"error": "No encontrado"}), 404
    return jsonify(pedido.to_dict())

def optimizar_y_guardar_imagen(file_storage):
    if not file_storage or file_storage.filename == '':
        return None
    
    filename = secure_filename(file_storage.filename)
    nombre_base, _ = os.path.splitext(filename)
    nuevo_nombre = f"{nombre_base}_{int(os.urandom(4).hex(), 16)}.webp"
    
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    ruta_destino = os.path.join(UPLOAD_FOLDER, nuevo_nombre)

    imagen = Image.open(file_storage.stream)
    if imagen.mode in ("RGBA", "P"):
        imagen = imagen.convert("RGB")

    imagen.thumbnail((500, 500))
    imagen.save(ruta_destino, "WEBP", quality=80)
    return nuevo_nombre

@api_bp.route('/productos', methods=['POST'])
def crear_producto():
    nombre = request.form.get('nombre')
    precio = request.form.get('precio')
    categoria = request.form.get('categoria')
    ingredientes = request.form.get('ingredientes', '[]')
    imagen_file = request.files.get('imagen')

    if not nombre or not precio or not categoria:
        return jsonify({'error': 'Faltan campos obligatorios'}), 400

    nombre_imagen = optimizar_y_guardar_imagen(imagen_file) or 'default_pancho.png'

    nuevo_producto = Producto(
        nombre=nombre.strip(),
        precio=float(precio),
        categoria=categoria.strip(),
        ingredientes=ingredientes,
        imagen=nombre_imagen,
        disponible=True
    )
    db.session.add(nuevo_producto)
    db.session.commit()

    return jsonify({'mensaje': 'Producto creado con éxito', 'producto': nuevo_producto.to_dict()}), 201

@api_bp.route('/productos/<int:producto_id>', methods=['DELETE'])
def eliminar_producto(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    db.session.delete(producto)
    db.session.commit()
    socketio.emit('producto_eliminado', {'id': producto_id})
    return jsonify({'mensaje': 'Producto eliminado correctamente'}), 200

@api_bp.route('/productos/<int:id>', methods=['GET', 'PUT', 'DELETE'])
def gestionar_producto_individual(id):
    producto = Producto.query.get_or_404(id)
    
    if request.method == 'GET':
        return jsonify(producto.to_dict())
        
    elif request.method == 'PUT':
        nombre = request.form.get('nombre')
        precio = request.form.get('precio')
        categoria = request.form.get('categoria')
        ingredientes = request.form.get('ingredientes')
        imagen_file = request.files.get('imagen')

        if nombre: 
            producto.nombre = nombre.strip()
        if precio: 
            producto.precio = float(precio)
        if categoria: 
            producto.categoria = categoria.strip()
        if ingredientes:
            producto.ingredientes = ingredientes
            
        if imagen_file and imagen_file.filename != '':
            nombre_imagen = optimizar_y_guardar_imagen(imagen_file)
            if nombre_imagen:
                producto.imagen = nombre_imagen

        db.session.commit()
        return jsonify({'success': True})
        
    elif request.method == 'DELETE':
        db.session.delete(producto)
        db.session.commit()
        return jsonify({'success': True})

@views_bp.route('/productos/nuevo', methods=['GET', 'POST'])
def vista_nuevo_producto():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        precio = request.form.get('precio')
        categoria = request.form.get('categoria')
        ingredientes = request.form.get('ingredientes', '[]')
        imagen_file = request.files.get('imagen')

        if nombre and precio and categoria:
            nombre_imagen = optimizar_y_guardar_imagen(imagen_file) or 'default_pancho.png'
            nuevo_producto = Producto(
                nombre=nombre.strip(),
                precio=float(precio),
                categoria=categoria.strip(),
                ingredientes=ingredientes,
                imagen=nombre_imagen,
                disponible=True
            )
            db.session.add(nuevo_producto)
            db.session.commit()
            return redirect(url_for('views.vista_admin'))

    return render_template('nuevo_producto.html')
