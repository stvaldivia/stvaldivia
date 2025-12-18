# 🔧 Cómo el Agente Java Obtiene la Configuración de Getnet

**Fecha:** 2025-12-18

---

## 📋 MÉTODO ACTUAL (Mejorado)

### 1. Al Iniciar el Agente

El agente Java ahora **carga automáticamente la configuración desde el backend** al iniciar:

1. Hace una petición a: `GET /caja/api/payment/agent/config?register_id=1`
2. El backend retorna la configuración desde `pos_registers.provider_config`
3. El agente usa esa configuración (puerto COM, baudrate, timeout)

### 2. Fallback a Variables de Entorno

Si falla la carga desde el backend, el agente usa:
- Variables de entorno: `GETNET_PORT`, `GETNET_BAUDRATE`, `GETNET_TIMEOUT_MS`
- O valores por defecto: COM4, 115200, 30000

---

## 🔄 FLUJO COMPLETO

### Backend (Base de Datos)

```
pos_registers.provider_config (JSON):
{
  "GETNET": {
    "mode": "serial",
    "port": "COM4",
    "baudrate": 115200,
    "timeout_ms": 30000
  }
}
```

### Endpoint del Backend

**URL:** `GET /caja/api/payment/agent/config?register_id=1`  
**Auth:** Header `X-AGENT-KEY`

**Respuesta:**
```json
{
  "success": true,
  "register_id": "1",
  "register_name": "CAJA TEST BIMBA",
  "register_code": "TEST001",
  "getnet": {
    "enabled": true,
    "mode": "serial",
    "port": "COM4",
    "baudrate": 115200,
    "timeout_ms": 30000
  }
}
```

### Agente Java

1. **Al iniciar:** Llama a `/caja/api/payment/agent/config`
2. **Obtiene configuración:** Puerto, baudrate, timeout
3. **Usa configuración:** Para inicializar conexión serial con Getnet

---

## ✅ VENTAJAS

1. **Configuración centralizada:** Se cambia desde el panel admin
2. **Sin reiniciar agente:** (Aunque actualmente solo carga al iniciar)
3. **Sincronizado:** Agente siempre usa la misma config que el backend
4. **Fallback seguro:** Si falla, usa variables de entorno o defaults

---

## 🔧 CÓMO CAMBIAR LA CONFIGURACIÓN

### Método 1: Panel de Administración (Recomendado)

1. Ir a `/admin/payment-machines`
2. Seleccionar la máquina
3. Hacer clic en "⚙️ Configurar"
4. Cambiar puerto, baudrate, etc.
5. Guardar

**IMPORTANTE:** Después de cambiar, **reiniciar el agente Java** para que cargue la nueva configuración.

### Método 2: Variables de Entorno (Fallback)

```bash
export GETNET_PORT=COM5
export GETNET_BAUDRATE=115200
export GETNET_TIMEOUT_MS=30000
./run.sh
```

---

## 📝 CÓDIGO RELEVANTE

### Backend: Endpoint de Configuración

**Archivo:** `app/blueprints/pos/views/payment_intents.py`  
**Función:** `agent_get_config()`

### Agente Java: Carga de Configuración

**Archivo:** `getnet_agent/java/GetnetAgent.java` (generado por setup.sh)  
**Función:** `cargarConfiguracionDesdeBackend()`

---

## 🧪 PROBAR CONFIGURACIÓN

### Desde Backend (cURL)

```bash
curl -H "X-AGENT-KEY: <tu-key>" \
  "https://stvaldivia.cl/caja/api/payment/agent/config?register_id=1"
```

### Desde Agente

El agente imprime al iniciar:
```
📥 Cargando configuración desde backend...
✅ Configuración cargada desde backend para register: CAJA TEST BIMBA
Configuración Getnet cargada:
  GETNET_PORT=COM4
  GETNET_BAUDRATE=115200
  GETNET_TIMEOUT_MS=30000
```

---

## ⚠️ NOTA IMPORTANTE

**El agente carga la configuración SOLO AL INICIAR.**

Si cambias la configuración en el panel admin:
1. Debes **reiniciar el agente Java** para que use la nueva configuración
2. O implementar recarga dinámica (futuro)

---

## 🔮 MEJORA FUTURA (Opcional)

Podríamos implementar recarga dinámica:
- El agente consulta la configuración periódicamente
- O el backend notifica cuando cambia la configuración
- El agente recarga automáticamente sin reiniciar

**Por ahora, reiniciar el agente después de cambiar configuración es suficiente.**


