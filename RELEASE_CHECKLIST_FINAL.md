# ✅ RELEASE CHECKLIST FINAL - BIMBA v2025-12-12-prod

**Fecha:** 2025-12-12 04:40 UTC  
**Release Engineer:** Auto  
**Estado:** ✅ **READY FOR PRODUCTION**

---

## 📋 CHECKLIST COMPLETADO

### 1. VERIFICACIÓN DE ARRANQUE
- [x] App arranca en modo producción simulado
- [x] No hay tracebacks al boot (solo warnings esperados)
- [x] Validación de env vars funciona:
  - [x] Falta FLASK_SECRET_KEY → aborta ✅
  - [x] Falta DATABASE_URL → aborta ✅
  - [x] Falta OPENAI_API_KEY → app levanta con bot en modo reglas ✅
- [x] Warnings relevantes loggeados correctamente

### 2. SMOKE TEST AUTOMÁTICO
- [x] **APIs públicas:**
  - [x] GET /api/v1/public/evento/hoy → 200 ✅
  - [x] GET /api/v1/public/eventos/proximos → 200 ✅
- [x] **Bot:**
  - [x] POST /api/v1/bot/responder ("qué hay hoy") → 200 ✅
  - [x] POST /api/v1/bot/responder spam (>30 req/5min) → 429 ✅
  - [x] Bot sin OPENAI_API_KEY → respuesta fallback segura ✅
- [x] **Operational API:**
  - [x] GET /api/v1/operational/summary SIN API key → 401 ✅
  - [x] GET /api/v1/operational/summary CON API key → 200 ✅
  - [x] Logging de accesos funciona (sin registrar key) ✅

### 3. VERIFICACIÓN DE RATE LIMITING
- [x] Bot: 30 req / 5 min / IP ✅
- [x] Públicas: 120 req / 5 min / IP ✅
- [x] Respuesta JSON con status 429 ✅

### 4. VERIFICACIÓN DE NORMALIZACIÓN DE FECHAS
- [x] Función `normalize_shift_date()` funciona ✅
- [x] Acepta YYYY-MM-DD, DD/MM/YYYY, YYYY/MM/DD ✅
- [x] Rechaza formatos inválidos con log ✅
- [x] Aplicada en creación de ventas ✅
- [x] Aplicada en creación de jornadas ✅
- [x] Aplicada en creación de inventario ✅

### 5. LOGGING Y SEGURIDAD
- [x] /api/v1/operational/* registra endpoint, IP, status ✅
- [x] NO se loguean API keys ✅
- [x] NO se loguean payloads sensibles ✅
- [x] Rutas admin requieren sesión ✅

### 6. PREPARACIÓN DE RELEASE
- [x] Backup existe: `backup_pre_prod_2025_12_12/` ✅
- [x] Release notes generados ✅
- [x] Tag sugerido: `v2025-12-12-prod` ✅

---

## 🔧 COMANDOS SUGERIDOS

### Git Tag:
```bash
git tag -a v2025-12-12-prod -m "Release producción: Hardening crítico - Rate limiting, fallbacks seguros, normalización fechas"
git push --tags
```

### Arranque en Servidor:
```bash
# Variables de entorno OBLIGATORIAS:
export FLASK_ENV=production
export FLASK_SECRET_KEY=<clave_secreta_fuerte>
export DATABASE_URL=<postgresql://usuario:password@host:puerto/database>

# Variables OPCIONALES (recomendadas):
export BIMBA_INTERNAL_API_BASE_URL=https://tu-dominio.com
export BIMBA_INTERNAL_API_KEY=<clave_api_interna>
export OPENAI_API_KEY=<clave_openai>

# Arrancar aplicación
python3 run_local.py
# O según configuración del servidor:
# gunicorn app:create_app() --bind 0.0.0.0:5001 --workers 2
```

---

## 📝 RECOMENDACIONES POST-DEPLOY (Máx 5)

1. **Monitorear logs las primeras 2 horas** - Verificar que no hay errores inesperados y que el logging funciona correctamente
2. **Probar bot manualmente** - Enviar "qué hay hoy?" y "cómo va la noche?" para confirmar respuestas con `source: rule_based`
3. **Verificar rate limiting** - Confirmar que después de 30 requests al bot se recibe 429
4. **Validar fechas nuevas** - Crear una venta/jornada y confirmar que la fecha está en formato YYYY-MM-DD
5. **Revisar accesos a API operational** - Verificar en logs que se registran correctamente los accesos (endpoint, IP, status)

---

## ⚠️ NOTAS IMPORTANTES

- **Rate limiting en memoria:** Solo funciona para single-process. Si hay múltiples workers, cada uno tiene su contador.
- **OperationalInsightsService:** En producción sin `BIMBA_INTERNAL_API_BASE_URL`, bot funciona pero sin contexto operativo (seguro y esperado).
- **Fechas existentes:** Normalización solo aplica a nuevas escrituras. Fechas mal formateadas existentes pueden causar problemas hasta corregirse.

---

**ESTADO FINAL:** ✅ **READY FOR PRODUCTION**
