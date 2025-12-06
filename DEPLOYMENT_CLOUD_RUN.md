# Guía de Deployment a Google Cloud Run
# Sistema BIMBA - Actualización con Sistema de Notificaciones

## 📋 PREREQUISITOS

Antes de comenzar, asegúrate de tener:

1. ✅ Google Cloud SDK instalado (`gcloud`)
2. ✅ Docker instalado (para build local opcional)
3. ✅ Acceso a tu proyecto de Google Cloud
4. ✅ Permisos para desplegar en Cloud Run

## 🚀 OPCIÓN 1: DEPLOYMENT RÁPIDO (Recomendado)

### Paso 1: Verificar que estás autenticado en Google Cloud

```bash
# Verificar autenticación
gcloud auth list

# Si no estás autenticado, ejecutar:
gcloud auth login

# Configurar proyecto (reemplazar con tu PROJECT_ID)
gcloud config set project TU_PROJECT_ID
```

### Paso 2: Hacer commit de los cambios

```bash
cd /Users/sebagatica/tickets

# Ver archivos modificados
git status

# Agregar todos los archivos nuevos
git add .

# Hacer commit
git commit -m "feat: Sistema de notificaciones en tiempo real implementado

- Modelo de notificaciones con persistencia en BD
- Servicio de notificaciones con Socket.IO
- API REST completa para gestión de notificaciones
- Frontend con panel, toasts y sonidos
- Integración en template base
- Documentación y ejemplos de uso"

# Push a tu repositorio
git push origin main
```

### Paso 3: Desplegar a Cloud Run

```bash
# Opción A: Si tienes Cloud Build configurado con GitHub/GitLab
gcloud run deploy bimba-system \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10 \
  --set-env-vars "FLASK_ENV=production,LOCAL_ONLY=false"

# Opción B: Build y deploy en un solo comando
gcloud builds submit --tag gcr.io/TU_PROJECT_ID/bimba-system
gcloud run deploy bimba-system \
  --image gcr.io/TU_PROJECT_ID/bimba-system \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1
```

### Paso 4: Verificar el deployment

```bash
# Ver el servicio desplegado
gcloud run services describe bimba-system --region us-central1

# Obtener la URL del servicio
gcloud run services describe bimba-system --region us-central1 --format='value(status.url)'
```

---

## 🔧 OPCIÓN 2: DEPLOYMENT CON DOCKERFILE (Control Total)

Si prefieres tener control total del build, usa esta opción.

### Paso 1: Crear Dockerfile (ya incluido en esta guía)

Ver archivo `Dockerfile` en la raíz del proyecto.

### Paso 2: Build de la imagen

```bash
cd /Users/sebagatica/tickets

# Build local (opcional, para probar)
docker build -t bimba-system .

# Build en Google Cloud
gcloud builds submit --tag gcr.io/TU_PROJECT_ID/bimba-system
```

### Paso 3: Deploy

```bash
gcloud run deploy bimba-system \
  --image gcr.io/TU_PROJECT_ID/bimba-system \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --set-env-vars "FLASK_ENV=production,LOCAL_ONLY=false"
```

---

## 🔐 CONFIGURAR VARIABLES DE ENTORNO

### Opción A: Desde la consola de Cloud Run

1. Ve a Cloud Run Console: https://console.cloud.google.com/run
2. Selecciona tu servicio `bimba-system`
3. Click en "EDIT & DEPLOY NEW REVISION"
4. En "Variables & Secrets", agrega:
   - `FLASK_SECRET_KEY`: (tu secret key)
   - `ADMIN_PASSWORD`: (tu password de admin)
   - `API_KEY`: (tu API key de PHP POS)
   - `BASE_API_URL`: https://clubbb.phppointofsale.com/index.php/api/v1
   - `FLASK_ENV`: production
   - `LOCAL_ONLY`: false

### Opción B: Desde la línea de comandos

```bash
gcloud run services update bimba-system \
  --region us-central1 \
  --update-env-vars \
    FLASK_SECRET_KEY="tu-secret-key-aqui",\
    ADMIN_PASSWORD="tu-password-aqui",\
    API_KEY="tu-api-key-aqui",\
    BASE_API_URL="https://clubbb.phppointofsale.com/index.php/api/v1",\
    FLASK_ENV="production",\
    LOCAL_ONLY="false"
```

---

## 📊 MIGRACIÓN DE BASE DE DATOS

**IMPORTANTE**: Cloud Run usa almacenamiento efímero. Para persistencia de datos, tienes 2 opciones:

### Opción A: Cloud SQL (Recomendado para Producción)

```bash
# 1. Crear instancia de Cloud SQL
gcloud sql instances create bimba-db \
  --database-version=POSTGRES_14 \
  --tier=db-f1-micro \
  --region=us-central1

# 2. Crear base de datos
gcloud sql databases create bimba --instance=bimba-db

# 3. Conectar Cloud Run con Cloud SQL
gcloud run services update bimba-system \
  --region us-central1 \
  --add-cloudsql-instances TU_PROJECT_ID:us-central1:bimba-db \
  --update-env-vars DATABASE_URL="postgresql://user:password@/bimba?host=/cloudsql/TU_PROJECT_ID:us-central1:bimba-db"
```

### Opción B: SQLite en /tmp (Solo para desarrollo/testing)

La base de datos se creará automáticamente en `/tmp` en Cloud Run, pero **se perderá al reiniciar**.

Para persistencia con SQLite, necesitas:
1. Cloud Storage FUSE
2. Backups programados
3. O migrar a Cloud SQL

---

## 🔄 ACTUALIZAR EL SERVICIO (Deployments Futuros)

Cada vez que hagas cambios:

```bash
cd /Users/sebagatica/tickets

# 1. Commit cambios
git add .
git commit -m "Descripción de cambios"
git push

# 2. Re-desplegar
gcloud run deploy bimba-system \
  --source . \
  --region us-central1
```

---

## 🧪 TESTING POST-DEPLOYMENT

### 1. Verificar que el servicio está corriendo

```bash
# Obtener URL
URL=$(gcloud run services describe bimba-system --region us-central1 --format='value(status.url)')
echo "URL del servicio: $URL"

# Probar health check
curl $URL/api/health
```

### 2. Verificar notificaciones

```bash
# Crear notificación de prueba (requiere estar logueado como admin)
curl -X POST $URL/admin/api/notifications/test \
  -H "Content-Type: application/json" \
  -H "Cookie: session=TU_SESSION_COOKIE" \
  -d '{"type": "info", "title": "Prueba", "message": "Sistema desplegado correctamente"}'
```

### 3. Verificar logs

```bash
# Ver logs en tiempo real
gcloud run services logs tail bimba-system --region us-central1

# Ver logs recientes
gcloud run services logs read bimba-system --region us-central1 --limit 50
```

---

## 🚨 TROUBLESHOOTING

### Error: "Service not found"
```bash
# Verificar que el servicio existe
gcloud run services list --region us-central1
```

### Error: "Permission denied"
```bash
# Verificar permisos
gcloud projects get-iam-policy TU_PROJECT_ID

# Agregar rol necesario
gcloud projects add-iam-policy-binding TU_PROJECT_ID \
  --member="user:tu-email@gmail.com" \
  --role="roles/run.admin"
```

### Error: "Build failed"
```bash
# Ver logs del build
gcloud builds list --limit 5
gcloud builds log BUILD_ID
```

### Base de datos no persiste
- Cloud Run usa almacenamiento efímero
- Migrar a Cloud SQL para persistencia
- O configurar backups automáticos a Cloud Storage

---

## 📦 BACKUP Y RESTORE

### Backup de la base de datos (si usas SQLite)

```bash
# Desde el servidor, crear backup
python3 scripts/backup_db.py

# Descargar backup
gcloud run services proxy bimba-system --region us-central1
# Luego acceder vía SSH o Cloud Shell
```

### Restore

```bash
# Subir backup a Cloud Storage
gsutil cp backup.db gs://tu-bucket/backups/

# Restaurar en Cloud Run (requiere configuración adicional)
```

---

## 🎯 CHECKLIST DE DEPLOYMENT

Antes de desplegar, verifica:

- [ ] Todas las variables de entorno configuradas
- [ ] Secret keys actualizadas (no usar valores de desarrollo)
- [ ] API keys configuradas
- [ ] Base de datos configurada (Cloud SQL o alternativa)
- [ ] Backups configurados
- [ ] Logs monitoreados
- [ ] Health checks funcionando
- [ ] Socket.IO funcionando (verificar WebSocket support)
- [ ] Notificaciones funcionando

---

## 📞 COMANDOS ÚTILES

```bash
# Ver servicios
gcloud run services list

# Ver detalles del servicio
gcloud run services describe bimba-system --region us-central1

# Ver logs
gcloud run services logs tail bimba-system --region us-central1

# Eliminar servicio (¡cuidado!)
gcloud run services delete bimba-system --region us-central1

# Ver revisiones
gcloud run revisions list --service bimba-system --region us-central1

# Rollback a revisión anterior
gcloud run services update-traffic bimba-system \
  --region us-central1 \
  --to-revisions REVISION_NAME=100
```

---

## 🔗 RECURSOS ADICIONALES

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud SQL Documentation](https://cloud.google.com/sql/docs)
- [Cloud Build Documentation](https://cloud.google.com/build/docs)

---

**Última actualización:** 6 de Diciembre de 2025
