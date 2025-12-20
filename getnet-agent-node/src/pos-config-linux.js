/**
 * Wrapper de PosConfig para Linux
 * 
 * El SDK original lee configuración desde un archivo encriptado en Windows.
 * Este módulo proporciona una alternativa para Linux usando variables de entorno.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

/**
 * Obtiene la configuración del POS para Linux
 * 
 * En Linux, leemos desde variables de entorno en lugar del archivo encriptado de Windows.
 */
function GetPosConfigLinux() {
    return new Promise((resolve, reject) => {
        try {
            // Leer configuración desde variables de entorno
            const config = {
                IsUsbConnection: true, // En Linux siempre USB/Serial
                PortName: process.env.GETNET_COM_PORT || '/dev/ttyUSB0',
                BaudRate: parseInt(process.env.GETNET_BAUDRATE || '9600', 10),
                PosIp: process.env.GETNET_POS_IP || '',
                PosPort: parseInt(process.env.GETNET_POS_PORT || '0', 10)
            };
            
            // Retornar como JSON string (el SDK espera esto)
            resolve(JSON.stringify(config));
        } catch (error) {
            reject(new Error(`Error al obtener configuración POS: ${error.message}`));
        }
    });
}

/**
 * Parchea el módulo PosConfig del SDK para usar nuestra función en Linux
 * 
 * Esto modifica el require cache para que PosConfig.GetPosConfig use nuestra función.
 */
function patchPosConfigForLinux() {
    // Ruta al SDK (misma que en pos.js)
    const sdkBase = process.env.GETNET_SDK_PATH || 
        (process.env.NODE_ENV === 'production'
            ? '/app/getnet-sdk'
            : path.join(__dirname, '../../getnet-sdk/Node.JS/getnet_posintegrado'));
    
    const sdkPath = sdkBase === '/app/getnet-sdk'
        ? '/app/getnet-sdk/Node.JS/getnet_posintegrado'
        : sdkBase;
    
    const PosConfigPath = path.join(sdkPath, 'lib/PosConfig.js');
    
    try {
        // Limpiar el cache del módulo si ya fue cargado
        delete require.cache[require.resolve(PosConfigPath)];
        
        // Cargar el módulo PosConfig
        const PosConfig = require(PosConfigPath);
        
        // Reemplazar GetPosConfig con nuestra versión para Linux
        if (os.platform() !== 'win32') {
            PosConfig.GetPosConfig = GetPosConfigLinux;
            console.log('[PosConfig Linux] ✅ PosConfig parcheado para Linux');
        }
    } catch (error) {
        console.warn('[PosConfig Linux] ⚠️ No se pudo parchear PosConfig:', error.message);
        console.warn('[PosConfig Linux] El SDK intentará usar su configuración por defecto');
    }
}

module.exports = {
    GetPosConfigLinux,
    patchPosConfigForLinux
};

