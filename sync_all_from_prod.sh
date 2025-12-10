#!/bin/bash

# Script completo para sincronizar TODOS los datos desde producción a local
# Sistema BIMBA - Sincronización de Base de Datos

echo "🔄 Sincronización completa desde Producción a Local"
echo "=================================================="
echo ""

# Descargar Cloud SQL Proxy si no existe
if [ ! -f "cloud-sql-proxy" ]; then
    echo "📥 Descargando Cloud SQL Proxy..."
    curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.darwin.amd64
    chmod +x cloud-sql-proxy
    echo "✅ Cloud SQL Proxy descargado"
fi

# Verificar si el proxy ya está corriendo
if pgrep -f "cloud-sql-proxy" > /dev/null; then
    echo "⚠️  Cloud SQL Proxy ya está ejecutándose"
    echo "   Usando proxy existente..."
    PROXY_PID=""
else
    # Iniciar proxy en background
    echo "🚀 Iniciando Cloud SQL Proxy..."
    ./cloud-sql-proxy pelagic-river-479014-a3:us-central1:bimba-db &
    PROXY_PID=$!
    
    echo "⏳ Esperando que el proxy esté listo..."
    sleep 5
    echo "✅ Proxy iniciado (PID: $PROXY_PID)"
fi

echo ""
echo "🌍 Conectando a Base de Datos de Producción..."
echo ""

# Configurar URL de base de datos
export DATABASE_URL="postgresql://bimba_user:qbiqpVcv9zJPVB0aaA9YwfAJSzFIGroUBcwJHNhzsas=@localhost:5432/bimba"
export FLASK_ENV=production

# Ejecutar script de sincronización completo
python3 sync_all_data_from_prod.py

# Detener proxy solo si lo iniciamos nosotros
if [ ! -z "$PROXY_PID" ]; then
    echo ""
    echo "🛑 Deteniendo Cloud SQL Proxy..."
    kill $PROXY_PID 2>/dev/null
    echo "✅ Proxy detenido"
fi

echo ""
echo "✅ Sincronización completada"
echo ""
echo "💡 Para mantener los datos actualizados, ejecuta este script regularmente:"
echo "   ./sync_all_from_prod.sh"




