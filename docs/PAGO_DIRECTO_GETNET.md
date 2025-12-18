# 💳 Pago Directo con Getnet (Sin TPV)

**Fecha:** 2025-12-18

---

## ⚠️ ADVERTENCIA IMPORTANTE

Este script procesa pagos **directamente con Getnet**, **SIN pasar por el TPV**.

**Esto significa:**
- ✅ El pago se procesa en Getnet (se cobra en la tarjeta)
- ❌ NO se crea una venta en el sistema
- ❌ NO se registra en inventario
- ❌ NO se genera ticket
- ❌ NO se registra en contabilidad

**Usar SOLO para:**
- 🔧 Pruebas técnicas
- 🔍 Verificar que Getnet funciona
- 🧪 Testing del terminal

**NO usar para:**
- ❌ Ventas reales (perderás el registro)
- ❌ Operaciones de producción

---

## 🎯 CUANDO USAR ESTO

### Casos de Uso Válidos:

1. **Verificar que el terminal funciona:**
   - Probar con montos pequeños ($100, $500)
   - Verificar que el SDK responde correctamente
   - Diagnosticar problemas de conexión

2. **Testing técnico:**
   - Probar diferentes montos
   - Verificar códigos de autorización
   - Probar diferentes tipos de tarjeta

3. **Diagnóstico:**
   - Si el TPV no funciona, verificar si es problema de Getnet o del sistema
   - Aislar problemas de comunicación

---

## 📋 ARCHIVOS

- `getnet_agent/java/pago_directo.java` - Código fuente
- `getnet_agent/java/pago_directo.bat` - Script para Windows

---

## 🚀 USO

### En Windows:

**Opción 1: Script batch (Recomendado)**
```batch
cd C:\ruta\al\agente\getnet_agent\java
pago_directo.bat 1000
```

**Opción 2: Manual**
```batch
javac -cp .;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar pago_directo.java
java -cp .;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar pago_directo 1000 COM3
```

**Parámetros:**
- `<monto>` - Monto en pesos CLP (sin decimales)
  - Ejemplo: `1000` = $1,000 CLP
  - Ejemplo: `100` = $100 CLP
- `[puerto]` - Puerto COM (opcional, default: COM3)

---

## 📊 EJEMPLOS

### Ejemplo 1: Pago de $1,000 CLP
```batch
pago_directo.bat 1000
```

### Ejemplo 2: Pago de $5,000 CLP en COM3
```batch
pago_directo.bat 5000 COM3
```

### Ejemplo 3: Pago de $100 CLP (prueba pequeña)
```batch
pago_directo.bat 100
```

---

## 🔄 FLUJO

1. **Abrir puerto COM3** (115200 bauds)
2. **Inicializar SDK Getnet**
3. **Crear SaleRequest** con el monto
4. **Procesar pago** en el terminal
   - El cliente inserta/pasa la tarjeta
   - El terminal procesa
   - El SDK recibe respuesta
5. **Mostrar resultado:**
   - ✅ Aprobado: Muestra código de autorización
   - ❌ Rechazado: Muestra mensaje de error

---

## 📝 SALIDA ESPERADA

### Pago Aprobado:
```
========================================
  ✅ PAGO APROBADO
========================================
Monto: $1000 CLP
Código de autorización: 532976

⚠️  NOTA: Este pago NO fue registrado en el TPV.
   Es una transacción directa con Getnet únicamente.
```

### Pago Rechazado:
```
========================================
  ❌ PAGO RECHAZADO
========================================
Mensaje: Transacción rechazada
```

---

## ⚠️ DIFERENCIAS CON EL FLUJO NORMAL

### Flujo Normal (TPV):
```
Usuario → TPV → Backend → Agente Java → Getnet → Backend → TPV → Ticket
```
- ✅ Se registra en base de datos
- ✅ Se actualiza inventario
- ✅ Se genera ticket
- ✅ Se registra en contabilidad

### Flujo Directo (Este Script):
```
Script Java → Getnet → Resultado
```
- ✅ Se procesa en Getnet (se cobra)
- ❌ NO se registra en base de datos
- ❌ NO se actualiza inventario
- ❌ NO se genera ticket
- ❌ NO se registra en contabilidad

---

## 🔒 RECOMENDACIONES

1. **Solo para pruebas:**
   - Usa montos pequeños ($100-$1000)
   - Prueba en horarios de baja actividad
   - Documenta lo que haces

2. **No usar en producción:**
   - No proceses ventas reales con esto
   - Siempre usa el flujo normal del TPV

3. **Reconciliación:**
   - Si usas esto, registra manualmente la transacción
   - O cancela la transacción en Getnet si es necesario

---

## 📚 REFERENCIAS

- SDK Getnet: `POSIntegradoGetnet.jar`
- Documentación Getnet: Ver documentación del SDK
- Flujo normal: `docs/RESUMEN_IMPLEMENTACION_GETNET.md`

---

## ✅ RESUMEN

**¿Puedo hacer pagos directos desde Java?**
- ✅ **SÍ**, técnicamente puedes hacerlo
- ⚠️ Pero **NO se registran** en el sistema TPV
- 🎯 Úsalo **solo para pruebas**, no para ventas reales

**Para ventas reales:**
- ✅ Usa siempre el flujo normal del TPV
- ✅ El agente Java procesará el pago automáticamente
- ✅ Todo se registrará correctamente


