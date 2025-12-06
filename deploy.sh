#!/bin/bash

# Script de Deployment Automatizado para Google Cloud Run
# Sistema BIMBA

set -e  # Salir si hay algún error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuración
PROJECT_ID="${GCLOUD_PROJECT_ID:-tu-project-id}"
SERVICE_NAME="bimba-system"
REGION="us-central1"
MEMORY="512Mi"
CPU="1"
MAX_INSTANCES="10"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Deployment de Sistema BIMBA${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Verificar que gcloud está instalado
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ Error: gcloud CLI no está instalado${NC}"
    echo "Instala desde: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

echo -e "${GREEN}✓${NC} gcloud CLI encontrado"

# Verificar autenticación
echo -e "${YELLOW}Verificando autenticación...${NC}"
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo -e "${RED}❌ No estás autenticado en Google Cloud${NC}"
    echo "Ejecuta: gcloud auth login"
    exit 1
fi

ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
echo -e "${GREEN}✓${NC} Autenticado como: ${ACTIVE_ACCOUNT}"

# Verificar/configurar proyecto
echo -e "${YELLOW}Configurando proyecto...${NC}"
if [ "$PROJECT_ID" == "tu-project-id" ]; then
    echo -e "${YELLOW}⚠️  PROJECT_ID no configurado${NC}"
    echo "Proyectos disponibles:"
    gcloud projects list --format="table(projectId,name)"
    echo ""
    read -p "Ingresa el PROJECT_ID: " PROJECT_ID
fi

gcloud config set project "$PROJECT_ID"
echo -e "${GREEN}✓${NC} Proyecto configurado: ${PROJECT_ID}"

# Verificar que estamos en el directorio correcto
if [ ! -f "run_local.py" ]; then
    echo -e "${RED}❌ Error: No se encontró run_local.py${NC}"
    echo "Ejecuta este script desde el directorio raíz del proyecto"
    exit 1
fi

echo -e "${GREEN}✓${NC} Directorio correcto"

# Preguntar si hacer commit
echo ""
echo -e "${YELLOW}¿Deseas hacer commit de los cambios antes de desplegar? (y/n)${NC}"
read -p "> " DO_COMMIT

if [ "$DO_COMMIT" == "y" ] || [ "$DO_COMMIT" == "Y" ]; then
    echo -e "${YELLOW}Haciendo commit...${NC}"
    git add .
    read -p "Mensaje de commit: " COMMIT_MSG
    git commit -m "$COMMIT_MSG" || echo "No hay cambios para commitear"
    
    echo -e "${YELLOW}¿Deseas hacer push? (y/n)${NC}"
    read -p "> " DO_PUSH
    if [ "$DO_PUSH" == "y" ] || [ "$DO_PUSH" == "Y" ]; then
        git push
        echo -e "${GREEN}✓${NC} Push completado"
    fi
fi

# Seleccionar método de deployment
echo ""
echo -e "${BLUE}Selecciona método de deployment:${NC}"
echo "1) Deployment desde código fuente (recomendado)"
echo "2) Build con Docker y deployment"
read -p "Opción (1 o 2): " DEPLOY_METHOD

if [ "$DEPLOY_METHOD" == "1" ]; then
    # Deployment desde código fuente
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Desplegando desde código fuente${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    gcloud run deploy "$SERVICE_NAME" \
        --source . \
        --region "$REGION" \
        --allow-unauthenticated \
        --memory "$MEMORY" \
        --cpu "$CPU" \
        --timeout 300 \
        --max-instances "$MAX_INSTANCES" \
        --set-env-vars "FLASK_ENV=production,LOCAL_ONLY=false"
    
elif [ "$DEPLOY_METHOD" == "2" ]; then
    # Build con Docker
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Building imagen Docker${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"
    
    echo -e "${YELLOW}Building imagen: ${IMAGE_NAME}${NC}"
    gcloud builds submit --tag "$IMAGE_NAME"
    
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Desplegando a Cloud Run${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    gcloud run deploy "$SERVICE_NAME" \
        --image "$IMAGE_NAME" \
        --region "$REGION" \
        --platform managed \
        --allow-unauthenticated \
        --memory "$MEMORY" \
        --cpu "$CPU" \
        --timeout 300 \
        --max-instances "$MAX_INSTANCES" \
        --set-env-vars "FLASK_ENV=production,LOCAL_ONLY=false"
else
    echo -e "${RED}❌ Opción inválida${NC}"
    exit 1
fi

# Obtener URL del servicio
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Deployment Completado${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format='value(status.url)')

echo -e "${GREEN}✅ Servicio desplegado exitosamente!${NC}"
echo ""
echo -e "${BLUE}URL del servicio:${NC} ${GREEN}$SERVICE_URL${NC}"
echo ""
echo -e "${YELLOW}Próximos pasos:${NC}"
echo "1. Configurar variables de entorno (API keys, passwords)"
echo "2. Configurar base de datos (Cloud SQL recomendado)"
echo "3. Verificar que Socket.IO funciona correctamente"
echo "4. Probar sistema de notificaciones"
echo ""
echo -e "${BLUE}Comandos útiles:${NC}"
echo "  Ver logs:    gcloud run services logs tail $SERVICE_NAME --region $REGION"
echo "  Ver detalles: gcloud run services describe $SERVICE_NAME --region $REGION"
echo "  Actualizar:   ./deploy.sh"
echo ""

# Preguntar si abrir en navegador
echo -e "${YELLOW}¿Deseas abrir el servicio en el navegador? (y/n)${NC}"
read -p "> " OPEN_BROWSER

if [ "$OPEN_BROWSER" == "y" ] || [ "$OPEN_BROWSER" == "Y" ]; then
    if command -v open &> /dev/null; then
        open "$SERVICE_URL"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "$SERVICE_URL"
    else
        echo "Abre manualmente: $SERVICE_URL"
    fi
fi

echo ""
echo -e "${GREEN}🎉 Deployment completado!${NC}"
