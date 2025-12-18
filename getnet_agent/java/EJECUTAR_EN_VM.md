# 🖥️ Ejecutar Pago Directo en Máquina Virtual Windows

**Fecha:** 2025-12-18

---

## 📋 ESCENARIO

El terminal Getnet está conectado a una **máquina virtual Windows**.

---

## 🔧 OPCIONES PARA ACCEDER

### Opción 1: Acceso Directo (Recomendado)

Si puedes acceder directamente a la VM:

1. **Conectar a la VM:**
   - Remote Desktop (RDP)
   - VNC
   - O acceso físico si es local

2. **Ejecutar el script desde la VM:**
   ```batch
   cd C:\ruta\al\agente\getnet_agent\java
   pago_directo.bat 100
   ```

---

### Opción 2: Copiar Archivos a la VM

Si necesitas copiar los archivos primero:

**Método A: Compartir carpeta**
1. Comparte una carpeta desde tu Mac al host de la VM
2. Copia los archivos a la VM
3. Ejecuta desde la VM

**Método B: SCP/WinSCP (si tiene SSH)**
```bash
# Desde Mac/Linux
scp -r getnet_agent/java/* usuario@vm-windows:/ruta/destino/
```

**Método C: USB/CD compartido**
1. Monta USB o CD en la VM
2. Copia archivos
3. Ejecuta

---

### Opción 3: PowerShell Remoto (Si está habilitado)

Si PowerShell Remoting está habilitado en la VM:

```powershell
# Desde tu máquina (si tienes PowerShell)
Enter-PSSession -ComputerName vm-windows -Credential usuario

# Dentro de la sesión remota
cd C:\ruta\al\agente\getnet_agent\java
.\pago_directo.bat 100
```

---

## 🔌 IMPORTANTE: Puerto COM en VM

### Si el Terminal Getnet está físicamente conectado:

**El puerto COM debe estar "pasado" a la VM:**

1. **VMware:**
   - Settings de la VM → USB
   - Agregar dispositivo USB (el terminal Getnet)
   - O configurar passthrough del puerto serial

2. **VirtualBox:**
   - Settings → Ports → Serial Ports
   - Habilitar puerto COM (ej: COM3)
   - Configurar para usar el dispositivo físico

3. **Hyper-V:**
   - Settings → COM Ports
   - Configurar Named Pipe o passthrough físico

### Verificar que la VM vea el puerto COM:

**En la VM Windows:**
```powershell
Get-WmiObject Win32_SerialPort | Select-Object Name, DeviceID
```

Deberías ver `COM3` en la lista.

---

## 🚀 PASOS COMPLETOS

### 1. Verificar Acceso a la VM

**Conectar a la VM:**
- Remote Desktop (mstsc.exe)
- O acceso físico

### 2. Verificar Puerto COM en la VM

**Abrir PowerShell en la VM:**
```powershell
Get-WmiObject Win32_SerialPort
```

**Buscar COM3:**
- Si no aparece, configurar el passthrough del puerto en la VM
- El terminal debe estar conectado al HOST y pasarse a la VM

### 3. Preparar Archivos en la VM

**Crear directorio (si no existe):**
```batch
mkdir C:\getnet_agent\java
cd C:\getnet_agent\java
```

**Copiar archivos necesarios:**
- `pago_directo.java`
- `pago_directo.bat`
- `POSIntegradoGetnet.jar`
- `jSerialComm-2.9.3.jar`
- `gson-2.10.1.jar`
- `json.jar`

### 4. Verificar Java en la VM

```batch
java -version
javac -version
```

Si no está instalado, instalarlo.

### 5. Ejecutar el Script

```batch
cd C:\getnet_agent\java
pago_directo.bat 100
```

---

## ⚠️ PROBLEMAS COMUNES EN VM

### Problema: "Puerto COM3 no encontrado"

**Causa:** El puerto COM no está pasado a la VM.

**Solución:**
1. Configurar passthrough del puerto serial en la VM
2. O conectar el terminal directamente a la VM (si es posible)

### Problema: "Puerto está siendo usado"

**Causa:** Otro programa o el agente Java está usando el puerto.

**Solución:**
```batch
# Detener agente Java si está corriendo
taskkill /F /IM java.exe

# Esperar unos segundos
timeout /t 3

# Ejecutar script
pago_directo.bat 100
```

### Problema: "Acceso denegado al puerto"

**Causa:** Permisos insuficientes.

**Solución:**
1. Ejecutar como Administrador
2. O configurar permisos del puerto COM

---

## 📋 CHECKLIST

Antes de ejecutar, verifica:

- [ ] Acceso a la VM (RDP/VNC/físico)
- [ ] Terminal Getnet conectado al HOST
- [ ] Puerto COM pasado a la VM
- [ ] Java instalado en la VM
- [ ] JARs del SDK Getnet en la VM
- [ ] Archivos del script copiados a la VM
- [ ] Puerto COM3 visible en la VM (Get-WmiObject)
- [ ] Ningún otro programa usando COM3

---

## 🔄 ALTERNATIVA: Ejecutar desde el HOST

Si el terminal Getnet está conectado al **HOST** (no a la VM):

1. **Ejecutar el script en el HOST:**
   - Si el HOST es Windows: Ejecutar directamente ahí
   - Si el HOST es Linux/Mac: No es posible (necesita Windows)

2. **O configurar passthrough:**
   - Pasar el puerto COM del HOST a la VM
   - Ejecutar script en la VM

---

## 📞 SOPORTE

Si tienes problemas:

1. **Verifica que la VM vea el puerto:**
   ```powershell
   Get-WmiObject Win32_SerialPort
   ```

2. **Verifica permisos:**
   - Ejecutar como Administrador

3. **Verifica que el terminal esté encendido:**
   - El terminal debe estar encendido y conectado

4. **Revisa logs del script:**
   - Los mensajes de error en la consola ayudan a diagnosticar

---

## ✅ RESUMEN

**Para ejecutar en VM:**

1. Conectar a la VM
2. Verificar que COM3 esté disponible
3. Copiar archivos si es necesario
4. Ejecutar: `pago_directo.bat 100`

**Importante:** El puerto COM debe estar "pasado" desde el HOST a la VM para que funcione.


