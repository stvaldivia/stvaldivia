# Agente Getnet Node.js

Servicio HTTP local para comunicación con POS Getnet en tótems Linux de Bimba.

## Descripción

Este agente corre en cada tótem Linux y proporciona una API HTTP local (`http://127.0.0.1:7777`) para que el navegador de la caja pueda solicitar pagos al POS Getnet conectado por USB usando el SDK oficial de Getnet.

## Requisitos

- Node.js >= 14.0.0
- SDK oficial de Getnet (ZIP Node_JS de Santander)
- POS Getnet conectado por USB (en modo producción)

## Instalación

### 1. Instalar dependencias

```bash
npm install
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con los valores correctos
```

### 3. SDK de Getnet

**IMPORTANTE:** El SDK oficial de Getnet ya está descargado en:

```
getnet-sdk/
  Node.JS/
    getnet_posintegrado/
      lib/
        PosIntegrado.js
      index.js
      ... (otros archivos del SDK)
```

El agente está configurado para usar el SDK desde `../getnet-sdk/Node.JS/getnet_posintegrado/`.

Si necesitas usar otra ubicación, configura en `.env`:

```
GETNET_SDK_PATH=./ruta/al/sdk
```

**Nota para Linux:** El SDK está diseñado para Windows y lee configuración desde un archivo encriptado. El agente incluye un wrapper (`src/pos-config-linux.js`) que permite usar variables de entorno en Linux.

### 4. Ejecutar

```bash
npm start
```

O en modo desarrollo con auto-reload:

```bash
npm run dev
```

## Configuración

### Variables de Entorno

Ver `.env.example` para todas las opciones disponibles.

**Variables principales:**

- `PORT`: Puerto del servidor HTTP (default: 7777)
- `GETNET_DEMO`: `true` para modo demo (simulación), `false` para POS real
- `GETNET_COM_PORT`: Puerto serie del POS (ej: `/dev/ttyUSB0`)
- `GETNET_COMMERCE_CODE`: Código de comercio Getnet
- `GETNET_TERMINAL_ID`: ID del terminal Getnet
- `GETNET_API_KEY`: API Key de Getnet (si el SDK lo requiere)

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

**Response (siempre 200 OK):**
```json
{
  "ok": true,
  "responseCode": "0",
  "responseMessage": "Aprobado",
  "authorizationCode": "123456",
  "ticketNumber": "TKT-001",
  "raw": {...}
}
```

### GET /estado

Devuelve el estado actual del agente.

**Response:**
```json
{
  "status": "ok",
  "posInicializado": true,
  "demo": false,
  "lastPayment": {
    "ok": true,
    "responseCode": "0",
    "responseMessage": "Aprobado",
    "timestamp": "2025-12-18T03:00:00.000Z"
  }
}
```

## Modo Demo

Para probar sin un POS Getnet real, activa el modo demo:

```bash
export GETNET_DEMO=true
npm start
```

En modo demo:
- No se usa el SDK real
- Se simulan respuestas de pago (80% éxito, 20% rechazo)
- Útil para desarrollo y pruebas

## Integración con el Frontend

El navegador del tótem debe:

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

## Configuración del SDK

**IMPORTANTE:** Antes de usar en producción, debes:

1. Revisar el SDK oficial de Getnet (`./sdk/lib/PosIntegrado.js`)
2. Ajustar `src/pos.js` según la API real del SDK:
   - Métodos de inicialización
   - Métodos de venta
   - Estructura de respuestas
   - Manejo de callbacks/promesas

Busca los comentarios `TODO:` en `src/pos.js` para ver dónde ajustar.

## Estructura del Proyecto

```
getnet-agent-node/
├── src/
│   ├── index.js          # Punto de entrada del servidor
│   ├── config.js         # Configuración desde variables de entorno
│   ├── logger.js         # Logger con timestamps
│   ├── pos.js            # Wrapper del SDK POSIntegrado
│   └── routes/
│       ├── pago.js       # Endpoint POST /pago
│       └── estado.js     # Endpoint GET /estado
├── sdk/                  # SDK oficial de Getnet (colocar aquí)
├── package.json
├── .env.example
└── README.md
```

## Troubleshooting

### El SDK no se encuentra

Verifica que el SDK esté en `./sdk/` o configura `GETNET_SDK_PATH` en `.env`.

### Error al inicializar POS

- Verifica que el POS esté conectado por USB
- Verifica que el puerto serie sea correcto (`GETNET_COM_PORT`)
- Verifica las credenciales (`GETNET_COMMERCE_CODE`, `GETNET_TERMINAL_ID`)

### Modo demo no funciona

Verifica que `GETNET_DEMO=true` esté en `.env` o exportado como variable de entorno.

## Licencia

Propietario - Bimba

