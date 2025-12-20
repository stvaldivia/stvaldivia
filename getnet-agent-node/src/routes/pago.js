/**
 * Ruta POST /pago
 * 
 * Procesa un pago con el POS Getnet.
 * 
 * Body esperado:
 * {
 *   "amount": 15000,
 *   "currency": "CLP",
 *   "metadata": {
 *     "caja_codigo": "caja1",
 *     "cajero": "TOTEM_AUTO_1"
 *   }
 * }
 * 
 * Respuesta (siempre 200 OK):
 * {
 *   "ok": true/false,
 *   "responseCode": "...",
 *   "responseMessage": "...",
 *   "authorizationCode": "...",
 *   "ticketNumber": "...",
 *   "raw": {...}
 * }
 */

const express = require('express');
const router = express.Router();
const pos = require('../pos');
const logger = require('../logger');

// Estado del último pago (para /estado)
let lastPayment = null;

/**
 * POST /pago
 * Procesa un pago con Getnet
 */
router.post('/', async (req, res) => {
    try {
        const { amount, currency, metadata } = req.body;
        
        // Validar monto
        if (!amount || typeof amount !== 'number' || amount <= 0) {
            return res.status(200).json({
                ok: false,
                responseCode: 'INVALID_AMOUNT',
                responseMessage: 'Monto inválido. Debe ser un número mayor a 0.',
                authorizationCode: null,
                ticketNumber: null,
                raw: { error: 'Invalid amount' }
            });
        }
        
        // Validar currency (opcional, pero recomendado)
        if (currency && currency !== 'CLP') {
            logger.warn(`Currency no soportado: ${currency}, usando CLP`);
        }
        
        logger.payment('Recibida solicitud de pago', {
            amount,
            caja_codigo: metadata?.caja_codigo
        });
        
        // Ejecutar venta con el POS
        const result = await pos.sale(amount, metadata || {});
        
        // Guardar resultado para /estado
        lastPayment = {
            ...result,
            timestamp: new Date().toISOString(),
            amount,
            metadata
        };
        
        // Siempre responder 200 OK (el campo "ok" indica éxito/fallo)
        res.status(200).json(result);
        
    } catch (error) {
        logger.error('Error en POST /pago:', error);
        
        const errorResult = {
            ok: false,
            responseCode: 'ERROR_SERVER',
            responseMessage: `Error interno: ${error.message}`,
            authorizationCode: null,
            ticketNumber: null,
            raw: {
                error: error.message,
                stack: process.env.NODE_ENV !== 'production' ? error.stack : undefined
            }
        };
        
        // Guardar error para /estado
        lastPayment = {
            ...errorResult,
            timestamp: new Date().toISOString()
        };
        
        // Siempre responder 200 OK
        res.status(200).json(errorResult);
    }
});

/**
 * Obtiene el último pago procesado
 * (usado por /estado)
 */
function getLastPayment() {
    return lastPayment;
}

module.exports = router;
module.exports.getLastPayment = getLastPayment;


