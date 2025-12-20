# Cápsula de Transacción Getnet

Microservicio HTTP simple para realizar pagos con POS Integrado Getnet.

## Descripción

Esta cápsula expone un servicio HTTP local (`http://127.0.0.1:7777`) que permite realizar transacciones con el POS Getnet conectado por USB/COM. La cápsula NO sabe nada de carrito, tickets, inventario ni Bimbaverso; solo hace: **monto → venta local con POS → respuesta JSON estándar**.

## Requisitos

- Node.js >= 14.0.0
- SDK oficial de Getnet (POSIntegrado) disponible en `../getnet-sdk/Node.JS/getnet_posintegrado/`
- POS Getnet conectado por USB/COM (ej: COM3 en Windows, /dev/ttyUSB0 en Linux)

## Instalación

```bash
npm install
```

## Ejecutar

```bash
npm start
```

O en modo desarrollo con auto-reload:

```bash
npm run dev
```

## API Endpoints

### POST /pago

Procesa un pago con el POS Getnet.

**Request:**
```json
{
  "amount": 5000,
  "currency": "CLP",
  "metadata": {
    "caja_codigo": "caja1",
    "cajero": "TOTEM_AUTO_1",
    "origen": "TOTEM"
  }
}
```

**Response (siempre 200 OK):**
```json
{
  "ok": true,
  "responseCode": 0,
  "responseMessage": "Aprobado",
  "authorizationCode": "250349",
  "amount": 5000,
  "cardBrand": "VI",
  "cardType": "DB",
  "last4Digits": 1690,
  "terminalId": "20129179",
  "commerceCode": 266665,
  "raw": { ... }
}
```

**Reglas:**
- `ok = true` si `ResponseCode == 0` o `"0"`
- `ok = false` en cualquier otro caso o si hay error en la comunicación
- Siempre responde HTTP 200 con JSON (aunque `ok=false`)

### GET /estado

Devuelve el estado de la cápsula y del POS.

**Response:**
```json
{
  "status": "ok",
  "posReady": true,
  "lastPayment": {
    "ok": true,
    "responseCode": 0,
    "responseMessage": "Aprobado",
    ...
  }
}
```

## Ejemplo de Prueba

```bash
# Probar endpoint de pago
curl -X POST http://127.0.0.1:7777/pago \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 500,
    "currency": "CLP",
    "metadata": {
      "caja_codigo": "caja1",
      "cajero": "TOTEM_AUTO_1",
      "origen": "TOTEM"
    }
  }'

# Ver estado
curl http://127.0.0.1:7777/estado
```

## Configuración

### Variables de Entorno

- `PORT`: Puerto del servidor HTTP (default: 7777)
- `GETNET_SDK_PATH`: Ruta al SDK de Getnet (default: `../getnet-sdk/Node.JS/getnet_posintegrado`)
- `NODE_ENV`: `production` para usar ruta absoluta `/app/getnet-sdk`

### SDK de Getnet

La cápsula espera encontrar el SDK en:
- **Desarrollo**: `../getnet-sdk/Node.JS/getnet_posintegrado/`
- **Producción**: `/app/getnet-sdk/Node.JS/getnet_posintegrado/`

O configura la ruta con `GETNET_SDK_PATH`.

## Arquitectura

```
Bimbaverso (Backend)
    ↓ HTTP POST /pago
Cápsula Getnet (127.0.0.1:7777)
    ↓ SDK POSIntegrado
POS Getnet (USB/COM)
```

La cápsula actúa como un adaptador HTTP que envuelve toda la lógica de comunicación con el POS. El backend solo ve una API REST simple.

## Estructura del Proyecto

```
getnet-capsula/
├── server.js          # Servidor Express con endpoints
├── pos_adapter.js     # Adaptador que envuelve el SDK POSIntegrado
├── package.json
└── README.md
```

## Troubleshooting

### El POS no responde

- Verifica que el POS esté conectado por USB/COM
- Verifica que el puerto COM esté disponible (COM3, /dev/ttyUSB0, etc.)
- Revisa los logs de la cápsula para ver errores del SDK

### Error al cargar el SDK

- Verifica que el SDK esté en la ruta correcta
- Configura `GETNET_SDK_PATH` si el SDK está en otra ubicación

### Timeout esperando respuesta

- El POS puede estar ocupado o desconectado
- Verifica la conexión física del POS
- Revisa los logs del SDK para más detalles

## Logs

La cápsula imprime logs en consola con formato:
- `[POS Adapter]` - Logs del adaptador del POS
- `[Server]` - Logs del servidor HTTP
- Timestamps ISO8601 para cada request

## Licencia

Propietario - Bimba


