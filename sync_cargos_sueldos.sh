#!/bin/bash

# Script para sincronizar cargos y sueldos desde producción
# Inicia el proxy automáticamente si no está corriendo

echo "🔄 Sincronización de Cargos y Sueldos desde Producción"
echo "======================================================"
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
    echo "✅ Cloud SQL Proxy ya está ejecutándose"
    PROXY_PID=""
else
    # Iniciar proxy en background
    echo "🚀 Iniciando Cloud SQL Proxy..."
    ./cloud-sql-proxy pelagic-river-479014-a3:us-central1:bimba-db > proxy_log.txt 2>&1 &
    PROXY_PID=$!
    
    echo "⏳ Esperando que el proxy esté listo..."
    sleep 5
    
    # Verificar que el proxy esté funcionando
    if pgrep -f "cloud-sql-proxy" > /dev/null; then
        echo "✅ Proxy iniciado (PID: $PROXY_PID)"
    else
        echo "❌ Error: No se pudo iniciar el proxy"
        exit 1
    fi
fi

echo ""
echo "🌍 Sincronizando datos..."
echo ""

# Ejecutar script de sincronización
python3 sync_cargos_sueldos_from_prod.py

SYNC_EXIT_CODE=$?

# Detener proxy solo si lo iniciamos nosotros
if [ ! -z "$PROXY_PID" ]; then
    echo ""
    echo "🛑 Deteniendo Cloud SQL Proxy..."
    kill $PROXY_PID 2>/dev/null
    wait $PROXY_PID 2>/dev/null
    echo "✅ Proxy detenido"
fi

if [ $SYNC_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Sincronización completada exitosamente"
    echo ""
    echo "💡 Los datos de cargos y sueldos ahora están sincronizados con producción"
else
    echo ""
    echo "❌ Error durante la sincronización"
    exit 1
fi




