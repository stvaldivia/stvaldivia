# 🔍 Cómo Verificar Conexión Getnet

**Fecha:** 2025-12-18

---

## 🎯 Problema

El sistema imprime tickets pero Getnet no procesa pagos. Necesitamos verificar si el terminal Getnet está conectado y funcionando.

---

## ✅ SOLUCIONES IMPLEMENTADAS

### 1. Verificación Automática en el Agente

El agente ahora verifica automáticamente la conexión Getnet y envía el estado en cada heartbeat.

**Estado reportado:**
- `OK` - Terminal conectado y respondiendo
- `UNKNOWN` - Puerto abierto pero no se puede verificar terminal
- `ERROR` - Error de conexión o terminal no responde

**Mensaje incluido:**
- Descripción detallada del estado
- Errores específicos si los hay

### 2. Script de Prueba Manual

**Archivo:** `tools/test_getnet_connection.java`

**Uso:**
```bash
cd ~/getnet_agent/java

# Compilar
javac -cp .:POSIntegradoGetnet.jar:jSerialComm-2.9.3.jar:gson-2.10.1.jar ../tools/test_getnet_connection.java

# Ejecutar (puerto y baudrate por defecto: COM4, 115200)
java -cp .:POSIntegradoGetnet.jar:jSerialComm-2.9.3.jar:gson-2.10.1.jar:.. test_getnet_connection COM4 115200
```

**Qué hace:**
1. Lista puertos COM disponibles
2. Verifica que COM4 existe
3. Intenta abrir el puerto
4. Inicializa el SDK Getnet
5. Verifica comunicación con el terminal
6. Reporta el estado

---

## 📊 Verificar Estado desde el Backend

### Panel de Administración

**URL:** `/admin/dashboard`

**Tarjeta:** "Estado Getnet (CAJA TEST)"

**Muestra:**
- Estado del agente (online/offline)
- Estado de Getnet (OK/ERROR/UNKNOWN)
- Último heartbeat
- Mensaje de estado

### API Directa

```bash
curl -H "Authorization: Bearer <token>" \
  "https://stvaldivia.cl/admin/api/getnet/status?register_id=1"
```

**Respuesta:**
```json
{
  "register_id": "1",
  "agent": {
    "online": true,
    "agent_name": "POS-CAJA-TEST",
    "last_heartbeat": "2025-12-18T...",
    "last_getnet_status": "OK",
    "last_getnet_message": "OK: Terminal responde correctamente",
    "seconds_since_heartbeat": 5
  },
  "backend": {
    "ok": true,
    "last_payment_intent_at": "...",
    "last_payment_intent_status": "READY"
  },
  "overall_status": "OK"
}
```

---

## 🔧 Diagnóstico de Problemas

### Problema: "ERROR: Puerto serial no está abierto"

**Causas posibles:**
- El agente no está corriendo
- El puerto está en uso por otra aplicación
- El puerto no existe (verificar en Device Manager)

**Solución:**
1. Verificar que el agente está corriendo: `ps aux | grep GetnetAgent`
2. Verificar puertos disponibles: Device Manager → Ports (COM & LPT)
3. Cerrar otras aplicaciones que usen COM4

### Problema: "ERROR: No se pudo abrir puerto serial COM4"

**Causas posibles:**
- Puerto en uso
- Drivers no instalados
- Terminal no conectado

**Solución:**
1. Verificar en Device Manager que COM4 existe
2. Verificar que no hay otra aplicación usando COM4
3. Reiniciar el terminal Getnet
4. Verificar cable USB

### Problema: "WARN: Puerto abierto pero estado del terminal desconocido"

**Causas posibles:**
- Terminal no responde a comandos de prueba
- Configuración incorrecta (baudrate)
- Terminal apagado o en modo de error

**Solución:**
1. Verificar que el terminal está encendido
2. Verificar baudrate (debe ser 115200)
3. Reiniciar el terminal
4. Verificar cable y conexión

### Problema: "ERROR: Error al verificar: ..."

**Causas posibles:**
- SDK no puede comunicarse con el terminal
- Timeout en comunicación
- Error en el terminal

**Solución:**
1. Revisar logs del agente para más detalles
2. Ejecutar script de prueba manual
3. Contactar soporte Getnet si persiste

---

## 🧪 Testing Paso a Paso

### 1. Verificar Hardware

```powershell
# En Windows PowerShell
Get-WmiObject Win32_SerialPort | Select-Object Name, DeviceID, Description
```

**Buscar:** COM4 en la lista

### 2. Verificar Agente

```bash
# En Windows, verificar que el agente está corriendo
# Ver logs del agente
```

**Buscar en logs:**
- "✅ Puerto serial abierto: COM4"
- "✅ SDK Getnet inicializado"
- "💓 Heartbeat enviado: Getnet=OK"

### 3. Ejecutar Script de Prueba

```bash
cd ~/getnet_agent/java
java -cp .:POSIntegradoGetnet.jar:jSerialComm-2.9.3.jar:gson-2.10.1.jar:.. test_getnet_connection COM4 115200
```

**Resultado esperado:**
- ✅ Puerto COM4 encontrado
- ✅ Puerto abierto correctamente
- ✅ SDK Getnet inicializado
- ✅ Terminal Getnet está conectado y responde

### 4. Verificar en Panel Admin

1. Ir a `/admin/dashboard`
2. Buscar tarjeta "Estado Getnet (CAJA TEST)"
3. Verificar que muestra:
   - Badge verde (OK)
   - "Getnet: OK"
   - Mensaje positivo

---

## 📝 Logs del Agente

El agente imprime información detallada:

```
🔌 Inicializando conexión Getnet...
   Puerto: COM4
   Baudrate: 115200
✅ Puerto serial abierto: COM4
✅ SDK Getnet inicializado
💓 Heartbeat enviado: Getnet=OK (OK: Terminal responde correctamente)
```

**Si hay errores:**
```
⚠️  Error al verificar Getnet: No se pudo abrir puerto serial COM4
💓 Heartbeat enviado: Getnet=ERROR (ERROR: No se pudo abrir puerto serial COM4)
```

---

## 🎯 Próximos Pasos

1. **Ejecutar script de prueba** para diagnosticar el problema actual
2. **Revisar logs del agente** para ver qué está reportando
3. **Verificar en panel admin** el estado actual
4. **Ajustar configuración** según los resultados

---

## 📚 Referencias

- Script de prueba: `tools/test_getnet_connection.java`
- Agente: `getnet_agent/java/GetnetAgent.java`
- Panel admin: `/admin/dashboard`
- API status: `/admin/api/getnet/status?register_id=1`


