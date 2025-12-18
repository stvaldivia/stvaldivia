import com.fazecast.jSerialComm.SerialPort;
import posintegradogetnet.POSIntegrado;
import posintegradogetnet.POSCommands;
import posintegradogetnet.requests.*;

/**
 * Script para procesar un pago directo con Getnet SIN pasar por el TPV
 * 
 * ⚠️ ADVERTENCIA: Este script procesa pagos directamente, sin crear ventas
 *    en el sistema. Solo procesa el pago en Getnet. Úsalo solo para pruebas.
 * 
 * Uso:
 *   javac -cp .;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar pago_directo.java
 *   java -cp .;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar pago_directo 100
 * 
 * Parámetros:
 *   - Monto (en pesos CLP, sin decimales): ej. 100 = $100 CLP
 *   - Puerto COM (opcional): ej. COM3 (default: COM3)
 */
public class pago_directo {
    
    public static void main(String[] args) {
        // Parsear argumentos
        if (args.length < 1) {
            System.out.println("Uso: java pago_directo <monto> [puerto]");
            System.out.println("Ejemplo: java pago_directo 1000 COM3");
            System.exit(1);
        }
        
        int monto = Integer.parseInt(args[0]);
        String puerto = args.length > 1 ? args[1] : "COM3";
        int baudrate = 115200;
        
        System.out.println("========================================");
        System.out.println("  PAGO DIRECTO GETNET (Sin TPV)");
        System.out.println("========================================");
        System.out.println("⚠️  ADVERTENCIA: Este pago NO se registra");
        System.out.println("   en el sistema TPV. Solo procesa en Getnet.");
        System.out.println();
        System.out.println("Monto: $" + monto + " CLP");
        System.out.println("Puerto: " + puerto);
        System.out.println("Baudrate: " + baudrate);
        System.out.println();
        
        SerialPort serialPort = null;
        POSIntegrado sdk = null;
        
        try {
            // 1. Abrir puerto serial
            System.out.println("[1/4] Abriendo puerto " + puerto + "...");
            serialPort = SerialPort.getCommPort(puerto);
            serialPort.setBaudRate(baudrate);
            serialPort.setComPortTimeouts(SerialPort.TIMEOUT_READ_SEMI_BLOCKING, 30000, 0);
            
            if (!serialPort.openPort()) {
                System.out.println("❌ Error al abrir puerto: " + serialPort.getLastErrorCode());
                System.exit(1);
            }
            System.out.println("✅ Puerto abierto");
            
            // 2. Inicializar SDK Getnet
            System.out.println("[2/4] Inicializando SDK Getnet...");
            sdk = new POSIntegrado();
            System.out.println("✅ SDK inicializado");
            
            // 3. Preparar request de venta
            System.out.println("[3/4] Preparando venta...");
            System.out.println("   Monto: $" + monto + " CLP");
            
            // Crear request de venta
            SaleRequest saleReq = new SaleRequest();
            
            // Convertir monto a centavos (Getnet generalmente trabaja en centavos)
            long montoCentavos = monto * 100;
            saleReq.setAmount(montoCentavos);
            
            // Tipo de venta: Débito por defecto
            saleReq.setSaleType(POSCommands.SaleType.DEBITO);
            
            System.out.println("✅ Request preparado");
            System.out.println();
            
            // 4. Procesar pago
            System.out.println("[4/4] Procesando pago en terminal Getnet...");
            System.out.println("   (El cliente debe insertar/pasar la tarjeta en el terminal)");
            System.out.println();
            
            Object saleResult = null;
            
            // Intentar métodos del SDK usando reflexión
            try {
                // Intentar método más común: executeSale
                java.lang.reflect.Method executeMethod = sdk.getClass().getMethod("executeSale", SaleRequest.class);
                saleResult = executeMethod.invoke(sdk, saleReq);
                System.out.println("✅ Método executeSale() usado");
            } catch (NoSuchMethodException e1) {
                try {
                    // Intentar método alternativo: processSale
                    java.lang.reflect.Method processMethod = sdk.getClass().getMethod("processSale", SaleRequest.class);
                    saleResult = processMethod.invoke(sdk, saleReq);
                    System.out.println("✅ Método processSale() usado");
                } catch (NoSuchMethodException e2) {
                    System.out.println("❌ Error: No se encontró método para procesar venta");
                    System.out.println("   Métodos probados: executeSale, processSale");
                    System.exit(1);
                }
            }
            
            // 5. Procesar respuesta
            System.out.println();
            System.out.println("📊 Procesando respuesta del terminal...");
            
            if (saleResult == null) {
                System.out.println("❌ El SDK no devolvió respuesta");
                System.exit(1);
            }
            
            // Intentar interpretar respuesta
            boolean aprobado = false;
            String authCode = "";
            String errorMsg = "";
            
            // Si la respuesta es String (JSON), parsearlo
            if (saleResult instanceof String) {
                String jsonResponse = (String) saleResult;
                System.out.println("   Respuesta JSON: " + jsonResponse);
                
                try {
                    org.json.JSONObject jsonResult = new org.json.JSONObject(jsonResponse);
                    
                    // Buscar JsonSerialized si existe
                    org.json.JSONObject jsonSerialized = null;
                    if (jsonResult.has("JsonSerialized")) {
                        jsonSerialized = jsonResult.getJSONObject("JsonSerialized");
                    } else {
                        jsonSerialized = jsonResult;
                    }
                    
                    int responseCode = jsonSerialized.optInt("ResponseCode", -1);
                    String responseMessage = jsonSerialized.optString("ResponseMessage", "");
                    
                    if (responseCode == 0 && "Aprobado".equals(responseMessage)) {
                        aprobado = true;
                        authCode = jsonSerialized.optString("AuthorizationCode", "");
                    } else {
                        errorMsg = responseMessage.isEmpty() ? "Código: " + responseCode : responseMessage;
                    }
                } catch (Exception e) {
                    System.out.println("   ⚠️  No se pudo parsear JSON: " + e.getMessage());
                }
            } else {
                // Si es objeto Java, intentar usar reflexión
                try {
                    java.lang.reflect.Method isApprovedMethod = saleResult.getClass().getMethod("isApproved");
                    aprobado = (Boolean) isApprovedMethod.invoke(saleResult);
                    
                    if (aprobado) {
                        try {
                            java.lang.reflect.Method getAuthCodeMethod = saleResult.getClass().getMethod("getAuthCode");
                            authCode = (String) getAuthCodeMethod.invoke(saleResult);
                        } catch (Exception e) {
                            // Ignorar si no existe
                        }
                    }
                } catch (Exception e) {
                    System.out.println("   ⚠️  No se pudo interpretar respuesta: " + e.getMessage());
                }
            }
            
            // 6. Mostrar resultado
            System.out.println();
            System.out.println("========================================");
            if (aprobado) {
                System.out.println("  ✅ PAGO APROBADO");
                System.out.println("========================================");
                System.out.println("Monto: $" + monto + " CLP");
                System.out.println("Código de autorización: " + (authCode.isEmpty() ? "N/A" : authCode));
                System.out.println();
                System.out.println("⚠️  NOTA: Este pago NO fue registrado en el TPV.");
                System.out.println("   Es una transacción directa con Getnet únicamente.");
            } else {
                System.out.println("  ❌ PAGO RECHAZADO");
                System.out.println("========================================");
                System.out.println("Mensaje: " + (errorMsg.isEmpty() ? "Transacción rechazada" : errorMsg));
            }
            
        } catch (Exception e) {
            System.out.println();
            System.out.println("========================================");
            System.out.println("  ❌ ERROR");
            System.out.println("========================================");
            System.out.println(e.getMessage());
            e.printStackTrace();
        } finally {
            // Cerrar puerto
            if (serialPort != null && serialPort.isOpen()) {
                System.out.println();
                System.out.println("🔒 Cerrando puerto...");
                serialPort.closePort();
            }
        }
    }
}


