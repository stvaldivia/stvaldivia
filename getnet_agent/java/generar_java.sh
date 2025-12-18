#!/bin/bash
# Script rápido para generar GetnetAgent.java con valores por defecto
set -e

echo "=== Generando GetnetAgent.java ==="
echo ""

# Variables por defecto (el usuario las puede cambiar después en Windows)
export BASE_URL="${BASE_URL:-https://stvaldivia.cl}"
export REGISTER_ID="${REGISTER_ID:-1}"
export AGENT_API_KEY="${AGENT_API_KEY:-REEMPLAZAR_CON_API_KEY_REAL}"
export AGENT_ID="${AGENT_ID:-java-agent-windows}"

echo "Usando configuración:"
echo "  BASE_URL=$BASE_URL"
echo "  REGISTER_ID=$REGISTER_ID"
echo "  AGENT_API_KEY=${AGENT_API_KEY:0:20}..."
echo "  AGENT_ID=$AGENT_ID"
echo ""
echo "⚠️  IMPORTANTE: Si AGENT_API_KEY no es correcta,"
echo "   debes cambiarla después en Windows usando CONFIGURAR_VARIABLES.bat"
echo ""

# Ejecutar el script setup para generar GetnetAgent.java
bash setup_getnet_agent_java.sh

echo ""
echo "✅ GetnetAgent.java generado correctamente"
echo ""
echo "Próximos pasos:"
echo "1. Copia GetnetAgent.java y los archivos .bat a Windows"
echo "2. En Windows, ejecuta: INSTALAR_Y_EJECUTAR.bat"
echo "3. O configura las variables: CONFIGURAR_VARIABLES.bat"
