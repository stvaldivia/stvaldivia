#!/bin/bash

# Script para ejecutar migraciones de recetas en la base de datos de PRODUCCIÓN
# Usa Cloud SQL Proxy para conectar

echo "🔐 Configurando Cloud SQL Proxy..."

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
echo "🌍 Conectando a Base de Datos de Producción..."

# Configurar URL de base de datos para que la app use Postgres local (proxy)
export DATABASE_URL="postgresql://bimba_user:qbiqpVcv9zJPVB0aaA9YwfAJSzFIGroUBcwJHNhzsas=@localhost:5432/bimba"
export FLASK_ENV=production

echo ""
echo "📦 1. Migrando Productos desde Excel..."
python3 migrate_excel_products.py

echo ""
echo "📦 2. Migrando Ingredientes y Recetas Base..."
python3 migrate_recipes.py

echo ""
echo "📦 3. Configurando Recetas de Gin..."
python3 configure_gin_recipes.py

# Detener proxy
echo ""
echo "🛑 Deteniendo Cloud SQL Proxy..."
kill $PROXY_PID
echo "✅ Proxy detenido"
echo "🎉 ¡Migración a Producción completada!"
