#!/bin/bash
# Script para conectarse a la VM de Google Cloud

set -e

export PATH="$HOME/google-cloud-sdk/bin:$PATH"

INSTANCE_NAME="stvaldivia"
ZONE="southamerica-west1-a"
PROJECT_ID="stvaldivia"

echo "🔐 CONECTARSE A LA VM"
echo "===================="
echo ""

# Verificar si gcloud está autenticado
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | grep -q .; then
    echo "⚠️  No hay cuenta autenticada en gcloud"
    echo ""
    echo "📋 Para autenticarte, ejecuta:"
    echo "   gcloud auth login"
    echo ""
    echo "Luego ejecuta este script de nuevo."
    exit 1
fi

echo "✅ gcloud autenticado"
echo ""

# Configurar proyecto
echo "⚙️  Configurando proyecto..."
gcloud config set project "$PROJECT_ID" > /dev/null 2>&1
echo "✅ Proyecto configurado: $PROJECT_ID"
echo ""

# Obtener IP de la instancia
echo "🔍 Obteniendo IP de la instancia..."
EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --format="get(networkInterfaces[0].accessConfigs[0].natIP)" 2>/dev/null)

if [ -z "$EXTERNAL_IP" ]; then
    echo "❌ No se pudo obtener la IP de la instancia"
    exit 1
fi

echo "✅ IP encontrada: $EXTERNAL_IP"
echo ""

# Conectarse
echo "🚀 Conectándose a la VM..."
echo "   Instancia: $INSTANCE_NAME"
echo "   Zona: $ZONE"
echo "   IP: $EXTERNAL_IP"
echo ""

# Si se pasa un comando como argumento, ejecutarlo
if [ $# -gt 0 ]; then
    echo "📝 Ejecutando comando: $@"
    echo ""
    gcloud compute ssh "$INSTANCE_NAME" \
        --zone="$ZONE" \
        --project="$PROJECT_ID" \
        --command="$@"
else
    echo "💡 Para ejecutar un comando remoto, pásalo como argumento:"
    echo "   ./conectar_vm.sh 'ls -la'"
    echo ""
    echo "🔌 Iniciando sesión SSH interactiva..."
    echo ""
    gcloud compute ssh "$INSTANCE_NAME" \
        --zone="$ZONE" \
        --project="$PROJECT_ID"
fi
