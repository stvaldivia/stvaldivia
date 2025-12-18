# 📊 Explicación del Estado Getnet (CAJA TEST)

**Fecha:** 2025-12-18

---

## 🎯 ¿En qué se basa el estado?

El estado de Getnet se calcula en el endpoint `/admin/api/getnet/status` y considera **3 factores principales**:

### 1. 🔍 Existencia de Agente

- Debe existir un registro en la tabla `payment_agents` con `register_id='1'`
- Si no existe ningún registro → **ERROR**

### 2. ⏱️ Heartbeat Reciente

El agente Java debe enviar un "heartbeat" (latido) cada 30 segundos al backend.

- **OK**: heartbeat < 60 segundos
- **WARN**: heartbeat entre 60-300 segundos (1-5 minutos)
- **ERROR**: heartbeat > 300 segundos (5 minutos)

### 3. 🎯 Estado Getnet Reportado

El agente Java verifica la conexión con el terminal Getnet y reporta:

- **`OK`**: Terminal conectado y respondiendo
- **`UNKNOWN`**: Puerto abierto pero no se puede verificar terminal
- **`ERROR`**: Error de conexión o terminal no responde

---

## ✅ Estado Final

El `overall_status` se determina así:

```python
if not agent:
    overall_status = "ERROR"  # Sin agente registrado
elif seconds_since_heartbeat > 300:
    overall_status = "ERROR"  # Heartbeat muy antiguo (>5 min)
elif 60 < seconds_since_heartbeat <= 300:
    overall_status = "WARN"   # Heartbeat antiguo (1-5 min)
elif agent.last_getnet_status == 'ERROR':
    overall_status = "ERROR"  # Terminal Getnet con error
elif agent.last_getnet_status == 'UNKNOWN':
    overall_status = "WARN"   # Estado desconocido
elif seconds_since_heartbeat <= 60 and agent.last_getnet_status == 'OK':
    overall_status = "OK"     # Todo bien ✅
else:
    overall_status = "WARN"   # Estado intermedio
```

---

## ❌ Problema Actual

**Último heartbeat:** Hace ~10546 segundos (casi 3 horas)

**Causa:** El agente Java no está enviando heartbeats. Debe enviarlos cada 30 segundos.

**Por qué dice "desconectado":**
- `seconds_since_heartbeat > 300` → **ERROR**

---

## 🔧 Solución

### Verificar si el agente está corriendo en Windows

**En la máquina Windows (CAJA TEST):**

1. **Verificar procesos Java:**
   ```cmd
   tasklist | findstr java
   ```
   Deberías ver un proceso `java.exe` ejecutando `GetnetAgent`.

2. **Si no está corriendo, iniciarlo:**
   ```cmd
   cd C:\Users\<usuario>\getnet_agent\java
   .\ejecutar.bat
   ```
   O usar `INSTALAR_Y_EJECUTAR.bat` si es la primera vez.

3. **Verificar logs del agente:**
   Deberías ver en la consola cada 30 segundos:
   ```
   💓 Heartbeat enviado: Getnet=OK (Pinpad conectado y listo)
   ```

4. **Verificar conectividad:**
   El agente debe poder conectarse a `https://stvaldivia.cl/caja/api/payment/agent/heartbeat`

---

## 📋 Checklist de Verificación

- [ ] Agente Java está corriendo en Windows
- [ ] Agente puede conectarse a `https://stvaldivia.cl`
- [ ] Terminal Getnet está conectado físicamente a COM3
- [ ] Heartbeats se envían cada 30 segundos
- [ ] `last_getnet_status` es `'OK'` en la base de datos

---

## 🔍 Consultar Estado en Base de Datos

```sql
SELECT 
    register_id,
    agent_name,
    last_heartbeat,
    last_getnet_status,
    last_getnet_message,
    EXTRACT(EPOCH FROM (NOW() - last_heartbeat))::int as seconds_ago
FROM payment_agents 
WHERE register_id='1' 
ORDER BY last_heartbeat DESC 
LIMIT 1;
```

**Interpretación:**
- `seconds_ago < 60` → Agente activo ✅
- `seconds_ago 60-300` → Advertencia ⚠️
- `seconds_ago > 300` → Agente desconectado ❌

---

## 💡 Notas Importantes

1. **El agente debe estar corriendo todo el tiempo** para que el estado se mantenga actualizado.

2. **El heartbeat incluye el estado de Getnet**, por lo que si el terminal está desconectado, el estado será `ERROR` incluso si el agente está corriendo.

3. **El estado se actualiza cada 10 segundos** en el dashboard admin, pero depende de que haya heartbeats recientes.

4. **Si el agente se detiene**, el estado pasará a `ERROR` después de 5 minutos sin heartbeat.

---

## 📞 Troubleshooting

**"Siempre dice desconectado"**:
1. Verifica que el agente Java esté corriendo
2. Verifica que pueda conectarse al backend
3. Verifica los logs del agente para errores
4. Verifica que `AGENT_API_KEY` sea correcto

**"Dice WARN aunque está conectado"**:
- Heartbeat tiene entre 60-300 segundos (puede ser normal si el agente acaba de reiniciarse)
- `getnet_status` es `UNKNOWN` (verifica conexión serial)

**"Dice OK pero no procesa pagos"**:
- El terminal puede estar conectado pero no responder correctamente
- Verifica logs del agente durante una transacción
- Prueba con `pago_directo.bat` para verificar el terminal


