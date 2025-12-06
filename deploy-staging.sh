#!/bin/bash
# Deployment a STAGING (ambiente de pruebas)
# NO afecta producción (stvaldivia.cl)

set -e

PROJECT_ID="pelagic-river-479014-a3"
SERVICE_NAME="bimba-system-staging"  # Servicio separado para staging
REGION="us-central1"

echo "🧪 Deployment a STAGING (ambiente de pruebas)"
echo "⚠️  NO afecta producción (bimba-system)"
echo ""

gcloud config set project "$PROJECT_ID" --quiet

gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300 \
    --max-instances 5 \
    --add-cloudsql-instances "pelagic-river-479014-a3:us-central1:bimba-db" \
    --set-env-vars "FLASK_ENV=staging,LOCAL_ONLY=false,DATABASE_URL=postgresql+psycopg2://bimba_user:qbiqpVcv9zJPVB0aaA9YwfAJSzFIGroUBcwJHNhzsas=@/bimba?host=/cloudsql/pelagic-river-479014-a3:us-central1:bimba-db" \
    --quiet

STAGING_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format='value(status.url)')

echo ""
echo "✅ Staging desplegado!"
echo "🧪 URL Staging: $STAGING_URL"
echo "🌐 URL Producción: https://stvaldivia.cl (NO afectada)"
echo ""
echo "💡 Usa staging para probar cambios antes de producción"

