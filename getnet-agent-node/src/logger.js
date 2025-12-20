/**
 * Logger simple con timestamps
 * 
 * Proporciona funciones de logging con formato consistente.
 */

/**
 * Formatea el timestamp actual
 */
function getTimestamp() {
    return new Date().toISOString();
}

/**
 * Logger con niveles
 */
const logger = {
    /**
     * Log de información general
     */
    info: (...args) => {
        console.log(`[${getTimestamp()}] [INFO]`, ...args);
    },
    
    /**
     * Log de advertencias
     */
    warn: (...args) => {
        console.warn(`[${getTimestamp()}] [WARN]`, ...args);
    },
    
    /**
     * Log de errores
     */
    error: (...args) => {
        console.error(`[${getTimestamp()}] [ERROR]`, ...args);
    },
    
    /**
     * Log de debug (solo en desarrollo)
     */
    debug: (...args) => {
        if (process.env.NODE_ENV !== 'production') {
            console.log(`[${getTimestamp()}] [DEBUG]`, ...args);
        }
    },
    
    /**
     * Log de operaciones de pago
     */
    payment: (message, data = {}) => {
        const { amount, caja_codigo, ok, responseCode } = data;
        const amountStr = amount ? `$${amount.toLocaleString('es-CL')}` : '';
        const cajaStr = caja_codigo ? ` [Caja: ${caja_codigo}]` : '';
        const resultStr = ok !== undefined ? ` [${ok ? '✅ APROBADO' : '❌ RECHAZADO'}]` : '';
        const codeStr = responseCode ? ` [Code: ${responseCode}]` : '';
        
        console.log(`[${getTimestamp()}] [PAYMENT] ${message}${amountStr}${cajaStr}${resultStr}${codeStr}`);
    }
};

module.exports = logger;



