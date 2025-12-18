# 📋 Copiar Archivos a Windows - Guía Rápida

**Fecha:** 2025-12-18

---

## 🎯 PROBLEMA

Los archivos `.bat` existen en el repositorio pero no están en tu máquina Windows.

---

## ✅ SOLUCIÓN: Copiar Archivos Necesarios

### Archivos que DEBES copiar a Windows

Desde el repositorio (carpeta `getnet_agent/java/`) copia estos archivos a tu máquina Windows:

#### 1. Scripts Batch (`.bat`):
- ✅ `ejecutar.bat` - Ejecutar el agente
- ✅ `recompilar.bat` - Recompilar el agente
- ✅ `CONFIGURAR_VARIABLES.bat` - Configurar variables de entorno
- ✅ `INSTALAR_Y_EJECUTAR.bat` - Instalación completa (recomendado)

#### 2. Código Java:
- ✅ `GetnetAgent.java` - **IMPORTANTE**: Este se genera con `setup_getnet_agent_java.sh`

#### 3. JARs del SDK Getnet (carpeta `sdk/`):
- ✅ `sdk/POSIntegradoGetnet.jar`
- ✅ `sdk/jSerialComm-2.9.3.jar`
- ✅ `sdk/gson-2.10.1.jar`
- ⚠️ `json.jar` - Se descarga automáticamente o desde Maven

---

## 📦 MÉTODOS PARA COPIAR

### Método 1: Git Clone en Windows (Recomendado)

Si tienes Git en Windows:

```batch
# En Windows, abrir CMD o PowerShell
cd C:\
git clone <url-del-repositorio>
cd tickets_cursor_clean\getnet_agent\java
```

### Método 2: Carpeta Compartida de Red

1. **En Mac:**
   ```bash
   # Compartir carpeta
   # System Preferences → Sharing → File Sharing
   # O usar SMB
   ```

2. **En Windows:**
   ```batch
   # Mapear unidad de red
   net use Z: \\mac-ip\tickets_cursor_clean
   xcopy Z:\getnet_agent\java\*.bat C:\getnet_agent\java\
   ```

### Método 3: USB / Disco Externo

1. Copiar carpeta `getnet_agent/java/` a USB
2. Conectar USB a Windows
3. Copiar archivos a `C:\getnet_agent\java\`

### Método 4: SCP / WinSCP

Si la VM tiene SSH habilitado:

```bash
# Desde Mac
scp -r getnet_agent/java/* usuario@windows-vm:/ruta/destino/
```

---

## 🚀 PASOS EN WINDOWS

Una vez que tengas los archivos en Windows:

### Paso 1: Crear directorio

```batch
mkdir C:\getnet_agent\java
cd C:\getnet_agent\java
```

### Paso 2: Copiar archivos

Copia todos los archivos listados arriba a este directorio.

### Paso 3: Generar GetnetAgent.java (si no existe)

**Opción A: Si tienes el script `setup_getnet_agent_java.sh`:**

```bash
# En Git Bash o WSL en Windows
cd C:\getnet_agent\java
REGISTER_ID="1" AGENT_API_KEY="tu_api_key_aqui" bash setup_getnet_agent_java.sh
```

**Opción B: Si ya tienes `GetnetAgent.java` copiado:**

No necesitas hacer nada, ya está listo.

### Paso 4: Ejecutar instalación

```batch
cd C:\getnet_agent\java
INSTALAR_Y_EJECUTAR.bat
```

Este script:
- ✅ Verifica Java
- ✅ Descarga JARs faltantes
- ✅ Compila el agente
- ✅ Configura variables
- ✅ Inicia el agente

---

## 🔍 VERIFICAR QUE TODO ESTÁ PRESENTE

En Windows, verifica que tengas estos archivos:

```batch
cd C:\getnet_agent\java
dir
```

Debes ver:
- ✅ `ejecutar.bat`
- ✅ `recompilar.bat`
- ✅ `CONFIGURAR_VARIABLES.bat`
- ✅ `GetnetAgent.java`
- ✅ `POSIntegradoGetnet.jar` (o en `sdk/`)
- ✅ `jSerialComm-2.9.3.jar` (o en `sdk/`)
- ✅ `gson-2.10.1.jar` (o en `sdk/`)

---

## ⚠️ IMPORTANTE: JARs del SDK

Los JARs deben estar en el mismo directorio que los `.bat`, o ajustar el `CLASSPATH` en los scripts.

**Si los JARs están en `sdk/`, cópialos al directorio principal:**

```batch
copy sdk\*.jar .
```

O edita `ejecutar.bat` y `recompilar.bat` para incluir `sdk/` en el classpath.

---

## ✅ DESPUÉS DE COPIAR

Una vez que todos los archivos estén en Windows:

```batch
cd C:\getnet_agent\java

# Configurar variables
CONFIGURAR_VARIABLES.bat

# Recompilar
recompilar.bat

# Ejecutar
ejecutar.bat
```

---

## 🆘 SI AÚN FALTAN ARCHIVOS

**Lista completa de archivos mínimos necesarios:**

```
C:\getnet_agent\java\
├── ejecutar.bat                    ← REQUERIDO
├── recompilar.bat                  ← REQUERIDO
├── CONFIGURAR_VARIABLES.bat        ← OPCIONAL (puedes configurar manualmente)
├── GetnetAgent.java                ← REQUERIDO
├── POSIntegradoGetnet.jar          ← REQUERIDO
├── jSerialComm-2.9.3.jar          ← REQUERIDO
├── gson-2.10.1.jar                ← REQUERIDO
└── json.jar                        ← Se descarga automáticamente
```

**Si falta alguno:**
- Los `.bat` → Cópiarlos desde el repositorio
- `GetnetAgent.java` → Generarlo con `setup_getnet_agent_java.sh`
- Los JARs → Copiarlos desde el SDK Getnet o desde `sdk/`

---

## 📞 SIGUIENTE PASO

Una vez que tengas todos los archivos, ejecuta:

```batch
cd C:\getnet_agent\java
INSTALAR_Y_EJECUTAR.bat
```

Este script verificará todo y te guiará paso a paso.

