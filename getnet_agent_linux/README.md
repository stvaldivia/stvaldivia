# Agente Getnet Linux

Servicio local para comunicación con POS Getnet en tótems de autoatención Linux.

## Descripción

Este agente corre en cada tótem Linux y proporciona una API HTTP local (`http://127.0.0.1:7777`) para que el navegador de la caja pueda solicitar pagos al POS Getnet conectado por USB.

La negociación de pago es **totalmente local**: el servidor central NO habla con Getnet, solo el tótem por USB.

## Estructura del Proyecto

```
getnet_agent_linux/
├── app/
│   ├── __init__.py
│   ├── main.py          # Servidor FastAPI con endpoints
│   ├── getnet.py        # Lógica de comunicación con POS Getnet
│   └── config.py        # Configuración desde variables de entorno
├── tests/
│   └── test_main.py     # Tests básicos
├── requirements.txt     # Dependencias Python
├── run_agent.sh         # Script para ejecutar el agente
├── bimba-getnet-agent.service  # Archivo systemd (ejemplo)
├── .env.example         # Ejemplo de variables de entorno
└── README.md           # Este archivo
```

## Instalación

### 1. Instalar dependencias

```bash
cd getnet_agent_linux
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con los valores correctos
```

Variables importantes:
- `GETNET_SERIAL_PORT`: Puerto serie del POS (ej: `/dev/ttyUSB0`)
- `GETNET_BAUDRATE`: Baudrate (ej: `9600`)
- `GETNET_DEMO`: `true` para modo demo (simula pagos sin POS real)

### 3. Ejecutar en modo desarrollo

```bash
chmod +x run_agent.sh
./run_agent.sh
```

O directamente:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 7777
```

## API Endpoints

### POST /pago

Procesa un pago a través del POS Getnet.

**Request:**
```json
{
  "amount": 15000,
  "currency": "CLP",
  "metadata": {
    "caja_codigo": "caja1",
    "cajero": "TOTEM_AUTO_1"
  }
}
```

**Response (éxito):**
```json
{
  "ok": true,
  "responseCode": "0",
  "responseMessage": "Aprobado",
  "authorizationCode": "123456",
  "raw": "..."
}
```

**Response (fallo):**
```json
{
  "ok": false,
  "responseCode": "05",
  "responseMessage": "No autorizado",
  "error": "No autorizado",
  "raw": "..."
}
```

### GET /estado

Devuelve el estado actual del agente para debugging.

**Response:**
```json
{
  "status": "ok",
  "device": "/dev/ttyUSB0",
  "demo_mode": false,
  "last_payment_ok": "2025-12-18T02:34:00",
  "last_error": null,
  "stats": {
    "total_payments": 10,
    "successful_payments": 8,
    "failed_payments": 2,
    "success_rate": "80.0%"
  }
}
```

## Integración con el Frontend

El navegador de la caja debe:

1. **Solicitar pago al agente local:**
   ```javascript
   const response = await fetch('http://127.0.0.1:7777/pago', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       amount: 15000,
       currency: 'CLP',
       metadata: { caja_codigo: 'caja1', cajero: 'TOTEM_AUTO_1' }
     })
   });
   const resultado = await response.json();
   ```

2. **Si `resultado.ok === true`:**
   - Llamar al backend central: `POST /api/caja/venta-ok`
   - Pasar el `authorizationCode` y detalles de la venta

3. **Si `resultado.ok === false`:**
   - Llamar al backend central: `POST /api/caja/venta-fallida-log`
   - Registrar el intento fallido
   - Mantener el carrito intacto

## Configuración como Servicio Systemd

### 1. Copiar archivos al sistema

```bash
sudo mkdir -p /opt/bimba/getnet_agent_linux
sudo cp -r * /opt/bimba/getnet_agent_linux/
sudo chown -R root:root /opt/bimba/getnet_agent_linux
```

### 2. Instalar servicio systemd

```bash
sudo cp bimba-getnet-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bimba-getnet-agent
sudo systemctl start bimba-getnet-agent
```

### 3. Verificar estado

```bash
sudo systemctl status bimba-getnet-agent
sudo journalctl -u bimba-getnet-agent -f
```

## Modo Demo

Para probar sin un POS Getnet real, activa el modo demo:

```bash
export GETNET_DEMO=true
# o en .env: GETNET_DEMO=true
```

En modo demo:
- No se usa el puerto serie real
- Se simulan respuestas de pago (éxito/fallo aleatorio)
- Útil para desarrollo y pruebas

## Implementación del Protocolo Getnet

**IMPORTANTE:** Las funciones de comunicación con Getnet están como STUB.

Cuando tengas el manual del protocolo Getnet, completa:

1. **`app/getnet.py::send_payment_to_getnet()`**
   - Construir el frame según el protocolo real
   - Incluir campos requeridos (monto, tipo, etc.)
   - Agregar checksum/CRC si aplica

2. **`app/getnet.py::parse_getnet_response()`**
   - Parsear la respuesta binaria real
   - Extraer código de respuesta, mensaje, autorización
   - Validar checksum/CRC si aplica

Busca los comentarios `# TODO:` en el código para ver dónde implementar.

## Tests

Ejecutar tests:

```bash
pytest tests/
```

O con cobertura:

```bash
pytest tests/ --cov=app --cov-report=html
```

## Troubleshooting

### El puerto serie no se encuentra

```bash
# Listar puertos serie disponibles
ls -l /dev/ttyUSB* /dev/ttyACM*

# Verificar permisos
sudo chmod 666 /dev/ttyUSB0
# o agregar usuario al grupo dialout
sudo usermod -a -G dialout $USER
```

### El servicio no inicia

```bash
# Ver logs
sudo journalctl -u bimba-getnet-agent -n 50

# Verificar variables de entorno
sudo systemctl show bimba-getnet-agent --property=Environment
```

### Modo demo no funciona

Verificar que `GETNET_DEMO=true` esté en `.env` o exportado como variable de entorno.

## Licencia

Propietario - Bimba


