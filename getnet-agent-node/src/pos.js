/**
 * Wrapper alrededor del SDK POSIntegrado de Getnet
 * 
 * Este módulo encapsula la comunicación con el POS Getnet usando el SDK oficial.
 * 
 * SDK ubicado en: ../getnet-sdk/Node.JS/getnet_posintegrado/
 * 
 * El SDK usa callbacks para manejar respuestas:
 * - Se crea instancia con getInstance(callback, timeOutResponseError, timeOutReceivedError)
 * - Los métodos como Sale() no retornan promesas, usan el callback del constructor
 */

const logger = require('./logger');
const { config } = require('./config');
const path = require('path');
const fs = require('fs');
const os = require('os');

// Instancia singleton del POS
let posInstance = null;
let posInitialized = false;
let ticketNumber = 1; // Correlativo simple para tickets

// Promesas pendientes para manejar respuestas asíncronas
const pendingSales = new Map(); // Map<ticketNumber, { resolve, reject, timestamp }>

/**
 * Configura PosConfig para Linux
 * 
 * El SDK lee configuración desde un archivo encriptado en Windows.
 * Para Linux, parcheamos PosConfig para que lea desde variables de entorno.
 */
async function setupPosConfigForLinux() {
    // Solo hacer esto en Linux
    if (os.platform() === 'win32') {
        logger.debug('Windows detectado, usando configuración estándar del SDK');
        return;
    }
    
    try {
        logger.debug('Configurando PosConfig para Linux...');
        
        // Cargar nuestro wrapper de PosConfig
        const { patchPosConfigForLinux } = require('./pos-config-linux');
        
        // Parchear PosConfig ANTES de cargar el SDK
        patchPosConfigForLinux();
        
        logger.debug('✅ PosConfig configurado para Linux');
    } catch (error) {
        logger.warn('⚠️ No se pudo configurar PosConfig para Linux:', error.message);
        logger.warn('El SDK intentará usar su configuración por defecto');
    }
}

/**
 * Callback principal del SDK para recibir respuestas
 * 
 * El SDK llama a este callback cuando recibe una respuesta del POS.
 */
function handleSDKCallback(jsonData) {
    logger.debug('Callback SDK recibido:', jsonData);
    
    // Si es un mensaje de "Received", ignorarlo (solo confirma recepción)
    if (jsonData.Received) {
        logger.debug('Mensaje de recepción recibido, ignorando...');
        return;
    }
    
    // Parsear la respuesta JSON serializada
    let responseData;
    try {
        if (typeof jsonData.JsonSerialized === 'string') {
            responseData = JSON.parse(jsonData.JsonSerialized);
        } else {
            responseData = jsonData;
        }
    } catch (error) {
        logger.error('Error al parsear respuesta del SDK:', error);
        return;
    }
    
    // Buscar la venta pendiente correspondiente
    // El SDK devuelve el ticketNumber en la respuesta
    const ticket = responseData.Ticket || responseData.ticketNumber;
    
    if (ticket && pendingSales.has(ticket)) {
        const pending = pendingSales.get(ticket);
        pendingSales.delete(ticket);
        
        // Mapear respuesta y resolver la promesa
        const result = mapSDKResponseToStandard(responseData);
        pending.resolve(result);
    } else {
        logger.warn('Respuesta recibida sin venta pendiente:', responseData);
    }
}

/**
 * Callback de timeout de respuesta del SDK
 */
function handleTimeoutResponseError() {
    logger.error('⏱️ Timeout esperando respuesta del POS');
    
    // Rechazar todas las ventas pendientes
    for (const [ticket, pending] of pendingSales.entries()) {
        pendingSales.delete(ticket);
        pending.reject(new Error('Timeout esperando respuesta del POS'));
    }
}

/**
 * Callback de timeout de recepción del SDK
 */
function handleTimeoutReceivedError() {
    logger.warn('⏱️ Timeout esperando confirmación de recepción del POS');
    // Este timeout es menos crítico, solo logueamos
}

/**
 * Inicializa el POS Integrado usando el SDK oficial
 * 
 * Esta función debe ser llamada antes de ejecutar cualquier operación.
 * Usa singleton para evitar múltiples inicializaciones.
 * 
 * @returns {Promise<boolean>} true si la inicialización fue exitosa
 */
async function initPOS() {
    if (posInitialized && posInstance) {
        logger.debug('POS ya está inicializado');
        return true;
    }
    
    if (config.demo) {
        logger.info('Modo DEMO: No se inicializa POS real');
        posInitialized = true;
        return true;
    }
    
    try {
        logger.info('Inicializando POS Getnet...');
        
        // Configurar PosConfig para Linux antes de cargar el SDK
        // El SDK lee configuración desde un archivo encriptado en Windows
        // Para Linux, necesitamos crear un archivo de configuración temporal
        await setupPosConfigForLinux();
        
        // Ruta al SDK
        // En producción: /app/getnet-sdk (que apunta a Node.JS/getnet_posintegrado)
        // En desarrollo: relativa desde este archivo
        const sdkBase = process.env.GETNET_SDK_PATH || 
            (process.env.NODE_ENV === 'production' 
                ? '/app/getnet-sdk'
                : path.join(__dirname, '../../getnet-sdk/Node.JS/getnet_posintegrado'));
        
        // Si es ruta absoluta simple (/app/getnet-sdk), agregar subdirectorio
        const sdkPath = sdkBase === '/app/getnet-sdk' 
            ? '/app/getnet-sdk/Node.JS/getnet_posintegrado'
            : sdkBase;
        
        const POSIntegrado = require(sdkPath);
        
        // Crear instancia usando getInstance() del SDK con callbacks
        // El SDK usa un patrón singleton
        posInstance = POSIntegrado.getInstance(
            handleSDKCallback,
            handleTimeoutResponseError,
            handleTimeoutReceivedError
        );
        
        // Hacer Poll para verificar conexión con el POS
        // El SDK no requiere inicialización explícita, solo hacer Poll
        logger.info('Verificando conexión con POS (Poll)...');
        posInstance.Poll();
        
        // Esperar un poco para ver si hay respuesta (opcional)
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        posInitialized = true;
        logger.info('✅ POS Getnet inicializado correctamente');
        return true;
        
    } catch (error) {
        logger.error('❌ Error al inicializar POS Getnet:', error);
        posInstance = null;
        posInitialized = false;
        throw error;
    }
}

/**
 * Ejecuta una venta con el POS Getnet
 * 
 * @param {number} amount - Monto en pesos chilenos
 * @param {Object} metadata - Metadatos { caja_codigo, cajero }
 * @returns {Promise<Object>} Resultado de la venta con formato estándar
 */
async function sale(amount, metadata = {}) {
    // Validar monto
    if (!amount || amount <= 0) {
        throw new Error('Monto inválido');
    }
    
    // Modo demo: simular respuesta
    if (config.demo) {
        return simulateSale(amount, metadata);
    }
    
    // Asegurar que el POS está inicializado
    if (!posInitialized) {
        await initPOS();
    }
    
    if (!posInstance) {
        throw new Error('POS no está inicializado');
    }
    
    try {
        logger.payment('Ejecutando venta', { amount, caja_codigo: metadata.caja_codigo });
        
        // Crear promesa para manejar la respuesta asíncrona del SDK
        const currentTicket = ticketNumber;
        const salePromise = new Promise((resolve, reject) => {
            // Guardar la promesa pendiente
            pendingSales.set(currentTicket, {
                resolve,
                reject,
                timestamp: Date.now()
            });
            
            // Timeout de seguridad (más largo que el del SDK)
            setTimeout(() => {
                if (pendingSales.has(currentTicket)) {
                    pendingSales.delete(currentTicket);
                    reject(new Error('Timeout esperando respuesta del POS'));
                }
            }, config.pos.timeout);
        });
        
        // Ejecutar venta usando el método Sale() del SDK
        // Parámetros según el SDK:
        // - amount: monto en pesos
        // - ticket: número de ticket
        // - printOnPos: imprimir en POS (false = solo en impresora térmica)
        // - saleType: tipo de venta (0 = Sale normal)
        // - sendMessage: enviar mensaje al cliente (false)
        // - employeeId: ID del empleado (1 por defecto)
        // - secondsTimeout: timeout en segundos (120 por defecto)
        // Cargar PosCommands desde el SDK (misma ruta que POSIntegrado)
        const sdkBaseForCommands = process.env.GETNET_SDK_PATH || 
            (process.env.NODE_ENV === 'production'
                ? '/app/getnet-sdk'
                : path.join(__dirname, '../../getnet-sdk/Node.JS/getnet_posintegrado'));
        
        const sdkPathForCommands = sdkBaseForCommands === '/app/getnet-sdk'
            ? '/app/getnet-sdk/Node.JS/getnet_posintegrado'
            : sdkBaseForCommands;
        
        const POSCommands = require(path.join(sdkPathForCommands, 'lib/PosCommands'));
        
        posInstance.Sale(
            amount,                    // monto
            currentTicket,             // número de ticket
            false,                     // printOnPos (no imprimir en POS)
            POSCommands.SaleType.Sale, // tipo de venta (0 = Sale)
            false,                     // sendMessage
            1,                         // employeeId
            config.pos.timeout / 1000  // timeout en segundos
        );
        
        // Incrementar número de ticket para próxima venta
        ticketNumber++;
        
        // Esperar respuesta del POS (viene por callback)
        const result = await salePromise;
        
        logger.payment('Venta completada', {
            amount,
            caja_codigo: metadata.caja_codigo,
            ok: result.ok,
            responseCode: result.responseCode
        });
        
        return result;
        
    } catch (error) {
        logger.error('Error al ejecutar venta:', error);
        
        // Retornar error en formato estándar
        return {
            ok: false,
            responseCode: 'ERROR_SDK',
            responseMessage: `Error al comunicarse con el POS: ${error.message}`,
            authorizationCode: null,
            ticketNumber: null,
            raw: {
                error: error.message,
                stack: error.stack
            }
        };
    }
}

/**
 * Simula una venta en modo demo
 * 
 * @param {number} amount - Monto en pesos chilenos
 * @param {Object} metadata - Metadatos
 * @returns {Promise<Object>} Resultado simulado
 */
async function simulateSale(amount, metadata) {
    logger.payment('Simulando venta (MODO DEMO)', { amount, caja_codigo: metadata.caja_codigo });
    
    // Simular latencia del POS
    await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 2000));
    
    // 80% de éxito, 20% de rechazo
    const aprobado = Math.random() < 0.8;
    
    if (aprobado) {
        const authCode = `SIM-${Date.now()}`;
        logger.payment('Venta simulada APROBADA', {
            amount,
            caja_codigo: metadata.caja_codigo,
            ok: true,
            responseCode: '0'
        });
        
        return {
            ok: true,
            responseCode: '0',
            responseMessage: 'Aprobado (SIMULADO)',
            authorizationCode: authCode,
            ticketNumber: `TKT-${ticketNumber++}`,
            raw: {
                simulated: true,
                timestamp: new Date().toISOString()
            }
        };
    } else {
        logger.payment('Venta simulada RECHAZADA', {
            amount,
            caja_codigo: metadata.caja_codigo,
            ok: false,
            responseCode: '05'
        });
        
        return {
            ok: false,
            responseCode: '05',
            responseMessage: 'No autorizado (SIMULADO)',
            authorizationCode: null,
            ticketNumber: null,
            raw: {
                simulated: true,
                timestamp: new Date().toISOString()
            }
        };
    }
}

/**
 * Mapea la respuesta del SDK a formato estándar
 * 
 * TODO: Ajustar según la estructura real de la respuesta del SDK POSIntegrado
 * Revisa el SDK para ver qué campos devuelve y mapea correctamente.
 * 
 * @param {Object} sdkResponse - Respuesta del SDK POSIntegrado
 * @returns {Object} Respuesta en formato estándar
 */
function mapSDKResponseToStandard(sdkResponse) {
    // Mapear respuesta del SDK SaleResponse a formato estándar
    // El SDK devuelve campos con mayúscula inicial (ResponseCode, AuthorizationCode, etc.)
    
    const responseCode = String(sdkResponse.ResponseCode || sdkResponse.responseCode || '99');
    const isApproved = responseCode === '0';
    
    return {
        ok: isApproved,
        responseCode: responseCode,
        responseMessage: sdkResponse.ResponseMessage || sdkResponse.responseMessage || 'Sin mensaje',
        authorizationCode: sdkResponse.AuthorizationCode || sdkResponse.authorizationCode || null,
        ticketNumber: sdkResponse.Ticket ? String(sdkResponse.Ticket) : null,
        raw: sdkResponse // Respuesta completa del SDK para debugging
    };
}

/**
 * Obtiene el estado del POS
 * 
 * @returns {Object} Estado del POS
 */
function getPOSStatus() {
    return {
        initialized: posInitialized,
        demo: config.demo,
        instance: posInstance ? 'created' : null
    };
}

module.exports = {
    initPOS,
    sale,
    getPOSStatus
};

