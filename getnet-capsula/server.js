/**
 * Servidor HTTP de la Cápsula de Transacción Getnet
 * 
 * Microservicio HTTP simple que expone un endpoint para realizar pagos
 * con el POS Integrado Getnet.
 * 
 * Escucha en: http://127.0.0.1:7777
 */

const express = require('express');
const cors = require('cors');
const { realizarVentaGetnet, inicializarPOS, getEstadoPOS, getLastPayment } = require('./pos_adapter');

const app = express();
const PORT = process.env.PORT || 7777;

// Middleware
app.use(cors()); // Permitir CORS desde el navegador local
app.use(express.json()); // Parsear JSON en el body
app.use(express.urlencoded({ extended: true }));

// Middleware de logging
app.use((req, res, next) => {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
    next();
});

/**
 * GET /estado
 * Devuelve el estado de la cápsula y del POS
 */
app.get('/estado', (req, res) => {
    try {
        const estadoPOS = getEstadoPOS();
        const lastPayment = getLastPayment();
        
        res.json({
            status: 'ok',
            posReady: estadoPOS.posReady,
            lastPayment: lastPayment
        });
    } catch (error) {
        console.error('[Server] Error en GET /estado:', error);
        res.status(500).json({
            status: 'error',
            error: error.message
        });
    }
});

/**
 * POST /pago
 * Procesa un pago con el POS Getnet
 * 
 * Request:
 * {
 *   "amount": 5000,
 *   "currency": "CLP",
 *   "metadata": {
 *     "caja_codigo": "caja1",
 *     "cajero": "TOTEM_AUTO_1",
 *     "origen": "TOTEM"
 *   }
 * }
 * 
 * Response (siempre 200 OK):
 * {
 *   "ok": true/false,
 *   "responseCode": 0,
 *   "responseMessage": "Aprobado",
 *   "authorizationCode": "250349",
 *   "amount": 5000,
 *   "cardBrand": "VI",
 *   "cardType": "DB",
 *   "last4Digits": 1690,
 *   "terminalId": "20129179",
 *   "commerceCode": 266665,
 *   "raw": { ... }
 * }
 */
app.post('/pago', async (req, res) => {
    try {
        const { amount, currency, metadata } = req.body;
        
        // Validar monto
        if (!amount || typeof amount !== 'number' || amount <= 0) {
            return res.status(200).json({
                ok: false,
                responseCode: 'INVALID_AMOUNT',
                responseMessage: 'Monto inválido. Debe ser un número mayor a 0.',
                authorizationCode: null,
                amount: amount || 0,
                cardBrand: null,
                cardType: null,
                last4Digits: null,
                terminalId: null,
                commerceCode: null,
                raw: { error: 'Invalid amount' }
            });
        }
        
        // Validar currency (opcional, pero recomendado)
        if (currency && currency !== 'CLP') {
            console.warn(`[Server] Currency no soportado: ${currency}, usando CLP`);
        }
        
        console.log(`[Server] Recibida solicitud de pago: $${amount} CLP`);
        if (metadata) {
            console.log(`[Server] Metadata:`, metadata);
        }
        
        // Ejecutar venta con el POS
        const result = await realizarVentaGetnet(amount);
        
        // Siempre responder 200 OK (el campo "ok" indica éxito/fallo)
        res.status(200).json(result);
        
    } catch (error) {
        console.error('[Server] Error en POST /pago:', error);
        
        const errorResult = {
            ok: false,
            responseCode: 'ERROR_SERVER',
            responseMessage: `Error interno: ${error.message}`,
            authorizationCode: null,
            amount: req.body.amount || 0,
            cardBrand: null,
            cardType: null,
            last4Digits: null,
            terminalId: null,
            commerceCode: null,
            raw: {
                error: error.message,
                stack: process.env.NODE_ENV !== 'production' ? error.stack : undefined
            }
        };
        
        // Siempre responder 200 OK
        res.status(200).json(errorResult);
    }
});

/**
 * GET /
 * Endpoint raíz con información básica
 */
app.get('/', (req, res) => {
    res.json({
        service: 'Cápsula de Transacción Getnet',
        version: '1.0.0',
        status: 'running',
        endpoints: {
            pago: 'POST /pago',
            estado: 'GET /estado'
        }
    });
});

// Manejo de errores
app.use((err, req, res, next) => {
    console.error('[Server] Error no manejado:', err);
    res.status(500).json({
        ok: false,
        error: 'Error interno del servidor',
        message: err.message
    });
});

// Inicializar servidor
async function startServer() {
    try {
        // Intentar inicializar el POS (no crítico si falla, se inicializará en el primer pago)
        try {
            await inicializarPOS();
        } catch (error) {
            console.warn('[Server] ⚠️ No se pudo inicializar POS al inicio:', error.message);
            console.warn('[Server] El POS se inicializará automáticamente en el primer pago');
        }
        
        // Iniciar servidor HTTP
        app.listen(PORT, '127.0.0.1', () => {
            console.log(`🚀 Cápsula Getnet iniciada en http://127.0.0.1:${PORT}`);
            console.log(`📋 Endpoints disponibles:`);
            console.log(`   - POST http://127.0.0.1:${PORT}/pago`);
            console.log(`   - GET  http://127.0.0.1:${PORT}/estado`);
        });
        
    } catch (error) {
        console.error('❌ Error al iniciar servidor:', error);
        process.exit(1);
    }
}

// Manejar señales de terminación
process.on('SIGTERM', () => {
    console.log('[Server] SIGTERM recibido, cerrando servidor...');
    process.exit(0);
});

process.on('SIGINT', () => {
    console.log('[Server] SIGINT recibido, cerrando servidor...');
    process.exit(0);
});

// Iniciar servidor
startServer();

module.exports = app;

