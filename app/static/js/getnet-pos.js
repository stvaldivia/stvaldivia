/**
 * Integración Getnet POS Integrado
 * Según Manual de Integración GetNet 1.11
 * 
 * Cliente WebSocket para comunicación con servidor Node.js
 */

const Getnet = (function() {
    let ws = null;
    let serverUrl = "";
    let messageCallback = null;
    let errorCallback = null;

    function init(host, port, onMessage, onError) {
        serverUrl = `ws://${host}:${port}`;
        messageCallback = onMessage;
        errorCallback = onError;
    }

    function connect() {
        return new Promise((resolve, reject) => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                resolve("Reconectado");
                return;
            }
            
            ws = new WebSocket(serverUrl);
            
            ws.onopen = () => { 
                console.log("✅ GetNet: Conectado al servidor Node.js");
                resolve(ws); 
            };
            
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    
                    // Ignorar ACK del servidor Node, esperar JsonSerialized
                    if (data.Received && !data.JsonSerialized) {
                        console.log("📥 GetNet: ACK recibido");
                        return;
                    }
                    
                    if (data.JsonSerialized && messageCallback) {
                        const posResponse = JSON.parse(data.JsonSerialized);
                        console.log("📥 GetNet: Respuesta del POS:", posResponse);
                        messageCallback(posResponse);
                    } else if (data.error && errorCallback) {
                        errorCallback(data.error);
                    }
                } catch (e) { 
                    console.error("❌ Error parseando respuesta:", e);
                    if (errorCallback) errorCallback("Error al parsear respuesta: " + e.message);
                }
            };
            
            ws.onerror = (err) => {
                console.error("❌ GetNet: Error WebSocket:", err);
                if (errorCallback) errorCallback(err);
                reject(err);
            };
            
            ws.onclose = () => {
                console.log("⚠️ GetNet: Desconectado");
                ws = null;
            };
        });
    }

    function sendCommand(cmd) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            console.log("📤 GetNet: Enviando comando:", cmd);
            ws.send(JSON.stringify(cmd));
        } else {
            const error = "Socket no conectado";
            console.error("❌ GetNet:", error);
            if (errorCallback) errorCallback(error);
        }
    }

    return {
        Init: init,
        Connect: connect,
        Disconnect: () => { 
            if(ws) {
                ws.close();
                ws = null;
            }
        },
        
        // Comandos según Manual 1.11
        Poll: () => sendCommand({ 
            "Command": 106, 
            "DateTime": new Date().toISOString() 
        }),
        
        Sale: (amount, ticket) => sendCommand({
            "Command": 100, // IMPORTANTE: 100 es Venta según Manual 1.11
            "Amount": parseInt(amount),
            "TicketNumber": ticket.toString(),
            "PrintOnPos": true,
            "SaleType": 1,
            "SendMessage": true, // Para recibir "Ingrese PIN", etc.
            "DateTime": new Date().toISOString()
        }),
        
        CancelSale: () => sendCommand({ 
            "Command": 116, 
            "DateTime": new Date().toISOString() 
        }),
        
        // Verificar estado de conexión
        IsConnected: () => ws && ws.readyState === WebSocket.OPEN
    };
})();

// Exponer globalmente
window.Getnet = Getnet;
