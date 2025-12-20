/**
 * Punto de entrada del Agente Getnet Node.js
 * 
 * Inicia el servidor HTTP Express que expone los endpoints
 * para comunicación con el POS Getnet.
 */

const express = require('express');
const cors = require('cors');
const { config, validateConfig } = require('./config');
const logger = require('./logger');
const pos = require('./pos');

// Importar rutas
const pagoRoute = require('./routes/pago');
const estadoRoute = require('./routes/estado');

// Crear aplicación Express
const app = express();

// Middleware
app.use(cors()); // Permitir CORS desde el navegador local
app.use(express.json()); // Parsear JSON en el body
app.use(express.urlencoded({ extended: true }));

// Middleware de logging de requests
app.use((req, res, next) => {
    logger.debug(`${req.method} ${req.path}`);
    next();
});

// Rutas
app.use('/pago', pagoRoute);
app.use('/estado', estadoRoute);

// Ruta raíz
app.get('/', (req, res) => {
    res.json({
        service: 'Agente Getnet Node.js',
        version: '1.0.0',
        status: 'running',
        endpoints: {
            pago: 'POST /pago',
            estado: 'GET /estado'
        },
        demo: config.demo
    });
});

// Manejo de errores
app.use((err, req, res, next) => {
    logger.error('Error no manejado:', err);
    res.status(500).json({
        ok: false,
        error: 'Error interno del servidor',
        message: err.message
    });
});

// Inicializar servidor
async function startServer() {
    try {
        // Validar configuración
        if (!validateConfig()) {
            logger.error('❌ Configuración inválida. Revisa las variables de entorno.');
            process.exit(1);
        }
        
        // Inicializar POS (si no está en modo demo)
        if (!config.demo) {
            logger.info('Inicializando POS Getnet...');
            try {
                await pos.initPOS();
                logger.info('✅ POS Getnet inicializado');
            } catch (error) {
                logger.error('❌ Error al inicializar POS:', error);
                logger.warn('⚠️  El servidor iniciará pero el POS no estará disponible');
            }
        } else {
            logger.info('ℹ️  Modo DEMO activado - No se inicializa POS real');
        }
        
        // Iniciar servidor HTTP
        app.listen(config.port, config.host, () => {
            logger.info(`🚀 Agente Getnet iniciado en http://${config.host}:${config.port}`);
            logger.info(`📋 Modo: ${config.demo ? 'DEMO (simulación)' : 'PRODUCCIÓN (POS real)'}`);
            logger.info(`🔌 Endpoints disponibles:`);
            logger.info(`   - POST http://${config.host}:${config.port}/pago`);
            logger.info(`   - GET  http://${config.host}:${config.port}/estado`);
        });
        
    } catch (error) {
        logger.error('❌ Error al iniciar servidor:', error);
        process.exit(1);
    }
}

// Manejar señales de terminación
process.on('SIGTERM', () => {
    logger.info('SIGTERM recibido, cerrando servidor...');
    process.exit(0);
});

process.on('SIGINT', () => {
    logger.info('SIGINT recibido, cerrando servidor...');
    process.exit(0);
});

// Iniciar servidor
startServer();

module.exports = app;



