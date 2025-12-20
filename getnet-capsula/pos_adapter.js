/**
 * Adaptador para POS Integrado Getnet
 * 
 * Envuelve la lógica de venta del SDK oficial de Getnet.
 * Reutiliza directamente las llamadas del proyecto de ejemplo que ya funciona.
 * 
 * IMPORTANTE: Este módulo usa el SDK POSIntegrado que está en:
 *   ../getnet-sdk/Node.JS/getnet_posintegrado/
 * 
 * O en la ruta configurada en GETNET_SDK_PATH
 */

const path = require('path');

// Estado del POS
let posInstance = null;
let posInitialized = false;
let ticketNumber = 1; // Correlativo simple para tickets
let lastPayment = null; // Última respuesta de pago

// Promesas pendientes para manejar respuestas asíncronas del SDK
const pendingSales = new Map(); // Map<ticketNumber, { resolve, reject, timestamp }>

/**
 * Callback principal del SDK para recibir respuestas
 * 
 * El SDK llama a este callback cuando recibe una respuesta del POS.
 */
function handleSDKCallback(jsonData) {
    console.log('[POS Adapter] Callback recibido:', JSON.stringify(jsonData, null, 2));
    
    // Si es un mensaje de "Received", ignorarlo (solo confirma recepción)
    if (jsonData.Received) {
        console.log('[POS Adapter] Mensaje de recepción, ignorando...');
        return;
    }
    
    // Parsear la respuesta JSON serializada
    let responseData;
    try {
        if (typeof jsonData.JsonSerialized === 'string') {
            responseData = JSON.parse(jsonData.JsonSerialized);
        } else if (jsonData.JsonSerialized && typeof jsonData.JsonSerialized === 'object') {
            responseData = jsonData.JsonSerialized;
        } else {
            responseData = jsonData;
        }
    } catch (error) {
        console.error('[POS Adapter] Error al parsear respuesta:', error);
        return;
    }
    
    console.log('[POS Adapter] Respuesta parseada:', JSON.stringify(responseData, null, 2));
    
    // Buscar la venta pendiente correspondiente
    // El SDK devuelve el ticketNumber en la respuesta (campo Ticket o similar)
    // Por ahora usamos FunctionCode para identificar si es una respuesta de venta
    const functionCode = responseData.FunctionCode;
    
    if (functionCode === 101) { // FunctionCode 101 = Sale
        // Buscar la venta pendiente más reciente (ya que no tenemos el ticket en la respuesta directamente)
        // TODO: Si el SDK devuelve el ticketNumber en la respuesta, usarlo para buscar la promesa correcta
        const pendingEntries = Array.from(pendingSales.entries());
        if (pendingEntries.length > 0) {
            // Tomar la más reciente
            const [ticket, pending] = pendingEntries[pendingEntries.length - 1];
            pendingSales.delete(ticket);
            
            // Mapear respuesta a formato estándar
            const result = mapResponseToStandard(responseData, jsonData);
            lastPayment = result;
            
            pending.resolve(result);
        } else {
            console.warn('[POS Adapter] Respuesta recibida sin venta pendiente');
        }
    } else {
        console.log(`[POS Adapter] Respuesta con FunctionCode ${functionCode}, ignorando (no es venta)`);
    }
}

/**
 * Callback de timeout de respuesta del SDK
 */
function handleTimeoutResponseError() {
    console.error('[POS Adapter] ⏱️ Timeout esperando respuesta del POS');
    
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
    console.warn('[POS Adapter] ⏱️ Timeout esperando confirmación de recepción del POS');
    // Este timeout es menos crítico, solo logueamos
}

/**
 * Inicializa el POS Integrado usando el SDK oficial
 * 
 * Reutiliza la misma lógica que el proyecto de ejemplo que ya funciona.
 * 
 * @returns {Promise<boolean>} true si la inicialización fue exitosa
 */
async function inicializarPOS() {
    if (posInitialized && posInstance) {
        console.log('[POS Adapter] POS ya está inicializado');
        return true;
    }
    
    try {
        console.log('[POS Adapter] Inicializando POS Getnet...');
        
        // Ruta al SDK
        // En producción: /app/getnet-sdk/Node.JS/getnet_posintegrado
        // En desarrollo: relativa desde este archivo
        const sdkPath = process.env.GETNET_SDK_PATH || 
            (process.env.NODE_ENV === 'production'
                ? '/app/getnet-sdk/Node.JS/getnet_posintegrado'
                : path.join(__dirname, '../getnet-sdk/Node.JS/getnet_posintegrado'));
        
        console.log(`[POS Adapter] Cargando SDK desde: ${sdkPath}`);
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
        console.log('[POS Adapter] Verificando conexión con POS (Poll)...');
        posInstance.Poll();
        
        // Esperar un poco para ver si hay respuesta (opcional)
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        posInitialized = true;
        console.log('[POS Adapter] ✅ POS Getnet inicializado correctamente');
        return true;
        
    } catch (error) {
        console.error('[POS Adapter] ❌ Error al inicializar POS Getnet:', error);
        posInstance = null;
        posInitialized = false;
        throw error;
    }
}

/**
 * Realiza una venta con el POS Getnet
 * 
 * Esta función envuelve la lógica de venta del proyecto de ejemplo oficial.
 * Reutiliza directamente la misma llamada que hace la app de prueba.
 * 
 * @param {number} monto - Monto en pesos chilenos
 * @returns {Promise<Object>} Respuesta estándar con ok, responseCode, etc.
 */
async function realizarVentaGetnet(monto) {
    // Validar monto
    if (!monto || typeof monto !== 'number' || monto <= 0) {
        throw new Error('Monto inválido');
    }
    
    // Asegurar que el POS está inicializado
    if (!posInitialized) {
        await inicializarPOS();
    }
    
    if (!posInstance) {
        throw new Error('POS no está inicializado');
    }
    
    try {
        console.log(`[POS Adapter] Ejecutando venta: $${monto}`);
        
        // Crear promesa para manejar la respuesta asíncrona del SDK
        const currentTicket = ticketNumber;
        const salePromise = new Promise((resolve, reject) => {
            // Guardar la promesa pendiente
            pendingSales.set(currentTicket, {
                resolve,
                reject,
                timestamp: Date.now()
            });
            
            // Timeout de seguridad (120 segundos, igual que el SDK)
            setTimeout(() => {
                if (pendingSales.has(currentTicket)) {
                    pendingSales.delete(currentTicket);
                    reject(new Error('Timeout esperando respuesta del POS'));
                }
            }, 120000);
        });
        
        // Cargar PosCommands desde el SDK
        const sdkBasePath = process.env.GETNET_SDK_PATH || 
            (process.env.NODE_ENV === 'production'
                ? '/app/getnet-sdk/Node.JS/getnet_posintegrado'
                : path.join(__dirname, '../getnet-sdk/Node.JS/getnet_posintegrado'));
        const POSCommands = require(path.join(sdkBasePath, 'lib/PosCommands'));
        
        // Ejecutar venta usando el método Sale() del SDK
        // Esta es la MISMA llamada que hace el proyecto de ejemplo oficial
        // Parámetros según el SDK:
        // - amount: monto en pesos
        // - ticket: número de ticket
        // - printOnPos: imprimir en POS (false = solo en impresora térmica)
        // - saleType: tipo de venta (0 = Sale normal)
        // - sendMessage: enviar mensaje al cliente (false)
        // - employeeId: ID del empleado (1 por defecto)
        // - secondsTimeout: timeout en segundos (120 por defecto)
        posInstance.Sale(
            monto,                          // amount
            currentTicket,                  // ticket number
            false,                          // printOnPos (no imprimir en POS)
            POSCommands.SaleType.Sale,      // saleType (0 = Sale)
            false,                          // sendMessage
            1,                              // employeeId
            120                             // secondsTimeout
        );
        
        console.log(`[POS Adapter] Comando Sale enviado, esperando respuesta...`);
        
        // Incrementar número de ticket para próxima venta
        ticketNumber++;
        
        // Esperar respuesta del POS (viene por callback)
        const result = await salePromise;
        
        console.log(`[POS Adapter] ✅ Venta completada: ${result.ok ? 'APROBADA' : 'RECHAZADA'}`);
        
        return result;
        
    } catch (error) {
        console.error('[POS Adapter] Error al ejecutar venta:', error);
        
        // Retornar error en formato estándar
        const errorResult = {
            ok: false,
            responseCode: 'ERROR_SDK',
            responseMessage: `Error al comunicarse con el POS: ${error.message}`,
            authorizationCode: null,
            amount: monto,
            cardBrand: null,
            cardType: null,
            last4Digits: null,
            terminalId: null,
            commerceCode: null,
            raw: {
                error: error.message,
                stack: error.stack
            }
        };
        
        lastPayment = errorResult;
        return errorResult;
    }
}

/**
 * Mapea la respuesta del SDK a formato estándar
 * 
 * Usa exactamente los campos que devuelve el SDK según el log del ejemplo:
 * 
 * RESPONSE: {
 *   "JsonSerialized": {
 *     "ResponseCode": 0,
 *     "ResponseMessage": "Aprobado",
 *     "AuthorizationCode": "250349",
 *     "Amount": 500,
 *     "CardBrand": "VI",
 *     "CardType": "DB",
 *     "Last4Digits": 1690,
 *     "TerminalId": "20129179",
 *     "CommerceCode": 266665,
 *     ...
 *   }
 * }
 * 
 * @param {Object} responseData - Respuesta parseada del SDK (JsonSerialized)
 * @param {Object} rawResponse - Respuesta completa original del SDK
 * @returns {Object} Respuesta en formato estándar
 */
function mapResponseToStandard(responseData, rawResponse) {
    const responseCode = responseData.ResponseCode;
    const isApproved = responseCode === 0 || responseCode === '0';
    
    return {
        ok: isApproved,
        responseCode: responseCode,
        responseMessage: responseData.ResponseMessage || 'Sin mensaje',
        authorizationCode: responseData.AuthorizationCode || null,
        amount: responseData.Amount || 0,
        cardBrand: responseData.CardBrand || null,
        cardType: responseData.CardType || null,
        last4Digits: responseData.Last4Digits || null,
        terminalId: responseData.TerminalId || null,
        commerceCode: responseData.CommerceCode || null,
        raw: rawResponse // Respuesta completa del SDK para debugging
    };
}

/**
 * Obtiene el estado del POS
 * 
 * @returns {Object} Estado del POS
 */
function getEstadoPOS() {
    return {
        posReady: posInitialized && posInstance !== null,
        initialized: posInitialized
    };
}

/**
 * Obtiene el último pago procesado
 * 
 * @returns {Object|null} Última respuesta de pago o null
 */
function getLastPayment() {
    return lastPayment;
}

module.exports = {
    realizarVentaGetnet,
    inicializarPOS,
    getEstadoPOS,
    getLastPayment
};

