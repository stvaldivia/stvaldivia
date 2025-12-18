# ✅ INSTRUCCIONES FINALES - ¡Todo listo!

**Fecha:** 2025-12-18

---

## 🎯 OBJETIVO

Habilitar ventas con Getnet en la CAJA TEST.

---

## ✅ LO QUE YA ESTÁ HECHO

1. ✅ **Backend actualizado y desplegado:**
   - Código en producción
   - Logging mejorado
   - Endpoints funcionando

2. ✅ **Código del agente actualizado:**
   - Parsea correctamente respuestas JSON del SDK Getnet
   - Extrae AuthorizationCode correctamente
   - Reporta status APPROVED al backend

3. ✅ **Scripts creados para Windows:**
   - `INSTALAR_Y_EJECUTAR.bat` - Todo en uno
   - `recompilar.bat` - Solo recompilar
   - `ejecutar.bat` - Solo ejecutar
   - `CONFIGURAR_VARIABLES.bat` - Solo configurar

---

## 🚀 QUÉ HACER AHORA (En Windows - CAJA TEST)

### Opción 1: Script Automatizado (RECOMENDADO)

1. **Copia estos archivos a la máquina Windows:**
   - Todos los `.bat` del directorio `getnet_agent/java/`
   - `GetnetAgent.java` (debe generarse con `setup_getnet_agent_java.sh` o copiarse desde donde esté)
   - Los JARs del SDK (ya están en `getnet_agent/java/sdk/`)

2. **Ejecuta:**
   ```batch
   INSTALAR_Y_EJECUTAR.bat
   ```

   Este script hace TODO automáticamente:
   - Verifica Java
   - Descarga json.jar si falta
   - Verifica JARs del SDK
   - Configura variables
   - Compila el agente
   - Ejecuta el agente

### Opción 2: Pasos Manuales

1. **Configurar variables:**
   ```batch
   CONFIGURAR_VARIABLES.bat
   ```
   O manualmente:
   ```batch
   set REGISTER_ID=1
   set BASE_URL=https://stvaldivia.cl
   set AGENT_API_KEY=bimba_getnet_prod_xxxxxxxxxxxxxxxxxxxxxxxx
   ```

2. **Recompilar:**
   ```batch
   recompilar.bat
   ```

3. **Ejecutar:**
   ```batch
   ejecutar.bat
   ```

---

## 📋 ARCHIVOS NECESARIOS

En el directorio del agente en Windows necesitas:

**Scripts:**
- `INSTALAR_Y_EJECUTAR.bat` ✅
- `recompilar.bat` ✅
- `ejecutar.bat` ✅
- `CONFIGURAR_VARIABLES.bat` ✅

**Código:**
- `GetnetAgent.java` (generado por setup_getnet_agent_java.sh)

**JARs:**
- `json.jar` (se descarga automáticamente si falta)
- `POSIntegradoGetnet.jar` (del SDK Getnet)
- `jSerialComm-2.9.3.jar` (del SDK Getnet)
- `gson-2.10.1.jar` (del SDK Getnet)

---

## 🔍 VERIFICACIÓN

### 1. Verificar que el agente está corriendo

En la consola del agente deberías ver:
```
🔌 Inicializando conexión Getnet...
   Puerto: COM4
   Baudrate: 115200
✅ Conexión Getnet OK

💓 Heartbeat enviado: OK
```

### 2. Verificar en el panel admin

1. Ve a: https://stvaldivia.cl/admin
2. Busca la tarjeta "Estado Getnet (CAJA TEST)"
3. Debe mostrar:
   - Badge verde "OK"
   - "Agente: online"
   - "Getnet: OK"

### 3. Probar una venta

1. Abre la caja TEST001 en el POS
2. Agrega productos al carrito
3. Selecciona pago con tarjeta (no efectivo)
4. Observa:
   - Aparece mensaje "Esperando terminal GETNET…"
   - El agente procesa el pago
   - Se muestra el ticket con QR
   - La venta se crea automáticamente

---

## 🐛 SI ALGO FALLA

### El agente no inicia

1. Verifica Java:
   ```batch
   java -version
   javac -version
   ```

2. Verifica que existan todos los JARs

3. Revisa los errores en la consola

### El agente no conecta con Getnet

1. Verifica que el terminal esté conectado
2. Verifica el puerto COM (puede ser COM3, COM4, COM5)
3. Prueba ejecutar como Administrador
4. Revisa el estado en el panel admin

### El agente no procesa pagos

1. Revisa los logs del agente (consola)
2. Revisa los logs del backend:
   ```bash
   ssh stvaldivia
   tail -f /var/www/stvaldivia/logs/error.log | grep PAYMENT_INTENT
   ```
3. Verifica que el AGENT_API_KEY coincida en servidor y agente

### El frontend no detecta el pago aprobado

1. Abre DevTools (F12) en el navegador
2. Ve a la consola
3. Busca mensajes sobre PaymentIntent
4. Verifica que el polling esté funcionando

---

## 📞 SOPORTE

Si después de seguir estos pasos sigue sin funcionar:

1. **Revisa los logs del agente** (consola donde corre)
2. **Revisa los logs del backend:**
   ```bash
   tail -f /var/www/stvaldivia/logs/error.log | grep PAYMENT_INTENT
   ```
3. **Revisa la consola del navegador** (F12) cuando intentas hacer una venta
4. **Revisa el panel admin** para ver el estado del agente

---

## ✅ CHECKLIST FINAL

- [ ] Scripts copiados a Windows
- [ ] GetnetAgent.java actualizado (con parseo JSON)
- [ ] JARs del SDK presentes
- [ ] Variables de entorno configuradas
- [ ] Agente compilado sin errores
- [ ] Agente ejecutándose
- [ ] Heartbeat funcionando (ver en panel admin)
- [ ] Getnet conectado (ver en panel admin)
- [ ] Venta de prueba exitosa

---

## 🎉 ¡LISTO!

Una vez completado el checklist, ya puedes vender con Getnet.

El flujo completo:
1. Usuario selecciona pago con tarjeta
2. Frontend crea PaymentIntent READY
3. Agente detecta y procesa con Getnet
4. Agente reporta APPROVED
5. Frontend crea venta automáticamente
6. Se muestra ticket con QR

¡A vender! 💳


