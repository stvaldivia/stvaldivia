#!/bin/bash

# Script para verificar TODOS los datos en producción
echo "🔍 Verificando datos en producción..."
echo ""

# Descargar Cloud SQL Proxy si no existe
if [ ! -f "cloud-sql-proxy" ]; then
    echo "📥 Descargando Cloud SQL Proxy..."
    curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.darwin.amd64
    chmod +x cloud-sql-proxy
    echo "✅ Cloud SQL Proxy descargado"
fi

# Iniciar proxy en background
echo "🚀 Iniciando Cloud SQL Proxy..."
./cloud-sql-proxy pelagic-river-479014-a3:us-central1:bimba-db &
PROXY_PID=$!

echo "⏳ Esperando que el proxy esté listo..."
sleep 5

echo ""
echo "✅ Proxy iniciado (PID: $PROXY_PID)"
echo ""

export DATABASE_URL="postgresql://bimba_user:qbiqpVcv9zJPVB0aaA9YwfAJSzFIGroUBcwJHNhzsas=@localhost:5432/bimba"
export FLASK_ENV=production

python3 << 'PYEOF'
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("📊 VERIFICACIÓN DE DATOS EN PRODUCCIÓN")
    print("=" * 50)
    
    # Verificar guardarropía
    try:
        result = db.session.execute(text('SELECT COUNT(*) FROM guardarropia_items'))
        count = result.scalar()
        print(f"\n🧥 Guardarropía: {count} registros")
        
        if count > 0:
            result = db.session.execute(text('''
                SELECT ticket_code, customer_name, status, price, deposited_at 
                FROM guardarropia_items 
                ORDER BY deposited_at DESC 
                LIMIT 5
            '''))
            print("   Últimos registros:")
            for row in result.fetchall():
                print(f"      - {row[0]}: {row[1]} ({row[2]}) - ${row[3] or 0} - {row[4]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Verificar empleados
    try:
        result = db.session.execute(text('SELECT COUNT(*) FROM employees WHERE is_active = true'))
        count = result.scalar()
        print(f"\n👥 Empleados activos: {count}")
        
        if count > 0:
            result = db.session.execute(text('''
                SELECT name, cargo 
                FROM employees 
                WHERE is_active = true 
                ORDER BY name 
                LIMIT 10
            '''))
            print("   Algunos empleados:")
            for row in result.fetchall():
                print(f"      - {row[0]}: {row[1]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Verificar jornadas
    try:
        result = db.session.execute(text('SELECT COUNT(*) FROM jornadas'))
        count = result.scalar()
        print(f"\n📅 Jornadas: {count}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Verificación completada")

PYEOF

# Detener proxy
echo ""
echo "🛑 Deteniendo Cloud SQL Proxy..."
kill $PROXY_PID 2>/dev/null
echo "✅ Proxy detenido"




