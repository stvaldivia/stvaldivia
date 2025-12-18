# 🔍 Cómo Diagnosticar Problemas con el Agente Getnet

**Fecha:** 2025-12-18

---

## 🎯 Situación

El simulador de Getnet funciona, pero nuestro sistema no funciona cuando debería.

---

## 📋 Checklist de Diagnóstico

### 1. ¿El agente está corriendo?

**En Windows (PowerShell o CMD):**
```batch
tasklist | findstr java
```

**Si aparece un proceso `java.exe`:**
- ✅ El agente podría estar corriendo
- Verifica que sea nuestro agente (ver paso 2)

**Si NO aparece:**
- ❌ El agente NO está corriendo
- Debes iniciarlo (ver "Iniciar el Agente" más abajo)

---

### 2. Verificar que es nuestro agente

**Ver comandos de procesos Java:**
```batch
wmic process where "name='java.exe'" get commandline,processid
```

**Busca en el `commandline`:**
- Debe contener `GetnetAgent`
- Debe contener la ruta a los JARs

---

### 3. Verificar que los archivos existen

**Si `ejecutar.bat` NO existe:**

⚠️ **Primero debes copiar los archivos desde el repositorio.**

Ver guía completa: `COPIAR_ARCHIVOS_A_WINDOWS.md`

**Resumen rápido:**
1. Copiar archivos `.bat` desde el repositorio a `C:\getnet_agent\java\`
2. Copiar `GetnetAgent.java` (o generarlo con `setup_getnet_agent_java.sh`)
3. Copiar JARs del SDK Getnet
4. Ejecutar `INSTALAR_Y_EJECUTAR.bat` (instalación completa)

**Verificar que los archivos existen:**
```batch
cd C:\getnet_agent\java
dir ejecutar.bat
dir GetnetAgent.java
dir *.jar
```

### 4. Iniciar el Agente y Observar Errores

**Ubicarse en el directorio:**
```batch
cd C:\getnet_agent\java
```

**Iniciar:**
```batch
ejecutar.bat
```

**O manualmente:**
```batch
java -cp .;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar GetnetAgent
```

**Observar los primeros mensajes:**
- ✅ `BASE_URL=...` (debe ser https://stvaldivia.cl/caja)
- ✅ `REGISTER_ID=...` (debe ser 1 o TEST001)
- ✅ `Configuración Getnet cargada:` (debe mostrar puerto, baudrate)
- ❌ `❌ Falta env AGENT_API_KEY` → **Problema de configuración**

---

### 5. Errores Comunes al Iniciar

#### Error: "No se pudo abrir puerto serial COM3"

**Causas:**
1. Puerto COM3 está siendo usado por otro programa
2. Terminal Getnet no está conectado
3. Permisos insuficientes
4. Puerto COM3 no existe

**Soluciones:**
```batch
# Verificar qué está usando COM3
Get-WmiObject Win32_SerialPort | Where-Object {$_.DeviceID -eq "COM3"}

# Verificar que el terminal esté conectado
# (en Administrador de Dispositivos → Puertos COM)

# Ejecutar como Administrador
# (click derecho → Ejecutar como administrador)
```

---

#### Error: "AGENT_API_KEY no configurado"

**Causa:** Variable de entorno no configurada

**Solución:**
```batch
# Verificar variables de entorno actuales
echo %AGENT_API_KEY%
echo %BASE_URL%
echo %REGISTER_ID%

# Si están vacías, configurarlas:
set AGENT_API_KEY=bimba_getnet_prod_xxxxxxxxxxxxxxxxxxxxxxxx
set BASE_URL=https://stvaldivia.cl/caja
set REGISTER_ID=1

# Luego ejecutar el agente
ejecutar.bat
```

**O usar el script de configuración:**
```batch
CONFIGURAR_VARIABLES.bat
```

---

#### Error: "Connection refused" o "Error de conexión al backend"

**Causas:**
1. Backend no accesible
2. Firewall bloqueando conexiones
3. BASE_URL incorrecto

**Soluciones:**
```batch
# Probar conexión al backend
curl https://stvaldivia.cl/caja/api/payment/agent/pending?register_id=1

# O con PowerShell
Invoke-WebRequest -Uri "https://stvaldivia.cl/caja/api/payment/agent/pending?register_id=1" -Headers @{"X-AGENT-KEY"="tu-key-aqui"}
```

---

#### Error: "ClassNotFoundException" o "NoClassDefFoundError"

**Causa:** Faltan JARs o classpath incorrecto

**Solución:**
```batch
# Verificar que todos los JARs estén presentes
dir *.jar

# Debes ver:
# - json.jar
# - POSIntegradoGetnet.jar
# - jSerialComm-2.9.3.jar
# - gson-2.10.1.jar

# Si falta alguno, copiarlo desde el SDK de Getnet
```

---

### 6. Verificar Logs del Agente

**Mensajes esperados al iniciar:**
```
BASE_URL=https://stvaldivia.cl/caja
REGISTER_ID=1
AGENT_ID=...

Configuración Getnet cargada:
  GETNET_PORT=COM3
  GETNET_BAUDRATE=115200
  GETNET_TIMEOUT_MS=30000

🔌 Inicializando conexión Getnet...
   Puerto: COM3
   Baudrate: 115200
✅ Puerto serial abierto: COM3
✅ SDK Getnet inicializado
💓 Heartbeat enviado: Getnet=OK (Pinpad conectado y listo)
```

**Mensajes de error comunes:**
```
❌ Error al abrir puerto: 5
   → Puerto en uso o permisos insuficientes

❌ Error al verificar Getnet: ...
   → Problema de conexión con el terminal

⚠️ Heartbeat falló: ...
   → Problema de conexión con el backend
```

---

### 7. Verificar Estado en el Backend

**Panel Admin:**
- URL: https://stvaldivia.cl/admin
- Tarjeta: "Estado Getnet (CAJA TEST)"
- Debe mostrar:
  - ✅ Agente: online (si heartbeat < 60 segundos)
  - ✅ Getnet: OK (si terminal conectado)
  - ❌ Error: Si hay problemas

**API Directa:**
```bash
curl -H "Cookie: session=..." \
  "https://stvaldivia.cl/admin/api/getnet/status?register_id=1"
```

---

### 8. Probar Conexión Directa al Terminal

**Si el agente no puede conectarse, probar directamente:**

```batch
cd C:\getnet_agent\java
test_com3.bat
```

**O:**
```batch
javac -cp .;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar test_getnet_connection.java
java -cp .;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar test_getnet_connection COM3
```

**Esto verifica:**
- ✅ Que COM3 existe
- ✅ Que se puede abrir
- ✅ Que el SDK puede inicializar
- ✅ Que el terminal responde

---

## 🔧 Pasos de Resolución Rápida

### Si el agente NO está corriendo:

1. **Verificar configuración:**
   ```batch
   CONFIGURAR_VARIABLES.bat
   ```

2. **Iniciar agente:**
   ```batch
   ejecutar.bat
   ```

3. **Observar errores** en la consola

4. **Si hay errores**, seguir las soluciones arriba

---

### Si el agente SÍ está corriendo pero no funciona:

1. **Verificar logs del agente** (la consola donde corre)

2. **Verificar estado en panel admin:**
   - ¿Muestra "online"?
   - ¿Muestra "Getnet: OK"?

3. **Si muestra "ERROR":**
   - Revisar mensaje de error
   - Verificar que el terminal esté conectado físicamente
   - Verificar que COM3 esté disponible

---

## 📞 Información para Reportar Problemas

Si necesitas ayuda, proporciona:

1. **¿El agente está corriendo?**
   ```
   tasklist | findstr java
   ```

2. **Primeros mensajes del agente** (al iniciar)

3. **Últimos mensajes del agente** (errores recientes)

4. **Estado en panel admin:**
   - Agente: online/offline
   - Getnet: OK/ERROR
   - Último heartbeat: hace X segundos

5. **Resultado de prueba directa:**
   ```batch
   test_com3.bat
   ```

---

## 🎯 Flujo de Diagnóstico Completo

```
1. Verificar si agente está corriendo
   ↓ NO
2. Iniciar agente
   ↓ Error al iniciar
3. Revisar mensajes de error
   ↓
4. Aplicar solución según error
   ↓
5. Reiniciar agente
   ↓ OK
6. Verificar heartbeats
   ↓ Heartbeats OK
7. Verificar estado en panel admin
   ↓ Estado OK
8. Probar venta desde TPV
```

---

## ⚠️ Notas Importantes

- **El agente debe correr continuamente** mientras la caja esté operativa
- **Cierra el simulador Getnet** antes de iniciar el agente
- **Solo una aplicación** puede usar COM3 a la vez
- **Ejecuta como Administrador** si hay problemas de permisos
- **Verifica la conexión física** del terminal Getnet


