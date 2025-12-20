/**
 * Configuración del Agente Getnet Node.js
 * 
 * Lee variables de entorno y valida la configuración necesaria.
 */

require('dotenv').config();

const config = {
    // Puerto del servidor HTTP
    port: parseInt(process.env.PORT || '7777', 10),
    
    // Host del servidor (solo localhost por seguridad)
    host: process.env.HOST || '127.0.0.1',
    
    // Modo demo: si es true, no usa el SDK real
    demo: process.env.GETNET_DEMO === 'true' || process.env.GETNET_DEMO === '1',
    
    // Configuración del SDK POSIntegrado (solo cuando demo=false)
    pos: {
        // Puerto serie del POS (ej: /dev/ttyUSB0 en Linux)
        comPort: process.env.GETNET_COM_PORT || '/dev/ttyUSB0',
        
        // Código de comercio Getnet
        commerceCode: process.env.GETNET_COMMERCE_CODE || '',
        
        // ID del terminal Getnet
        terminalId: process.env.GETNET_TERMINAL_ID || '',
        
        // API Key de Getnet (si el SDK lo requiere)
        apiKey: process.env.GETNET_API_KEY || '',
        
        // Timeout para operaciones (ms)
        timeout: parseInt(process.env.GETNET_TIMEOUT || '30000', 10),
        
        // Baudrate del puerto serie (si aplica)
        baudrate: parseInt(process.env.GETNET_BAUDRATE || '9600', 10),
        
        // Número de reintentos en caso de error
        retryCount: parseInt(process.env.GETNET_RETRY_COUNT || '3', 10)
    }
};

/**
 * Valida la configuración
 * En modo demo no requiere configuración del POS
 */
function validateConfig() {
    if (config.demo) {
        console.log('✅ Modo DEMO activado - No se requiere configuración del POS');
        return true;
    }
    
    // Validar configuración mínima para modo producción
    const errors = [];
    
    if (!config.pos.commerceCode) {
        errors.push('GETNET_COMMERCE_CODE es requerido');
    }
    
    if (!config.pos.terminalId) {
        errors.push('GETNET_TERMINAL_ID es requerido');
    }
    
    if (errors.length > 0) {
        console.error('❌ Errores de configuración:');
        errors.forEach(err => console.error(`   - ${err}`));
        console.error('\n💡 Solución: Configura las variables de entorno en .env o activa GETNET_DEMO=true');
        return false;
    }
    
    console.log('✅ Configuración válida para modo producción');
    return true;
}

module.exports = {
    config,
    validateConfig
};



