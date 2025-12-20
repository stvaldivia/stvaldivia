# 📖 Cómo Usar la Rama `base-para-cajas`

**Fecha:** 2025-12-18

---

## 🎯 ¿Qué es esta rama?

La rama `base-para-cajas` contiene **todos los archivos** que necesitas descargar en las cajas Windows para instalar y ejecutar el agente Getnet.

---

## 🖥️ ¿Dónde se ejecuta?

### ❌ NO en tu Mac (donde estás trabajando ahora)
Los comandos git que mencioné son solo para referencia. No necesitas ejecutarlos en tu terminal Mac.

### ✅ SÍ en las máquinas Windows (las cajas)
Esas instrucciones son para cuando vayas a configurar las cajas Windows.

---

## 📋 Flujo Completo

### Paso 1: Trabajo en Mac (lo que ya hiciste)
```
✅ Creaste la rama base-para-cajas
✅ Agregaste todos los archivos necesarios
✅ Hiciste commit y push a GitHub
```

### Paso 2: En la Máquina Windows (caja) - Cuando llegue el momento

**Opción A: Si la máquina Windows tiene Git instalado:**

1. Abrir CMD o PowerShell en Windows
2. Ir a donde quieras instalar el agente (ejemplo: `C:\`)
3. Clonar la rama:
   ```batch
   git clone -b base-para-cajas https://github.com/stvaldivia/stvaldivia.git
   cd stvaldivia\getnet_agent\java
   ```
4. Instalar y ejecutar:
   ```batch
   INSTALAR_Y_EJECUTAR.bat
   ```

**Opción B: Si la máquina Windows NO tiene Git:**

1. Desde tu Mac (o cualquier máquina con Git), descargar los archivos:
   ```bash
   git clone -b base-para-cajas https://github.com/stvaldivia/stvaldivia.git
   # Luego copiar la carpeta getnet_agent/java/ a USB o carpeta compartida
   ```

2. En Windows, copiar los archivos desde USB/carpeta compartida a `C:\getnet_agent\java\`

3. En Windows, ejecutar:
   ```batch
   cd C:\getnet_agent\java
   INSTALAR_Y_EJECUTAR.bat
   ```

**Opción C: Descargar ZIP desde GitHub (más fácil):**

1. Ir a GitHub: https://github.com/stvaldivia/stvaldivia
2. Cambiar a la rama `base-para-cajas`
3. Click en "Code" → "Download ZIP"
4. Extraer el ZIP en Windows
5. Ir a `stvaldivia-getnet_agent-java/getnet_agent/java/`
6. Ejecutar `INSTALAR_Y_EJECUTAR.bat`

---

## 🎯 Resumen Simple

**¿Qué hacer AHORA?**
- ✅ Nada. La rama ya está creada en GitHub con todos los archivos.

**¿Qué hacer cuando vayas a configurar una caja Windows?**
- Descargar los archivos desde GitHub (git clone, ZIP, o copiar manualmente)
- Ejecutar `INSTALAR_Y_EJECUTAR.bat` en Windows

---

## ❓ Preguntas Frecuentes

### ¿Puedo ejecutar esos comandos git en Mac?
Sí, pero no tiene sentido porque:
- Los scripts `.bat` son para Windows, no funcionan en Mac
- El agente Java debe ejecutarse en la máquina Windows donde está el terminal Getnet

### ¿Los archivos ya están en GitHub?
Sí, están en la rama `base-para-cajas`. Puedes verlos en:
https://github.com/stvaldivia/stvaldivia/tree/base-para-cajas/getnet_agent/java

### ¿Cuándo debo usar esta rama?
Cuando vayas a instalar/configurar el agente Getnet en una máquina Windows (caja).

---

## ✅ Estado Actual

- ✅ Rama `base-para-cajas` creada
- ✅ Archivos agregados y commiteados
- ✅ Push a GitHub completado
- ⏳ Esperando: Instalación en máquinas Windows (cuando sea necesario)



