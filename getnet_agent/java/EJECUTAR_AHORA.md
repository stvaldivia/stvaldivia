# 🚀 EJECUTAR AHORA - Pasos Simplificados

**Fecha:** 2025-12-18

---

## ⚠️ IMPORTANTE

Los scripts `.bat` **DEBEN ejecutarse en Windows** (máquina CAJA TEST).

No se pueden ejecutar desde Mac/Linux porque son scripts batch de Windows.

---

## 📦 ARCHIVOS LISTOS

✅ **Backend:** Actualizado y desplegado en producción  
✅ **Código Java:** Actualizado con parseo correcto de JSON  
✅ **Scripts Windows:** Creados y listos para usar  

---

## 🪟 EN WINDOWS (CAJA TEST) - HAZ ESTO:

### Paso 1: Preparar archivos

Copia estos archivos al directorio donde quieras tener el agente en Windows:

**Desde este repositorio:**
- `getnet_agent/java/INSTALAR_Y_EJECUTAR.bat`
- `getnet_agent/java/recompilar.bat`
- `getnet_agent/java/ejecutar.bat`
- `getnet_agent/java/CONFIGURAR_VARIABLES.bat`
- `getnet_agent/java/LEEME_WINDOWS.md`

**JARs del SDK Getnet:**
- `POSIntegradoGetnet.jar`
- `jSerialComm-2.9.3.jar`
- `gson-2.10.1.jar`

**Código Java (generar con setup_getnet_agent_java.sh):**
- `GetnetAgent.java`

### Paso 2: Generar GetnetAgent.java

**Opción A: En Mac/Linux (antes de copiar a Windows):**
```bash
cd getnet_agent/java
REGISTER_ID="1" AGENT_API_KEY="TU_API_KEY_AQUI" bash setup_getnet_agent_java.sh
```

**Opción B: En Windows (usar WSL o Git Bash):**
```bash
# En WSL o Git Bash en Windows
cd /ruta/al/directorio/del/agente
REGISTER_ID="1" AGENT_API_KEY="TU_API_KEY_AQUI" bash setup_getnet_agent_java.sh
```

### Paso 3: En Windows, ejecutar

**Abrir CMD o PowerShell en Windows y ejecutar:**

```batch
cd C:\ruta\al\directorio\del\agente
INSTALAR_Y_EJECUTAR.bat
```

---

## 🔑 CONFIGURAR AGENT_API_KEY

El `AGENT_API_KEY` debe ser **el mismo** en el servidor y en el agente.

**Para encontrarlo en el servidor:**
```bash
ssh stvaldivia
sudo systemctl show stvaldivia.service | grep AGENT_API_KEY
# O
sudo cat /etc/systemd/system/stvaldivia.service | grep AGENT_API_KEY
```

**O configurarlo manualmente en Windows:**
```batch
set AGENT_API_KEY=bimba_getnet_prod_xxxxxxxxxxxxxxxxxxxxxxxx
```

---

## ✅ VERIFICACIÓN

Una vez ejecutando, deberías ver en la consola:

```
🔌 Inicializando conexión Getnet...
   Puerto: COM4
   Baudrate: 115200
✅ Conexión Getnet OK

💓 Heartbeat enviado: OK
```

Y en https://stvaldivia.cl/admin:
- Badge verde "OK" en "Estado Getnet (CAJA TEST)"

---

## 🎯 RESUMEN RÁPIDO

1. ✅ Backend listo (ya desplegado)
2. ✅ Código Java listo (con parseo JSON)
3. ⏳ **FALTA:** Ejecutar scripts en Windows

**Próximo paso:** Ir a la máquina Windows (CAJA TEST) y ejecutar `INSTALAR_Y_EJECUTAR.bat`


