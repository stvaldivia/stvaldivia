#!/bin/bash

# Script para migrar de SQLite local a Cloud SQL en Google Cloud
# Sistema BIMBA

set -e

echo "🚀 Migración a Cloud SQL"
echo "========================"
echo ""

PROJECT_ID="pelagic-river-479014-a3"
REGION="us-central1"
INSTANCE_NAME="bimba-db"
DB_NAME="bimba"
DB_USER="bimba_user"
DB_PASSWORD=$(openssl rand -base64 32)

echo "📋 Configuración:"
echo "  Proyecto: $PROJECT_ID"
echo "  Región: $REGION"
echo "  Instancia: $INSTANCE_NAME"
echo "  Base de datos: $DB_NAME"
echo ""

# Paso 1: Habilitar API de Cloud SQL
echo "1️⃣ Habilitando Cloud SQL API..."
gcloud services enable sqladmin.googleapis.com --project=$PROJECT_ID
echo "✅ API habilitada"
echo ""

# Paso 2: Crear instancia de Cloud SQL
echo "2️⃣ Creando instancia de Cloud SQL (esto toma ~5 minutos)..."
gcloud sql instances create $INSTANCE_NAME \
  --database-version=POSTGRES_14 \
  --tier=db-f1-micro \
  --region=$REGION \
  --project=$PROJECT_ID \
  --root-password="$DB_PASSWORD" \
  --storage-type=SSD \
  --storage-size=10GB \
  --backup \
  --backup-start-time=03:00

echo "✅ Instancia creada"
echo ""

# Paso 3: Crear base de datos
echo "3️⃣ Creando base de datos..."
gcloud sql databases create $DB_NAME \
  --instance=$INSTANCE_NAME \
  --project=$PROJECT_ID

echo "✅ Base de datos creada"
echo ""

# Paso 4: Crear usuario
echo "4️⃣ Creando usuario..."
gcloud sql users create $DB_USER \
  --instance=$INSTANCE_NAME \
  --password="$DB_PASSWORD" \
  --project=$PROJECT_ID

echo "✅ Usuario creado"
echo ""

# Paso 5: Obtener connection name
CONNECTION_NAME=$(gcloud sql instances describe $INSTANCE_NAME \
  --project=$PROJECT_ID \
  --format='value(connectionName)')

echo "📝 Información de conexión:"
echo "  Connection Name: $CONNECTION_NAME"
echo "  Usuario: $DB_USER"
echo "  Password: $DB_PASSWORD"
echo ""
echo "⚠️  GUARDA ESTA INFORMACIÓN EN UN LUGAR SEGURO"
echo ""

# Guardar credenciales en archivo (para uso posterior)
cat > cloud_sql_credentials.txt << EOF
Cloud SQL Credentials
=====================
Connection Name: $CONNECTION_NAME
Database: $DB_NAME
User: $DB_USER
Password: $DB_PASSWORD

DATABASE_URL: postgresql://$DB_USER:$DB_PASSWORD@/$DB_NAME?host=/cloudsql/$CONNECTION_NAME
EOF

echo "✅ Credenciales guardadas en: cloud_sql_credentials.txt"
echo ""

# Paso 6: Actualizar Cloud Run para usar Cloud SQL
echo "5️⃣ Conectando Cloud Run con Cloud SQL..."
gcloud run services update bimba-pos \
  --region=$REGION \
  --add-cloudsql-instances=$CONNECTION_NAME \
  --update-env-vars="DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@/$DB_NAME?host=/cloudsql/$CONNECTION_NAME" \
  --project=$PROJECT_ID

echo "✅ Cloud Run actualizado"
echo ""

echo "🎉 ¡Migración completada!"
echo ""
echo "📋 Próximos pasos:"
echo "1. Instalar dependencias para PostgreSQL:"
echo "   pip install psycopg2-binary"
echo ""
echo "2. Migrar datos de SQLite a PostgreSQL:"
echo "   python3 migrate_data.py"
echo ""
echo "3. Re-desplegar la aplicación:"
echo "   gcloud run deploy bimba-pos --source . --region us-central1"
echo ""
