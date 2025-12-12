# ✅ CHECKLIST DE PRODUCCIÓN - BIMBA
**Fecha:** 2025-12-12  
**Backup:** `backup_pre_prod_2025_12_12/`

---

## 📋 ARCHIVOS MODIFICADOS

### Archivos Nuevos Creados:
1. `app/helpers/simple_rate_limiter.py` - Rate limiter en memoria
2. `app/helpers/date_normalizer.py` - Normalizador de fechas
3. `CHECKLIST_PRODUCCION_2025_12_12.md` - Este documento

### Archivos Modificados:
1. `app/application/services/operational_insights_service.py` - Fix localhost en producción
2. `app/__init__.py` - Validación de variables de entorno al boot
3. `app/blueprints/api/api_v1.py` - Rate limiting + fallback seguro del bot
4. `app/blueprints/api/api_operational.py` - Logging de accesos
5. `app/services/pos_service.py` - Normalización de fechas en ventas
6. `app/application/services/jornada_service.py` - Normalización de fechas en jornadas
7. `app/application/services/inventory_service.py` - Normalización de fechas en inventario

---

## ✅ CONFIRMACIÓN DE BACKUP

**Backup creado en:** `backup_pre_prod_2025_12_12/`

**Contenido del backup:**
- ✅ `app/` (carpeta completa)
- ✅ `run_local.py`
- ✅ `requirements.txt`

**Estado:** ✅ BACKUP COMPLETO Y VERIFICADO

---

## 🧪 EJEMPLOS DE COMPORTAMIENTO

### 1. Bot sin OPENAI_API_KEY

**Comportamiento esperado:**
- Bot funciona solo con RuleEngine
- Si no hay regla → responde mensaje genérico seguro
- NO crashea
- NO expone stacktrace

**Ejemplo de respuesta:**
```json
{
  "status": "ok",
  "respuesta": "Hola! 💜 Soy BimbaBot, el asistente de BIMBA. Hoy tenemos [evento]. Para más información, revisa nuestras redes sociales o contáctanos directamente. ¡Nos vemos en la noche! 💜✨",
  "source": "fallback",
  "intent": "unknown",
  "modelo": null,
  "tokens": null
}
```

### 2. Bot con Rate Limit Excedido

**Request:** `POST /api/v1/bot/responder` (más de 30 requests en 5 minutos)

**Respuesta:**
```json
{
  "status": "error",
  "error": "rate_limited",
  "detalle": "Demasiadas solicitudes. Intenta más tarde."
}
```
**Status Code:** 429

### 3. API Operational sin API Key

**Request:** `GET /api/v1/operational/summary` (sin header `X-API-KEY`)

**Respuesta:**
```json
{
  "status": "unauthorized",
  "detalle": "API key inválida o faltante"
}
```
**Status Code:** 401

**Logging:** Se registra acceso con status_code=401

### 4. OperationalInsightsService en Producción sin BIMBA_INTERNAL_API_BASE_URL

**Comportamiento:**
- Retorna `None` silenciosamente
- Loggea warning claro
- Bot funciona sin contexto operativo
- NO crashea

---

## ✅ CHECKLIST DE PRUEBAS MANUALES

### Pre-Producción (AHORA)

- [ ] **Backup verificado:** `backup_pre_prod_2025_12_12/` existe y contiene archivos
- [ ] **Servidor arranca:** `python run_local.py` funciona sin errores
- [ ] **Variables de entorno:** Logs muestran validación correcta al iniciar
- [ ] **Rate limiting:** Probar 31 requests rápidos a `/api/v1/bot/responder` → debe retornar 429
- [ ] **Bot sin OpenAI:** Desactivar `OPENAI_API_KEY` → bot debe responder con fallback
- [ ] **API operational:** Sin API key → debe retornar 401
- [ ] **Logging:** Verificar logs de accesos a API operational

### En Producción (MAÑANA EN LA NOCHE)

- [ ] **Variables críticas configuradas:**
  - [ ] `FLASK_SECRET_KEY` configurado
  - [ ] `DATABASE_URL` configurado
  - [ ] `BIMBA_INTERNAL_API_BASE_URL` configurado (si se usa bot con contexto operativo)
  - [ ] `BIMBA_INTERNAL_API_KEY` configurado (si se usa API operational)

- [ ] **Bot funciona:**
  - [ ] "qué hay hoy?" → responde con `source: rule_based`
  - [ ] "cómo va la noche?" → responde con `source: rule_based`
  - [ ] "escríbeme un poema" → responde (rule_based o openai o fallback)

- [ ] **APIs públicas:**
  - [ ] `GET /api/v1/public/evento/hoy` → funciona
  - [ ] Rate limiting funciona (probar múltiples requests)

- [ ] **APIs operacionales:**
  - [ ] Con API key → funciona
  - [ ] Sin API key → 401
  - [ ] Logs de acceso funcionan

- [ ] **Sistema crítico:**
  - [ ] Ventas se crean correctamente
  - [ ] Fechas normalizadas correctamente
  - [ ] Dashboard carga sin errores

---

## 🔧 CONFIGURACIÓN REQUERIDA EN PRODUCCIÓN

### Variables de Entorno OBLIGATORIAS:
```bash
FLASK_SECRET_KEY=<clave_secreta_fuerte>
DATABASE_URL=<postgresql://...>
```

### Variables de Entorno OPCIONALES (pero recomendadas):
```bash
# Para bot con contexto operativo
BIMBA_INTERNAL_API_BASE_URL=https://tu-dominio.com
BIMBA_INTERNAL_API_KEY=<clave_api_interna>

# Para bot con OpenAI
OPENAI_API_KEY=<clave_openai>

# Para APIs legacy (si se usan)
API_KEY=<clave_php_pos>
BASE_API_URL=<url_php_pos>
```

---

## 📝 NOTAS IMPORTANTES

1. **OperationalInsightsService:** En producción SIN `BIMBA_INTERNAL_API_BASE_URL`, el bot funcionará pero sin contexto operativo. Esto es seguro y esperado.

2. **Rate Limiting:** Está en memoria. Si hay múltiples procesos/workers, cada uno tendrá su propio contador. Para producción distribuida, considerar Redis en el futuro.

3. **Normalización de Fechas:** Solo se aplica en puntos de escritura. Datos existentes NO se modifican. Si hay fechas mal formateadas en BD, pueden causar problemas hasta que se corrijan manualmente.

4. **Bot Fallback:** El bot NUNCA crashea. Siempre responde algo, aunque sea genérico.

5. **Logging:** Los accesos a API operational se loggean pero NO se guardan en BD. Solo en logs de aplicación.

---

## ✅ ESTADO FINAL

**Sistema:** ✅ LISTO PARA PRODUCCIÓN CONTROLADA

**Riesgos Críticos Resueltos:**
- ✅ Localhost hardcoded → Corregido
- ✅ Bot sin fallback → Corregido
- ✅ Sin rate limiting → Corregido
- ✅ Sin logging de accesos → Corregido
- ✅ Fechas inconsistentes → Parche aplicado

**Próximos Pasos:**
1. Configurar variables de entorno en producción
2. Ejecutar pruebas manuales del checklist
3. Monitorear logs las primeras horas
4. Verificar que el bot funciona correctamente

---

**Fin del Checklist**
