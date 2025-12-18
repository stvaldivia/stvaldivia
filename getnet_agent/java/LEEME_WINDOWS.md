# 🪟 Guía Rápida: Agente Getnet en Windows

**Fecha:** 2025-12-18

---

## 🚀 INICIO RÁPIDO

### 1. Primera vez (Configuración inicial)

1. **Configurar variables de entorno:**
   ```batch
   configurar_variables.bat
   ```
   O manualmente:
   ```batch
   set REGISTER_ID=1
   set BASE_URL=https://stvaldivia.cl
   set AGENT_API_KEY=bimba_getnet_prod_xxxxxxxxxxxxxxxxxxxxxxxx
   ```

2. **Recompilar el agente:**
   ```batch
   recompilar.bat
   ```

3. **Ejecutar el agente:**
   ```batch
   ejecutar.bat
   ```

---

### 2. Uso diario

```batch
# Opción 1: Usar script de configuración + ejecución
call config_env.bat
ejecutar.bat

# Opción 2: Configurar manualmente
set REGISTER_ID=1
set AGENT_API_KEY=bimba_getnet_prod_xxxxxxxxxxxxxxxxxxxxxxxx
ejecutar.bat
```

---

## 📋 ARCHIVOS INCLUIDOS

- **`recompilar.bat`** - Recompila el agente Java
- **`ejecutar.bat`** - Ejecuta el agente
- **`configurar_variables.bat`** - Configura variables de entorno
- **`config_env.bat`** - Generado automáticamente con las variables

---

## ✅ VERIFICACIÓN

Cuando el agente está corriendo correctamente, deberías ver:

```
🔌 Inicializando conexión Getnet...
   Puerto: COM4
   Baudrate: 115200
✅ Conexión Getnet OK

💓 Heartbeat enviado: OK

🧾 Intent recibido: <uuid> amount=100.0 CLP
💳 Procesando pago Getnet...
📄 Respuesta JSON del SDK: {...}
✅ Pago aprobado (ResponseCode=0)
✅ Resultado reportado: intent=<uuid> status=APPROVED
```

---

## 🐛 SOLUCIÓN DE PROBLEMAS

### Error: "Java no está instalado"
**Solución:** Instala Java JDK 11 o superior desde:
- https://adoptium.net/
- O https://www.oracle.com/java/technologies/downloads/

### Error: "AGENT_API_KEY no está definido"
**Solución:** Configura la variable antes de ejecutar:
```batch
set AGENT_API_KEY=bimba_getnet_prod_xxxxxxxxxxxxxxxxxxxxxxxx
ejecutar.bat
```

### Error: "No se encuentra json.jar" (o otros JARs)
**Solución:** Asegúrate de que todos los JARs estén en el directorio:
- `json.jar`
- `POSIntegradoGetnet.jar`
- `jSerialComm-2.9.3.jar`
- `gson-2.10.1.jar`

### Error: "Connection refused" o errores de red
**Solución:** Verifica que:
1. El servidor `stvaldivia.cl` esté accesible
2. No haya firewall bloqueando las conexiones
3. El `BASE_URL` sea correcto

### Error: "Puerto COM4 no disponible"
**Solución:** 
1. Verifica que el terminal Getnet esté conectado
2. Verifica el número de puerto COM (puede ser COM3, COM5, etc.)
3. Verifica que no haya otro programa usando el puerto
4. Prueba ejecutar como Administrador

---

## 🔄 REINICIO DESPUÉS DE CAMBIOS

Si cambiaste el código del agente o la configuración:

1. Detener el agente (Ctrl+C)
2. Recompilar: `recompilar.bat`
3. Reiniciar: `ejecutar.bat`

---

## 📞 SOPORTE

Si después de seguir estos pasos sigue sin funcionar:

1. **Revisa los logs del agente** (la consola donde corre)
2. **Revisa los logs del backend:**
   ```bash
   ssh stvaldivia
   tail -f /var/www/stvaldivia/logs/error.log | grep PAYMENT_INTENT
   ```
3. **Revisa el panel de administración:**
   - Ve a: https://stvaldivia.cl/admin
   - Revisa la tarjeta "Estado Getnet (CAJA TEST)"
   - Verifica que el agente esté online y Getnet esté OK

---

## 📝 NOTAS

- El agente debe correr **continuamente** mientras la caja esté operativa
- El agente se conecta al servidor cada 800ms para consultar pagos pendientes
- El agente envía un heartbeat cada 30 segundos
- Si el agente se detiene, los pagos con tarjeta no funcionarán

---

## 🎯 PRÓXIMOS PASOS

1. ✅ Configurar variables de entorno
2. ✅ Recompilar el agente
3. ✅ Ejecutar el agente
4. ✅ Verificar que está online (panel admin)
5. ✅ Hacer una venta de prueba


