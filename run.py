from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    print("🚀 Iniciando servidor backend de la Panchería POS...")
    # Añadimos ignore_patterns para que las imágenes subidas no disparen reinicios del servidor
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)