#!/bin/bash
# Script para ejecutar el Agente Getnet Linux

# Obtener el directorio del script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activar entorno virtual si existe
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Cargar variables de entorno si existe .env
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Ejecutar el servidor FastAPI
echo "Iniciando Agente Getnet Linux..."
echo "Modo demo: ${GETNET_DEMO:-false}"
echo "Puerto serie: ${GETNET_SERIAL_PORT:-/dev/ttyUSB0}"
echo "Escuchando en: http://127.0.0.1:7777"
echo ""

python -m uvicorn app.main:app --host 127.0.0.1 --port 7777


