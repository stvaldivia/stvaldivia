# 🔧 Recompilar Agente Java Getnet

**IMPORTANTE:** Ejecuta estos pasos en la máquina Windows (CAJA TEST) donde corre el agente.

---

## 📋 PASOS

### 1. Detener el agente actual (si está corriendo)
```bash
# Buscar el proceso Java del agente
tasklist | findstr java

# Si encuentras el proceso, detenerlo:
taskkill /F /IM java.exe
# O si está en un terminal, presiona Ctrl+C
```

### 2. Ir al directorio del agente
```bash
cd C:\Users\<tu_usuario>\getnet_agent\java
# O donde hayas instalado el agente
```

### 3. Recompilar
```bash
.\build.sh
```

Si `build.sh` no funciona en Windows, usa:
```bash
javac -cp .;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar GetnetAgent.java
```

### 4. Reiniciar el agente
```bash
.\run.sh
```

O si `run.sh` no funciona:
```bash
java -cp .;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar GetnetAgent
```

---

## ✅ VERIFICACIÓN

Después de reiniciar, deberías ver en los logs:
- `🔌 Inicializando conexión Getnet...`
- `✅ Conexión Getnet OK`
- `💓 Heartbeat enviado: OK`

Y cuando proceses un pago:
- `💳 Procesando pago Getnet...`
- `📄 Respuesta JSON del SDK: ...`
- `✅ Pago aprobado (ResponseCode=0)`
- `✅ Resultado reportado: intent=... status=APPROVED`

---

## 🐛 SI HAY ERRORES DE COMPILACIÓN

1. Verifica que todos los JARs estén presentes:
   - `json.jar`
   - `POSIntegradoGetnet.jar`
   - `jSerialComm-2.9.3.jar`
   - `gson-2.10.1.jar`

2. Verifica que Java esté instalado:
   ```bash
   java -version
   javac -version
   ```

3. Si falta algún JAR, descárgalo o cópialo desde el SDK de Getnet.

---

## 📞 SOPORTE

Si después de recompilar sigue sin funcionar:
1. Revisa los logs del agente
2. Revisa los logs del backend: `tail -f /var/www/stvaldivia/logs/error.log | grep PAYMENT_INTENT`
3. Revisa la consola del navegador (F12) cuando intentas hacer una venta


