#!/bin/bash

# Script para migrar datos usando Cloud SQL Proxy
# Sistema BIMBA

echo "🔐 Configurando Cloud SQL Proxy..."
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
echo "📊 Ahora puedes conectarte a PostgreSQL en localhost:5432"
echo ""
echo "Para detener el proxy después:"
echo "  kill $PROXY_PID"
echo ""
echo "Presiona Enter para continuar con la migración..."
# read

# Ejecutar migración con configuración local
python3 - << 'EOF'
import sqlite3
import psycopg2
import os

# Configuración para conectar via proxy
POSTGRES_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'bimba',
    'user': 'bimba_user',
    'password': 'qbiqpVcv9zJPVB0aaA9YwfAJSzFIGroUBcwJHNhzsas='
}

SQLITE_DB = 'instance/bimba.db'

TABLES = ['employees', 'cargos', 'cargo_salary_configs', 'jornadas', 
          'planilla_trabajadores', 'register_closes', 'api_connection_logs',
          'audit_logs', 'ficha_review_logs', 'notifications']

print("🔄 Iniciando migración de datos...")
print()

# Conectar
sqlite_conn = sqlite3.connect(SQLITE_DB)
postgres_conn = psycopg2.connect(**POSTGRES_CONFIG)

print("✅ Conectado a ambas bases de datos")
print()

# Migrar cada tabla
for table in TABLES:
    print(f"📦 Migrando: {table}...", end=" ")
    
    try:
        # Obtener datos
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute(f"SELECT * FROM {table}")
        data = sqlite_cursor.fetchall()
        
        if not data:
            print("(vacía)")
            continue
        
        # Obtener columnas
        columns = [desc[0] for desc in sqlite_cursor.description]
        
        # Insertar en PostgreSQL
        pg_cursor = postgres_conn.cursor()
        placeholders = ','.join(['%s'] * len(columns))
        columns_str = ','.join(columns)
        query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
        
        inserted = 0
        for row in data:
            try:
                pg_cursor.execute(query, row)
                inserted += 1
            except:
                pass
        
        postgres_conn.commit()
        print(f"✅ {inserted}/{len(data)} registros")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        postgres_conn.rollback()

sqlite_conn.close()
postgres_conn.close()

print()
print("🎉 ¡Migración completada!")
EOF

# Detener proxy
echo ""
echo "🛑 Deteniendo Cloud SQL Proxy..."
kill $PROXY_PID
echo "✅ Proxy detenido"
