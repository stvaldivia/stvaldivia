# ✅ Actualización: Puerto COM3

**Fecha:** 2025-12-18

---

## 🔧 CAMBIO REALIZADO

El terminal Getnet está configurado para usar **COM3** (en lugar de COM4).

**Configuración:**
- Puerto: **COM3**
- Baudrate: **115200**
- Timeout: 30000 ms

---

## ✅ ACTUALIZACIONES APLICADAS

1. **Base de datos actualizada:**
   - `pos_registers.provider_config` para register_id=1 (TEST001)
   - Puerto cambiado de COM4 a COM3

2. **Código actualizado:**
   - `getnet_agent/java/setup_getnet_agent_java.sh` - Valor por defecto actualizado
   - `app/blueprints/pos/views/payment_intents.py` - Fallback actualizado
   - `app/templates/admin/registers/form.html` - Ejemplos actualizados

---

## 📋 VERIFICACIÓN

Para verificar que la configuración es correcta:

```sql
SELECT id, code, name, provider_config 
FROM pos_registers 
WHERE id = 1 OR code = 'TEST001';
```

Debería mostrar:
```json
{
  "GETNET": {
    "mode": "serial",
    "port": "COM3",
    "baudrate": 115200,
    "timeout_ms": 30000
  }
}
```

---

## 🔄 PRÓXIMOS PASOS

1. **Si el agente Java ya está corriendo:**
   - El agente carga la configuración desde el backend al iniciar
   - Reinicia el agente para que use COM3
   - O espera a que se reinicie automáticamente

2. **Si el agente Java aún no está corriendo:**
   - La configuración se cargará automáticamente desde el backend
   - Usará COM3 por defecto

---

## ✅ ESTADO

- ✅ Base de datos: COM3 configurado
- ✅ Código: Valores por defecto actualizados
- ✅ Agente: Usará COM3 al cargar configuración del backend

---

## 📝 NOTA

El agente Java carga la configuración dinámicamente desde el endpoint:
`GET /caja/api/payment/agent/config?register_id=1`

Por lo tanto, **no necesita recompilarse** - solo necesita reiniciarse para que cargue la nueva configuración.


