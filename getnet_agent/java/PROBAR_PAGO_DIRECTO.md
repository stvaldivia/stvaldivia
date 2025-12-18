# 🧪 Cómo Probar el Script de Pago Directo

**Fecha:** 2025-12-18

---

## ⚠️ IMPORTANTE

Este script **DEBE ejecutarse en Windows** donde está conectado el terminal Getnet (puerto COM3).

No se puede ejecutar desde Mac/Linux porque:
- Requiere acceso al puerto COM3
- Necesita el terminal Getnet físicamente conectado
- Requiere los JARs del SDK Getnet

---

## 📋 PREREQUISITOS

1. ✅ **Máquina Windows** con el terminal Getnet conectado
2. ✅ **Java JDK 11+** instalado
3. ✅ **JARs del SDK Getnet** en el directorio:
   - `POSIntegradoGetnet.jar`
   - `jSerialComm-2.9.3.jar`
   - `gson-2.10.1.jar`
   - `json.jar`
4. ✅ **Terminal Getnet** conectado en COM3 y encendido

---

## 🚀 PASOS PARA PROBAR

### 1. Preparar el entorno

**En Windows (máquina CAJA TEST):**

```batch
cd C:\ruta\al\agente\getnet_agent\java
```

Asegúrate de tener estos archivos:
- `pago_directo.java`
- `pago_directo.bat`
- `POSIntegradoGetnet.jar`
- `jSerialComm-2.9.3.jar`
- `gson-2.10.1.jar`
- `json.jar`

### 2. Compilar (si es necesario)

El script `pago_directo.bat` compila automáticamente, pero puedes hacerlo manualmente:

```batch
javac -cp .;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar pago_directo.java
```

### 3. Ejecutar prueba con monto pequeño

**⚠️ Recomendación:** Empieza con un monto pequeño ($100-$500 CLP) para pruebas.

```batch
pago_directo.bat 100
```

O manualmente:
```batch
java -cp .;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar pago_directo 100 COM3
```

### 4. Seguir las instrucciones

Cuando ejecutes el script:

1. **Verás mensajes en consola:**
   ```
   [1/4] Abriendo puerto COM3...
   ✅ Puerto abierto
   [2/4] Inicializando SDK Getnet...
   ✅ SDK inicializado
   [3/4] Preparando venta...
   Monto: $100 CLP
   ✅ Request preparado
   ```

2. **Cuando llegue a [4/4]:**
   ```
   [4/4] Procesando pago en terminal Getnet...
   (El cliente debe insertar/pasar la tarjeta en el terminal)
   ```
   
3. **En este punto:**
   - El terminal Getnet mostrará el monto
   - El cliente debe insertar o pasar la tarjeta
   - El terminal procesará el pago
   - El script recibirá la respuesta

4. **Resultado esperado:**
   - ✅ **Aprobado:** Verás código de autorización
   - ❌ **Rechazado:** Verás mensaje de error

---

## 📊 SALIDA ESPERADA

### Si el pago es aprobado:

```
========================================
  ✅ PAGO APROBADO
========================================
Monto: $100 CLP
Código de autorización: 532976

⚠️  NOTA: Este pago NO fue registrado en el TPV.
   Es una transacción directa con Getnet únicamente.
```

### Si el pago es rechazado:

```
========================================
  ❌ PAGO RECHAZADO
========================================
Mensaje: Transacción rechazada
```

### Si hay error de conexión:

```
❌ Error al abrir puerto: [código de error]
```

O:

```
❌ ERROR: Puerto COM3 no encontrado
```

---

## 🔍 TROUBLESHOOTING

### Error: "Puerto COM3 no encontrado"

**Solución:**
1. Verifica que el terminal Getnet esté conectado
2. Revisa el Administrador de dispositivos
3. Verifica qué puerto COM está usando:
   ```powershell
   Get-WmiObject Win32_SerialPort | Select-Object Name, DeviceID
   ```
4. Si usa otro puerto, ejecuta:
   ```batch
   pago_directo.bat 100 COM4
   ```
   (reemplaza COM4 con el puerto correcto)

### Error: "Puerto está siendo usado"

**Solución:**
1. Cierra cualquier otro programa que use COM3
2. Si el agente Java está corriendo, deténlo temporalmente:
   ```batch
   taskkill /F /IM java.exe
   ```
3. Ejecuta el script de nuevo

### Error: "SDK no devolvió respuesta"

**Posibles causas:**
- El terminal no está encendido
- El terminal no está respondiendo
- El cable está desconectado
- El baudrate no es correcto

**Solución:**
1. Verifica que el terminal esté encendido
2. Desconecta y reconecta el cable
3. Reinicia el terminal si tiene botón de reset

### Error: "No se encontró método para procesar venta"

**Solución:**
- El SDK puede tener un método diferente
- Revisa la documentación del SDK Getnet
- Puede requerir configuración adicional del SDK

---

## ✅ VERIFICACIÓN EXITOSA

Si el script funciona correctamente, deberías ver:

1. ✅ Puerto COM3 abierto
2. ✅ SDK Getnet inicializado
3. ✅ Terminal muestra el monto
4. ✅ Cliente puede pasar la tarjeta
5. ✅ Resultado del pago (aprobado/rechazado)

---

## 📝 NOTAS IMPORTANTES

1. **Este pago NO se registra en el TPV:**
   - Es una transacción directa con Getnet
   - No aparece en el sistema
   - No se genera ticket
   - No se actualiza inventario

2. **Solo para pruebas:**
   - Usa montos pequeños
   - Documenta lo que haces
   - No uses para ventas reales

3. **Si necesitas registrar la venta:**
   - Usa siempre el flujo normal del TPV
   - El agente Java procesará automáticamente

---

## 🎯 PRÓXIMOS PASOS

Después de probar exitosamente:

1. ✅ Verifica que el terminal responde correctamente
2. ✅ Verifica que los códigos de autorización son válidos
3. ✅ Usa el flujo normal del TPV para ventas reales

---

## 📞 SI ALGO FALLA

1. Revisa los mensajes de error en la consola
2. Verifica que el terminal esté conectado y encendido
3. Verifica que el puerto COM sea correcto
4. Revisa la documentación del SDK Getnet si hay errores específicos


