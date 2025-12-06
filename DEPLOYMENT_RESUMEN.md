# 🚀 RESUMEN: Deployment a Cloud Run

## ✅ Archivos Creados para Deployment

1. **`Dockerfile`** - Imagen Docker optimizada para Cloud Run
2. **`.dockerignore`** - Optimización del build
3. **`deploy.sh`** - Script automatizado de deployment
4. **`DEPLOYMENT_CLOUD_RUN.md`** - Guía completa de deployment

---

## 🎯 OPCIÓN RÁPIDA: Usar el Script Automatizado

```bash
cd /Users/sebagatica/tickets
./deploy.sh
```

El script te guiará paso a paso:
1. ✅ Verifica autenticación en Google Cloud
2. ✅ Configura el proyecto
3. ✅ Opcionalmente hace commit y push
4. ✅ Te permite elegir método de deployment
5. ✅ Despliega el servicio
6. ✅ Te muestra la URL final

---

## 📋 PASOS MANUALES (Si prefieres control total)

### 1. Autenticarse en Google Cloud

```bash
gcloud auth login
gcloud config set project TU_PROJECT_ID
```

### 2. Hacer commit de los cambios

```bash
cd /Users/sebagatica/tickets
git add .
git commit -m "feat: Sistema de notificaciones en tiempo real"
git push
```

### 3. Desplegar a Cloud Run

**Opción A: Desde código fuente (más simple)**
```bash
gcloud run deploy bimba-system \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --set-env-vars "FLASK_ENV=production,LOCAL_ONLY=false"
```

**Opción B: Con Docker (más control)**
```bash
# Build
gcloud builds submit --tag gcr.io/TU_PROJECT_ID/bimba-system

# Deploy
gcloud run deploy bimba-system \
  --image gcr.io/TU_PROJECT_ID/bimba-system \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1
```

### 4. Configurar Variables de Entorno

```bash
gcloud run services update bimba-system \
  --region us-central1 \
  --update-env-vars \
    FLASK_SECRET_KEY="tu-secret-key",\
    ADMIN_PASSWORD="tu-password",\
    API_KEY="tu-api-key",\
    BASE_API_URL="https://clubbb.phppointofsale.com/index.php/api/v1",\
    FLASK_ENV="production",\
    LOCAL_ONLY="false"
```

O desde la consola web: https://console.cloud.google.com/run

---

## ⚠️ IMPORTANTE: Base de Datos

Cloud Run usa almacenamiento **efímero**. Para persistencia:

### Opción 1: Cloud SQL (Recomendado)

```bash
# Crear instancia
gcloud sql instances create bimba-db \
  --database-version=POSTGRES_14 \
  --tier=db-f1-micro \
  --region=us-central1

# Crear base de datos
gcloud sql databases create bimba --instance=bimba-db

# Conectar con Cloud Run
gcloud run services update bimba-system \
  --region us-central1 \
  --add-cloudsql-instances TU_PROJECT_ID:us-central1:bimba-db
```

### Opción 2: SQLite en /tmp (Solo desarrollo)

La BD se creará automáticamente pero **se perderá al reiniciar**.

---

## 🧪 Verificar Deployment

```bash
# Obtener URL
gcloud run services describe bimba-system \
  --region us-central1 \
  --format='value(status.url)'

# Ver logs
gcloud run services logs tail bimba-system --region us-central1

# Probar health check
curl https://tu-servicio.run.app/api/health
```

---

## 📊 Verificar Sistema de Notificaciones

Una vez desplegado:

1. **Accede a la URL** del servicio
2. **Inicia sesión como admin**
3. **Verás la campana de notificaciones** en el header
4. **Prueba crear una notificación**:

```bash
curl -X POST https://tu-servicio.run.app/admin/api/notifications/test \
  -H "Content-Type: application/json" \
  -d '{"type": "success", "title": "Deployment Exitoso", "message": "Sistema desplegado en Cloud Run"}'
```

---

## 🔧 Comandos Útiles

```bash
# Ver servicios
gcloud run services list

# Ver logs en tiempo real
gcloud run services logs tail bimba-system --region us-central1

# Ver detalles del servicio
gcloud run services describe bimba-system --region us-central1

# Actualizar servicio
./deploy.sh

# Rollback a versión anterior
gcloud run revisions list --service bimba-system --region us-central1
gcloud run services update-traffic bimba-system \
  --to-revisions REVISION_NAME=100
```

---

## ✅ Checklist Pre-Deployment

- [ ] Código commiteado y pusheado
- [ ] Variables de entorno configuradas
- [ ] Secret keys actualizadas (no usar dev keys)
- [ ] Base de datos configurada
- [ ] Dockerfile verificado
- [ ] .dockerignore configurado
- [ ] Script de deployment ejecutable

---

## 🎉 ¡Listo para Desplegar!

Ejecuta:

```bash
cd /Users/sebagatica/tickets
./deploy.sh
```

O sigue los pasos manuales en `DEPLOYMENT_CLOUD_RUN.md`

---

## 📞 Soporte

Si tienes problemas:

1. Revisa los logs: `gcloud run services logs tail bimba-system --region us-central1`
2. Verifica variables de entorno en Cloud Console
3. Consulta `DEPLOYMENT_CLOUD_RUN.md` para troubleshooting

---

**¿Listo para desplegar?** 🚀
