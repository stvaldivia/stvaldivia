# 🌍 Ambientes de Trabajo

## 📋 Resumen

Tenemos **2 ambientes separados** para trabajar de forma segura:

### 🧪 **STAGING** (Desarrollo/Pruebas)
- **Servicio**: `bimba-system-staging`
- **URL**: Se genera automáticamente (ej: `bimba-system-staging-xxx.run.app`)
- **Propósito**: Probar cambios antes de producción
- **Base de datos**: Misma BD (puedes crear una separada si quieres)
- **Estado**: ✅ Listo para usar

### 🌐 **PRODUCCIÓN** (Sitio en Vivo)
- **Servicio**: `bimba-system`
- **URL**: https://stvaldivia.cl
- **Propósito**: Sitio real que usan los clientes
- **Estado**: ✅ Funcionando

## 🚀 Flujo de Trabajo Recomendado

### 1. **Desarrollo en Staging**
```bash
# Hacer cambios en código
# ...

# Deploy a STAGING (pruebas)
./deploy-staging.sh
```

### 2. **Probar en Staging**
- Abrir URL de staging
- Probar todas las funcionalidades
- Verificar que todo funciona

### 3. **Deploy a Producción** (solo cuando esté listo)
```bash
# Si todo está bien en staging:
./deploy-fast.sh
```

## 📝 Comandos

### Deploy a Staging (Pruebas)
```bash
./deploy-staging.sh
```

### Deploy a Producción (Sitio Real)
```bash
./deploy-fast.sh
```

### Ver URLs
```bash
# Staging
gcloud run services describe bimba-system-staging --region us-central1 --format='value(status.url)'

# Producción
gcloud run services describe bimba-system --region us-central1 --format='value(status.url)'
```

## ⚠️ Importante

- **Staging**: Para probar cambios sin riesgo
- **Producción**: Solo deployar cuando esté 100% probado
- **Nunca** trabajar directamente en producción sin probar antes

## 💡 Recomendación

1. **Trabajar en staging** para todos los cambios
2. **Probar bien** antes de pasar a producción
3. **Deploy a producción** solo cuando esté listo

