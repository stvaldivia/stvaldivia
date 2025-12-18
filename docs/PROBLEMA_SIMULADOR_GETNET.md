# ⚠️ Problema: Simulador Getnet vs Sistema Real

**Fecha:** 2025-12-18

---

## 🔍 Problema Identificado

El **simulador de Getnet** funciona correctamente (se ve transacción aprobada), pero nuestro sistema no funciona.

**Causa principal:** Solo una aplicación puede usar un puerto COM a la vez. Si el simulador está usando COM3, nuestro agente Java no puede usar ese mismo puerto.

---

## 📊 Estado Actual

### Simulador Getnet:
- ✅ Conectado a COM3
- ✅ Transacciones funcionando
- ✅ ResponseCode: 0 (Aprobado)
- ✅ AuthorizationCode recibido

### Nuestro Sistema:
- ❌ No puede usar COM3 (ocupado por simulador)
- ❌ Agente Java no puede conectarse
- ❌ Heartbeat hace ~3 horas (agente no está corriendo o falla al inicializar)

---

## 🔧 Solución

### Opción 1: Cerrar el Simulador (Recomendado)

**Para usar nuestro sistema de producción:**

1. **Cerrar el simulador Getnet:**
   - Cerrar completamente la aplicación "Getnet Simulador de Caja 2.21"
   - Esto libera el puerto COM3

2. **Verificar que el puerto esté libre:**
   ```batch
   # En Windows PowerShell
   Get-WmiObject Win32_SerialPort | Where-Object {$_.DeviceID -like "COM*"}
   ```

3. **Iniciar nuestro agente Java:**
   ```batch
   cd C:\getnet_agent\java
   ejecutar.bat
   ```

4. **Verificar que el agente se conecte:**
   - Debe ver: `✅ Puerto serial abierto: COM3`
   - Debe ver: `✅ SDK Getnet inicializado`
   - Debe ver: `💓 Heartbeat enviado: Getnet=OK`

---

### Opción 2: Usar Puerto Diferente (Si es posible)

Si tienes múltiples terminales Getnet o puedes cambiar el puerto:

1. **Cambiar configuración del simulador** a otro puerto (COM6, COM5, etc.)
2. **Mantener nuestro agente en COM3**

---

## 📋 Checklist de Verificación

### 1. Verificar Estado del Puerto COM3

**En Windows:**
```batch
# Ver qué proceso está usando COM3
wmic path Win32_SerialPort where "DeviceID='COM3'" get DeviceID,Description,Name

# Ver todos los puertos COM disponibles
Get-WmiObject Win32_SerialPort | Select-Object DeviceID, Description, Name
```

### 2. Verificar si el Agente Está Corriendo

```batch
# Ver procesos Java
tasklist | findstr java

# Si hay procesos Java, ver detalles
wmic process where "name='java.exe'" get commandline,processid
```

### 3. Verificar Logs del Agente

Si el agente está corriendo, revisar la consola:
- ¿Muestra `✅ Puerto serial abierto: COM3`?
- ¿Muestra `ERROR: No se pudo abrir puerto serial COM3`?
- ¿Muestra `💓 Heartbeat enviado`?

---

## 🐛 Errores Comunes

### Error: "No se pudo abrir puerto serial COM3"

**Causas:**
1. Simulador Getnet está usando el puerto
2. Otro programa está usando el puerto
3. Permisos insuficientes

**Solución:**
1. Cerrar el simulador Getnet
2. Cerrar cualquier otro programa que use COM3
3. Ejecutar el agente como Administrador

---

### Error: "Puerto COM3 no encontrado"

**Causas:**
1. El terminal Getnet no está conectado
2. Drivers no instalados
3. Puerto COM no visible en Windows

**Solución:**
1. Verificar que el terminal esté conectado físicamente
2. Verificar en Administrador de Dispositivos → Puertos COM
3. Reiniciar el terminal o reconectar el cable

---

### Error: Heartbeat no se envía

**Causas:**
1. El agente no está corriendo
2. Error de conexión al backend
3. `AGENT_API_KEY` incorrecto

**Solución:**
1. Verificar que el agente esté corriendo (`tasklist | findstr java`)
2. Revisar logs del agente para errores de conexión
3. Verificar variables de entorno (`AGENT_API_KEY`, `BASE_URL`, etc.)

---

## 🔄 Flujo Correcto de Operación

### Producción Normal:

1. **Terminal Getnet físicamente conectado** a COM3
2. **Simulador Getnet cerrado** (no debe estar corriendo)
3. **Agente Java corriendo** continuamente:
   ```batch
   cd C:\getnet_agent\java
   ejecutar.bat
   ```
4. **Agente envía heartbeats** cada 30 segundos
5. **Agente procesa pagos** cuando se crean PaymentIntents

---

## 🧪 Usar Simulador para Testing

**Solo para pruebas/desarrollo:**

1. **Detener el agente Java** (Ctrl+C o `taskkill /F /IM java.exe`)
2. **Abrir el simulador Getnet**
3. **Realizar pruebas** con el simulador
4. **Cerrar el simulador** cuando termines
5. **Reiniciar el agente Java** para producción

---

## 📊 Verificar Estado desde el Backend

**Panel Admin:**
- URL: https://stvaldivia.cl/admin
- Tarjeta: "Estado Getnet (CAJA TEST)"
- Debe mostrar:
  - ✅ Agente: online (si heartbeat < 60 segundos)
  - ✅ Getnet: OK (si terminal conectado)
  - ❌ Error: Si simulador está usando el puerto

**API:**
```bash
curl -H "Cookie: session=<tu-session>" \
  "https://stvaldivia.cl/admin/api/getnet/status?register_id=1"
```

---

## ⚠️ IMPORTANTE

**El simulador y nuestro sistema NO pueden funcionar simultáneamente** porque ambos intentan usar el mismo puerto COM3.

**Para producción:**
- ✅ Usar nuestro agente Java
- ❌ NO usar el simulador

**Para pruebas/desarrollo:**
- ✅ Usar el simulador (pero detener el agente primero)
- ❌ NO usar ambos a la vez

---

## 🎯 Resumen de Pasos Inmediatos

1. **Cerrar el simulador Getnet** si está abierto
2. **Verificar que COM3 esté libre**
3. **Iniciar el agente Java** (`ejecutar.bat`)
4. **Verificar logs** del agente
5. **Verificar estado** en panel admin
6. **Hacer venta de prueba** desde el TPV

---

## 📞 Si Sigue Sin Funcionar

1. **Revisar logs del agente** (la consola donde corre)
2. **Revisar logs del backend:**
   ```bash
   ssh stvaldivia
   tail -f /var/www/stvaldivia/logs/error.log | grep PAYMENT_INTENT
   ```
3. **Verificar configuración del puerto** en panel admin:
   - Ir a: Máquinas de Pago → Editar → Verificar puerto COM3
4. **Probar conexión** con `test_getnet_connection.java`


