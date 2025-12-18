# 🛡️ Protecciones de Windows 11 que Afectan el Agente Getnet

**Fecha:** 2025-12-18

---

## ⚠️ PROBLEMAS COMUNES EN WINDOWS 11

Windows 11 tiene varias capas de protección que pueden bloquear el acceso a puertos COM:

1. **Permisos de Usuario**
2. **Firewall de Windows**
3. **UAC (User Account Control)**
4. **Windows Defender / Antivirus**
5. **Permisos del Puerto COM**
6. **Hyper-V / Virtualización**

---

## 🔧 SOLUCIONES PASO A PASO

### 1. Ejecutar como Administrador

**Problema:** El agente Java necesita permisos elevados para acceder a puertos COM.

**Solución:**
- Clic derecho en el script `run.sh` o `.bat`
- Seleccionar "Ejecutar como administrador"

**O desde CMD/PowerShell:**
```cmd
# Abrir PowerShell como Administrador
# Luego ejecutar:
cd C:\ruta\al\agente
java -cp ... GetnetAgent
```

---

### 2. Permisos del Puerto COM

**Problema:** Windows puede bloquear acceso a puertos COM para aplicaciones sin privilegios.

**Solución A: Modificar permisos del puerto**

```powershell
# Ejecutar como Administrador
# 1. Ver puertos COM disponibles
Get-WmiObject -Class Win32_SerialPort | Select-Object Name, DeviceID

# 2. Ver permisos actuales del puerto COM4
Get-Acl COM4:

# 3. Otorgar permisos a tu usuario
$acl = Get-Acl COM4:
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$accessRule = New-Object System.Security.AccessControl.FileSystemAccessRule($user, "FullControl", "Allow")
$acl.SetAccessRule($accessRule)
Set-Acl COM4: $acl
```

**Solución B: Agregar usuario a grupo "Administrators"**

```powershell
# Ejecutar como Administrador
net localgroup Administrators %USERNAME% /add
```

---

### 3. Firewall de Windows

**Problema:** El firewall puede bloquear conexiones salientes del agente Java al backend.

**Solución:**

```powershell
# Ejecutar como Administrador
# Permitir Java saliente
New-NetFirewallRule -DisplayName "Getnet Agent Java" `
    -Direction Outbound `
    -Program "C:\Program Files\Java\bin\java.exe" `
    -Action Allow

# O permitir todas las conexiones salientes desde Java
netsh advfirewall firewall add rule name="Java Outbound" dir=out action=allow program="C:\Program Files\Java\bin\java.exe"
```

**Desde la GUI:**
1. Ir a "Configuración" > "Red e Internet" > "Firewall de Windows"
2. "Configuración avanzada"
3. "Reglas de salida" > "Nueva regla..."
4. Programas > Ruta a `java.exe`
5. Permitir la conexión

---

### 4. Windows Defender / Antivirus

**Problema:** Windows Defender puede bloquear el agente Java como amenaza.

**Solución A: Agregar excepción**

1. Abrir "Seguridad de Windows"
2. "Protección contra virus y amenazas"
3. "Administrar configuración" (bajo "Configuración de protección contra virus y amenazas")
4. Bajar hasta "Exclusiones"
5. "Agregar o quitar exclusiones"
6. Agregar carpeta donde está el agente Java

**Solución B: PowerShell**

```powershell
# Ejecutar como Administrador
Add-MpPreference -ExclusionPath "C:\ruta\completa\al\agente"
Add-MpPreference -ExclusionProcess "java.exe"
```

---

### 5. UAC (User Account Control)

**Problema:** UAC puede bloquear acceso a hardware (puertos COM).

**Solución: Deshabilitar UAC temporalmente (NO RECOMENDADO en producción)**

```powershell
# Ejecutar como Administrador
# Deshabilitar UAC
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name "EnableLUA" -Value 0
# Reiniciar necesario

# Re-habilitar UAC (más seguro)
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name "EnableLUA" -Value 1
```

**Mejor solución:** Ejecutar el agente como servicio de Windows con privilegios adecuados.

---

### 6. Hyper-V / Virtualización

**Problema:** Si Hyper-V está habilitado, puede interferir con acceso a puertos COM.

**Solución:**

```powershell
# Ejecutar como Administrador
# Verificar si Hyper-V está habilitado
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All

# Si está habilitado y causa problemas, deshabilitar:
Disable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
# Requiere reinicio
```

---

### 7. Verificar Acceso al Puerto COM

**Script de diagnóstico:**

```powershell
# Verificar que el puerto existe
Get-WmiObject -Class Win32_SerialPort | Where-Object { $_.DeviceID -like "*COM4*" }

# Verificar permisos
Get-Acl COM4: | Format-List

# Probar acceso directo (desde Java)
# Crear un pequeño test:
```

**Test Java simple:**

```java
import com.fazecast.jSerialComm.*;

public class TestCOM {
    public static void main(String[] args) {
        SerialPort[] ports = SerialPort.getCommPorts();
        System.out.println("Puertos COM disponibles:");
        for (SerialPort port : ports) {
            System.out.println("  " + port.getSystemPortName());
        }
        
        SerialPort port = SerialPort.getCommPort("COM4");
        if (port.openPort()) {
            System.out.println("✅ COM4 abierto correctamente");
            port.closePort();
        } else {
            System.out.println("❌ Error al abrir COM4: " + port.getLastErrorCode());
        }
    }
}
```

---

## 🚀 MEJOR PRÁCTICA: Ejecutar como Servicio de Windows

Para evitar problemas de permisos, ejecutar el agente como servicio de Windows:

**Opción 1: Usar NSSM (Non-Sucking Service Manager)**

1. Descargar NSSM: https://nssm.cc/download
2. Instalar servicio:

```cmd
# Ejecutar como Administrador
nssm install GetnetAgent "C:\Program Files\Java\bin\java.exe"
nssm set GetnetAgent AppParameters "-cp .;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar GetnetAgent"
nssm set GetnetAgent AppDirectory "C:\ruta\al\agente"
nssm set GetnetAgent DisplayName "Agente Getnet BIMBA"
nssm set GetnetAgent Description "Agente Java para procesamiento de pagos Getnet"
nssm set GetnetAgent Start SERVICE_AUTO_START
nssm start GetnetAgent
```

**Opción 2: Usar sc.exe (Windows Service Control)**

```cmd
# Crear servicio
sc create GetnetAgent binPath= "\"C:\Program Files\Java\bin\java.exe\" -cp .;json.jar;POSIntegradoGetnet.jar GetnetAgent" start= auto
sc description GetnetAgent "Agente Getnet BIMBA"
sc start GetnetAgent
```

---

## 🔍 DIAGNÓSTICO RÁPIDO

**Checklist:**

- [ ] ¿El agente se ejecuta como Administrador?
- [ ] ¿El puerto COM4 existe y está disponible?
- [ ] ¿El firewall permite conexiones salientes de Java?
- [ ] ¿Windows Defender no está bloqueando el agente?
- [ ] ¿El usuario tiene permisos en COM4?
- [ ] ¿El agente puede conectarse al backend (HTTPS)?

**Comandos de verificación:**

```powershell
# 1. Ver puertos COM
[System.IO.Ports.SerialPort]::getportnames()

# 2. Ver si Java puede acceder
java -version

# 3. Probar conexión al backend
Test-NetConnection -ComputerName stvaldivia.cl -Port 443

# 4. Ver logs del agente
Get-Content agent.log -Tail 50
```

---

## 📝 LOGS ÚTILES

**Windows Event Viewer:**
- Abrir "Visor de eventos" (eventvwr.msc)
- Windows Logs > Application
- Buscar errores relacionados con COM ports o Java

**Logs del Agente:**
- Revisar salida de consola del agente
- Buscar mensajes como:
  - "No se pudo abrir puerto serial COM4"
  - "Access denied"
  - "Permission denied"

---

## ⚠️ NOTAS IMPORTANTES

1. **NUNCA deshabilitar completamente el firewall o Windows Defender en producción**
2. **Usar excepciones específicas en lugar de deshabilitar protección**
3. **Ejecutar como servicio es más seguro que deshabilitar UAC**
4. **Probar cambios en ambiente de desarrollo antes de producción**

---

## 🔗 REFERENCIAS

- [Microsoft: Configurar firewall de Windows](https://support.microsoft.com/es-es/windows/c%C3%B3mo-abrir-un-puerto-en-el-firewall-de-windows-a81137e8-7d19-8c73-1c8c-9b0a0d8c0e5c)
- [jSerialComm: Troubleshooting](https://github.com/Fazecast/jSerialComm/wiki/Troubleshooting)
- [NSSM: Non-Sucking Service Manager](https://nssm.cc/)


