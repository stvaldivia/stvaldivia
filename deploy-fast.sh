#!/bin/bash
# Deployment rápido a PRODUCCIÓN (stvaldivia.cl)
# ⚠️  ESTO AFECTA PRODUCCIÓN - Solo usar cuando esté listo
set -e

PROJECT_ID="pelagic-river-479014-a3"
SERVICE_NAME="bimba-system"  # PRODUCCIÓN
REGION="us-central1"

echo "🚀 Deployment a PRODUCCIÓN (stvaldivia.cl)"
echo "⚠️  ESTO AFECTA EL SITIO EN VIVO"
echo ""
read -p "¿Estás seguro? (escribe 'si' para continuar): " confirm
if [ "$confirm" != "si" ]; then
    echo "❌ Deployment cancelado"
    exit 1
fi

echo "🚀 Desplegando a producción..."

gcloud config set project "$PROJECT_ID" --quiet

gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300 \
    --max-instances 10 \
    --add-cloudsql-instances "pelagic-river-479014-a3:us-central1:bimba-db" \
    --set-env-vars "FLASK_ENV=production,LOCAL_ONLY=false,DATABASE_URL=postgresql+psycopg2://bimba_user:qbiqpVcv9zJPVB0aaA9YwfAJSzFIGroUBcwJHNhzsas=@/bimba?host=/cloudsql/pelagic-river-479014-a3:us-central1:bimba-db" \
    --quiet

echo "✅ Deployment completado!"
echo "URL: https://bimba-system-1097791890106.us-central1.run.app"

