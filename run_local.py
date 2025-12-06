#!/usr/bin/env python3
"""
Script para ejecutar la aplicación Flask localmente
"""
import os
import sys

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, socketio

if __name__ == '__main__':
    # Crear la aplicación
    app = create_app()
    
    # Configurar para desarrollo local
    app.config['FLASK_ENV'] = 'development'
    app.config['FLASK_DEBUG'] = True
    
    # Obtener puerto de variable de entorno o usar 5000 por defecto
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    
    print("=" * 60)
    print("🚀 Iniciando aplicación Flask local")
    print("=" * 60)
    print(f"📍 URL: http://{host}:{port}")
    print(f"🔧 Entorno: {app.config.get('FLASK_ENV', 'development')}")
    print(f"🐛 Debug: {app.config.get('FLASK_DEBUG', False)}")
    print("=" * 60)
    print()
    
    try:
        # Ejecutar con SocketIO (necesario para WebSockets)
        socketio.run(
            app,
            host=host,
            port=port,
            debug=app.config.get('FLASK_DEBUG', True),
            allow_unsafe_werkzeug=True  # Para desarrollo
        )
    except KeyboardInterrupt:
        print("\n\n👋 Deteniendo servidor...")
        sys.exit(0)




