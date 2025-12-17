#!/bin/bash
# Script para deploy en VM de Google Compute Engine
# Uso: ./deploy_vm.sh [INSTANCE_NAME] [ZONE] [PROJECT_ID]

set -e

# Configuración por defecto (ajustar según tu VM)
INSTANCE_NAME="${1:-bimba-vm}"
ZONE="${2:-southamerica-west1-a}"
PROJECT_ID="${3:-stvaldiviacl}"

echo "🚀 DEPLOY A VM DE GOOGLE COMPUTE ENGINE"
echo "========================================"
echo ""
echo "📋 Configuración:"
echo "  Instancia: $INSTANCE_NAME"
echo "  Zona: $ZONE"
echo "  Proyecto: $PROJECT_ID"
echo ""

# Verificar autenticación
echo "🔐 Verificando autenticación..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ ERROR: No hay cuenta autenticada"
    echo "Ejecuta primero: gcloud auth login"
    exit 1
fi

ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1)
echo "✅ Autenticado como: $ACTIVE_ACCOUNT"
echo ""

# Configurar proyecto
echo "⚙️  Configurando proyecto..."
gcloud config set project $PROJECT_ID
echo ""

# Verificar que la instancia existe
echo "🔍 Verificando instancia..."
if ! gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID &>/dev/null; then
    echo "❌ ERROR: Instancia $INSTANCE_NAME no encontrada en zona $ZONE"
    echo "Lista de instancias disponibles:"
    gcloud compute instances list --project=$PROJECT_ID
    exit 1
fi

echo "✅ Instancia encontrada"
echo ""

# Obtener IP externa de la instancia
EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --format="get(networkInterfaces[0].accessConfigs[0].natIP)")
echo "📍 IP externa: $EXTERNAL_IP"
echo ""

# Conectar por SSH y ejecutar comandos de deploy
echo "📦 Desplegando código en la VM..."
echo ""

gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command="
    set -e
    echo '🔄 Actualizando código...'
    
    # Navegar al directorio del proyecto (ajustar según tu estructura)
    cd ~/tickets_cursor_clean || cd ~/tickets || cd ~/app || { echo '❌ Directorio del proyecto no encontrado'; exit 1; }
    
    # Hacer pull del código (si usas git)
    if [ -d .git ]; then
        echo '📥 Haciendo pull del repositorio...'
        git pull origin main || git pull origin master || echo '⚠️  No se pudo hacer pull (continuando...)'
    fi
    
    # Activar entorno virtual si existe
    if [ -d venv ]; then
        echo '🐍 Activando entorno virtual...'
        source venv/bin/activate
    fi
    
    # Instalar/actualizar dependencias
    if [ -f requirements.txt ]; then
        echo '📦 Instalando dependencias...'
        pip install -q -r requirements.txt || echo '⚠️  Algunas dependencias no se pudieron instalar'
    fi
    
    # Reiniciar servicio (ajustar según tu sistema de servicio)
    echo '🔄 Reiniciando servicio...'
    
    # Opción 1: Si usas systemd
    if systemctl is-active --quiet bimba.service 2>/dev/null; then
        sudo systemctl restart bimba.service
        echo '✅ Servicio systemd reiniciado'
    # Opción 2: Si usas supervisor
    elif command -v supervisorctl &>/dev/null && supervisorctl status bimba &>/dev/null; then
        sudo supervisorctl restart bimba
        echo '✅ Servicio supervisor reiniciado'
    # Opción 3: Si usas PM2
    elif command -v pm2 &>/dev/null; then
        pm2 restart bimba || pm2 restart all
        echo '✅ Servicio PM2 reiniciado'
    # Opción 4: Si el proceso está en un screen/tmux
    elif screen -list | grep -q bimba; then
        screen -S bimba -X stuff '^C'
        sleep 2
        screen -S bimba -X stuff 'python3 run_local.py\n'
        echo '✅ Proceso en screen reiniciado'
    else
        echo '⚠️  No se encontró servicio configurado. Reinicia manualmente.'
        echo '   Busca el proceso con: ps aux | grep python'
    fi
    
    echo ''
    echo '✅ Deploy completado'
    echo '📍 Verifica el servicio en: http://'$EXTERNAL_IP':5001'
"

echo ""
echo "✅ DEPLOY COMPLETADO"
echo ""
echo "📍 URL del servicio:"
echo "   http://$EXTERNAL_IP:5001"
echo ""
echo "🔍 Para ver logs:"
echo "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID"
echo ""








