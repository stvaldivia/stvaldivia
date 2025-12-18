# 🔍 Cómo "Hacer Ping" al Terminal Getnet

**Fecha:** 2025-12-18

---

## ⚠️ IMPORTANTE

El terminal Getnet **NO es una máquina en red** (no tiene IP). Es un dispositivo **físico conectado por puerto serial (COM3)**.

Por lo tanto, **NO puedes hacer ping tradicional** como harías con un servidor. En su lugar, debes verificar la **conexión serial**.

---

## 🎯 MÉTODOS PARA VERIFICAR LA CONEXIÓN

### Método 1: Panel de Administración (Más Fácil) ✅

1. Ve a: https://stvaldivia.cl/admin
2. Busca la tarjeta "Estado Getnet (CAJA TEST)"
3. Verifica el estado:
   - **Badge verde "OK"** = Terminal conectado y funcionando
   - **Badge amarillo "WARN"** = Terminal con problemas
   - **Badge rojo "ERROR"** = Terminal desconectado o no disponible

Este método es el más simple porque usa el agente Java que ya está corriendo.

---

### Método 2: Script Java de Prueba

**En Windows (máquina CAJA TEST):**

1. Asegúrate de tener los JARs del SDK Getnet en el directorio
2. Ejecuta:
   ```batch
   test_com3.bat
   ```

O manualmente:
```batch
javac -cp .;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar test_getnet_connection.java
java -cp .;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar test_getnet_connection COM3
```

**El script verificará:**
- ✅ Que el puerto COM3 exista
- ✅ Que el puerto se pueda abrir
- ✅ Que el SDK Getnet se pueda inicializar
- ✅ Comunicación básica con el terminal

---

### Método 3: Verificar Puertos COM en Windows

**Opción A: PowerShell**
```powershell
Get-WmiObject -Class Win32_SerialPort | Where-Object { $_.DeviceID -like "*COM3*" } | Format-List
```

**Opción B: Administrador de Dispositivos**
1. Presiona `Win + X`
2. Selecciona "Administrador de dispositivos"
3. Expande "Puertos (COM y LPT)"
4. Busca "COM3" y verifica que no tenga un símbolo de error

**Opción C: Device Manager (CMD)**
```cmd
devmgmt.msc
```

---

### Método 4: Verificar desde el Agente Java (Si está corriendo)

Si el agente Java ya está corriendo, revisa los logs:

**Deberías ver:**
```
🔌 Inicializando conexión Getnet...
   Puerto: COM3
   Baudrate: 115200
✅ Conexión Getnet OK
💓 Heartbeat enviado: OK
```

**Si ves errores:**
```
❌ Error al abrir puerto: [código de error]
❌ Error: Puerto COM3 no disponible
```

---

### Método 5: Usar Herramientas Serial de Windows

**PuTTY (gratis):**
1. Descarga PuTTY: https://www.putty.org/
2. Abre PuTTY
3. En "Connection type", selecciona "Serial"
4. En "Serial line", escribe: `COM3`
5. En "Speed", escribe: `115200`
6. Haz clic en "Open"
7. Si se conecta sin errores, el puerto está funcionando

**Nota:** El terminal Getnet puede no responder a conexiones directas, pero al menos verificas que el puerto está disponible.

---

## 🔧 TROUBLESHOOTING

### Error: "Puerto COM3 no encontrado"

**Posibles causas:**
- El terminal no está conectado físicamente
- El cable USB/serial está desconectado
- Windows no ha detectado el dispositivo

**Solución:**
1. Verifica la conexión física del terminal
2. Revisa el Administrador de dispositivos
3. Prueba desconectar y reconectar el terminal

---

### Error: "Puerto COM3 está siendo usado"

**Posibles causas:**
- Otro programa está usando el puerto (ej: el agente Java, otro software)
- El puerto quedó bloqueado por una aplicación anterior

**Solución:**
1. Cierra cualquier programa que pueda estar usando COM3
2. Si el agente Java está corriendo, deténlo temporalmente
3. Reinicia el agente después de la prueba

---

### Error: "Acceso denegado" o "Permission denied"

**Posibles causas:**
- Permisos insuficientes
- Windows UAC bloqueando el acceso

**Solución:**
1. Ejecuta como Administrador (clic derecho → "Ejecutar como administrador")
2. O configura permisos del puerto COM3 (ver `docs/WINDOWS11_PROTECCIONES_COM.md`)

---

### Error: "SDK no responde" o "Comunicación falló"

**Posibles causas:**
- El terminal está en un estado de error
- La configuración del SDK no es correcta
- El terminal necesita ser reiniciado

**Solución:**
1. Desconecta y reconecta el terminal físicamente
2. Reinicia el terminal Getnet si tiene botón de reset
3. Verifica que el baudrate sea correcto (115200)

---

## ✅ RESUMEN RÁPIDO

**Método más rápido:** Panel Admin → "Estado Getnet (CAJA TEST)"

**Método más técnico:** Ejecutar `test_com3.bat` en Windows

**Método manual:** Administrador de dispositivos → Verificar COM3

---

## 📝 NOTA

El "ping" a Getnet es realmente una **verificación de conectividad serial**, no una prueba de red tradicional. Lo importante es verificar que:

1. ✅ El puerto COM3 existe
2. ✅ El puerto se puede abrir
3. ✅ El SDK puede comunicarse con el terminal
4. ✅ El terminal responde correctamente


