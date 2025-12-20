/**
 * Ruta GET /estado
 * 
 * Devuelve el estado actual del agente y del POS.
 */

const express = require('express');
const router = express.Router();
const pos = require('../pos');
const logger = require('../logger');
const pagoRoute = require('./pago');

/**
 * GET /estado
 * Devuelve el estado del agente
 */
router.get('/', (req, res) => {
    try {
        const posStatus = pos.getPOSStatus();
        const lastPayment = pagoRoute.getLastPayment();
        
        const estado = {
            status: 'ok',
            posInicializado: posStatus.initialized,
            demo: posStatus.demo,
            lastPayment: lastPayment ? {
                ok: lastPayment.ok,
                responseCode: lastPayment.responseCode,
                responseMessage: lastPayment.responseMessage,
                timestamp: lastPayment.timestamp
            } : null
        };
        
        res.status(200).json(estado);
        
    } catch (error) {
        logger.error('Error en GET /estado:', error);
        res.status(500).json({
            status: 'error',
            error: error.message
        });
    }
});

module.exports = router;



