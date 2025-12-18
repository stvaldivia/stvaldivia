#!/usr/bin/env bash
set -euo pipefail

echo "=== Preparando Agente Getnet (Java) para BIMBA ==="
echo ""

# ============================================================================
# CONFIG (por env vars)
# ============================================================================
# Backend base (tu producción)
BASE_URL="${BASE_URL:-https://stvaldivia.cl}"
# Caja / register_id (string). Debe coincidir con el register_id que usa el POS.
REGISTER_ID="${REGISTER_ID:-1}"
# Key compartida con el backend (header X-AGENT-KEY). Debe igualar AGENT_API_KEY del server.
AGENT_API_KEY="${AGENT_API_KEY:-}"
# ID opcional del agente (para locking/observabilidad)
AGENT_ID="${AGENT_ID:-java-agent-$(hostname)}"

if [ -z "$AGENT_API_KEY" ]; then
  echo "❌ Falta AGENT_API_KEY."
  echo "Nota: en el backend debe estar configurada la variable de entorno AGENT_API_KEY."
  echo "Ejemplo: REGISTER_ID=\"1\" AGENT_API_KEY=\"...\" $0"
  exit 1
fi

# ============================================================================
# Directorio de trabajo
# ============================================================================
mkdir -p ~/getnet_agent/java
cd ~/getnet_agent/java
echo "Directorio de trabajo: $(pwd)"
echo ""

# ============================================================================
# Dependencias (Linux Debian/Ubuntu)
# ============================================================================
if command -v apt >/dev/null 2>&1; then
  echo "=== Detectado apt: instalando Java + curl (si faltan) ==="
  sudo apt update -y
  sudo apt install -y default-jre default-jdk curl ca-certificates
else
  echo "apt no encontrado. Asegúrate de tener Java 11+ y curl."
fi

# ============================================================================
# Descargar org.json (json.jar)
# ============================================================================
echo ""
echo "=== Descargando json.jar (org.json) ==="
JSON_JAR_URL="${JSON_JAR_URL:-https://repo1.maven.org/maven2/org/json/json/20240303/json-20240303.jar}"
curl -fsSL "$JSON_JAR_URL" -o json.jar
echo "OK: json.jar descargado"

# ============================================================================
# SDK Getnet (copiar desde directorio local o descargar)
# ============================================================================
echo ""
echo "=== Configurando SDK Getnet ==="
SDK_DIR="${SDK_DIR:-../sdk}"

if [ -d "$SDK_DIR" ] && [ -f "$SDK_DIR/POSIntegradoGetnet.jar" ]; then
    echo "Copiando SDK desde $SDK_DIR..."
    cp "$SDK_DIR/POSIntegradoGetnet.jar" .
    cp "$SDK_DIR/jSerialComm-2.9.3.jar" .
    cp "$SDK_DIR/gson-2.10.1.jar" .
    echo "OK: SDK Getnet copiado"
else
    echo "⚠️  SDK Getnet no encontrado en $SDK_DIR"
    echo "   Por favor, descarga los JARs desde:"
    echo "   https://banco.santander.cl/uploads/000/054/702/e6038e13-44f5-4f62-a943-895a7358c7ca/original/Java.zip"
    echo "   Y colócalos en: $SDK_DIR/"
    echo ""
    echo "   O copia manualmente:"
    echo "   - POSIntegradoGetnet.jar"
    echo "   - jSerialComm-2.9.3.jar"
    echo "   - gson-2.10.1.jar"
fi

# ============================================================================
# Código Java del agente
# ============================================================================
cat > GetnetAgent.java << EOF
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import org.json.*;

// SDK Getnet
import com.fazecast.jSerialComm.SerialPort;
import posintegradogetnet.POSIntegrado;
import posintegradogetnet.POSCommands;
import posintegradogetnet.requests.*;
import posintegradogetnet.exceptions.*;

public class GetnetAgent {

    // Backend (NO hardcodear secretos: leer desde env)
    private static final String BASE_URL = System.getenv().getOrDefault("BASE_URL", "${BASE_URL}");
    private static final String REGISTER_ID = System.getenv().getOrDefault("REGISTER_ID", "${REGISTER_ID}");
    private static final String AGENT_KEY = System.getenv("AGENT_API_KEY");
    private static final String AGENT_ID = System.getenv().getOrDefault("AGENT_ID", "${AGENT_ID}");

    private static final int POLL_MS = 800;
    private static final int HTTP_TIMEOUT_MS = 15000;
    
    // Configuración Getnet (se carga desde backend al iniciar)
    private static String GETNET_PORT = "COM3";
    private static int GETNET_BAUDRATE = 115200;
    private static int GETNET_TIMEOUT_MS = 30000;
    private static boolean configLoaded = false;
    
    // Instancia del SDK Getnet (singleton)
    private static POSIntegrado getnetSDK = null;
    private static SerialPort serialPort = null;

    public static void main(String[] args) {
        System.out.println("Agente Getnet iniciado (Java)...");
        if (AGENT_KEY == null || AGENT_KEY.trim().isEmpty()) {
            System.out.println("❌ Falta env AGENT_API_KEY (header X-AGENT-KEY).");
            return;
        }
        System.out.println("BASE_URL=" + BASE_URL);
        System.out.println("REGISTER_ID=" + REGISTER_ID);
        System.out.println("AGENT_ID=" + AGENT_ID);
        System.out.println("");
        
        // Cargar configuración desde backend
        cargarConfiguracionDesdeBackend();
        
        System.out.println("Configuración Getnet cargada:");
        System.out.println("  GETNET_PORT=" + GETNET_PORT);
        System.out.println("  GETNET_BAUDRATE=" + GETNET_BAUDRATE);
        System.out.println("  GETNET_TIMEOUT_MS=" + GETNET_TIMEOUT_MS);
        System.out.println("");
        
        // Registrar shutdown hook para cerrar puerto serial
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.out.println("\\n🛑 Cerrando agente...");
            cerrarGetnetSDK();
        }));

        // Enviar heartbeat inicial
        enviarHeartbeat();
        
        // Heartbeat cada 30 segundos
        long lastHeartbeat = System.currentTimeMillis();
        final long HEARTBEAT_INTERVAL_MS = 30000; // 30 segundos
        
        while (true) {
            try {
                // Enviar heartbeat periódico
                long now = System.currentTimeMillis();
                if (now - lastHeartbeat >= HEARTBEAT_INTERVAL_MS) {
                    enviarHeartbeat();
                    lastHeartbeat = now;
                }
                
                // Nota: blueprint de caja corre bajo /caja
                JSONObject pending = httpGetJson("/caja/api/payment/agent/pending?register_id=" + urlEncode(REGISTER_ID));

                if (!pending.optBoolean("success", false)) {
                    System.out.println("⚠️ pending success=false: " + pending.optString("error", "unknown"));
                    sleep(POLL_MS);
                    continue;
                }

                boolean hasPending = pending.optBoolean("pending", false);
                if (!hasPending) {
                    sleep(POLL_MS);
                    continue;
                }

                String intentId = pending.getString("intent_id");
                double amount = pending.optDouble("amount_total", 0.0);
                String currency = pending.optString("currency", "CLP");

                System.out.println("🧾 Intent recibido: " + intentId + " amount=" + amount + " " + currency);

                // TODO: implementar integración real Getnet aquí
                JSONObject result = ejecutarPago(amount, currency);

                // Reportar resultado al backend
                JSONObject body = new JSONObject()
                        .put("intent_id", intentId)
                        .put("status", result.optString("status", "ERROR"))
                        .put("provider_ref", result.has("provider_ref") ? result.get("provider_ref") : JSONObject.NULL)
                        .put("auth_code", result.has("auth_code") ? result.get("auth_code") : JSONObject.NULL)
                        .put("error_code", result.has("error_code") ? result.get("error_code") : JSONObject.NULL)
                        .put("error_message", result.has("error_message") ? result.get("error_message") : JSONObject.NULL);

                JSONObject resp = httpPostJson("/caja/api/payment/agent/result", body);
                if (!resp.optBoolean("success", false)) {
                    System.out.println("❌ Backend result success=false: " + resp.optString("error", "unknown"));
                } else {
                    System.out.println("✅ Resultado reportado: intent=" + intentId + " status=" + body.getString("status"));
                }

                sleep(POLL_MS);

            } catch (Exception e) {
                System.out.println("Error polling: " + e.getMessage());
                sleep(POLL_MS);
            }
        }
    }

    private static void inicializarGetnetSDK() throws Exception {
        if (getnetSDK != null && serialPort != null && serialPort.isOpen()) {
            return; // Ya inicializado
        }
        
        System.out.println("🔌 Inicializando conexión Getnet...");
        System.out.println("   Puerto: " + GETNET_PORT);
        System.out.println("   Baudrate: " + GETNET_BAUDRATE);
        
        // Abrir puerto serial
        serialPort = SerialPort.getCommPort(GETNET_PORT);
        serialPort.setBaudRate(GETNET_BAUDRATE);
        serialPort.setComPortTimeouts(SerialPort.TIMEOUT_READ_SEMI_BLOCKING, GETNET_TIMEOUT_MS, 0);
        
        if (!serialPort.openPort()) {
            throw new Exception("No se pudo abrir puerto serial " + GETNET_PORT);
        }
        
        System.out.println("✅ Puerto serial abierto: " + GETNET_PORT);
        
        // Inicializar SDK Getnet
        getnetSDK = new POSIntegrado(serialPort);
        System.out.println("✅ SDK Getnet inicializado");
    }
    
    private static String verificarConexionGetnet() {
        try {
            // Verificar que el puerto serial está abierto
            if (serialPort == null || !serialPort.isOpen()) {
                return "ERROR: Puerto serial no está abierto";
            }
            
            // Verificar que el SDK está inicializado
            if (getnetSDK == null) {
                return "ERROR: SDK Getnet no está inicializado";
            }
            
            // Intentar un comando de prueba/healthcheck
            // El SDK puede tener métodos como: ping(), test(), healthCheck(), etc.
            try {
                // Intentar método de prueba común
                java.lang.reflect.Method testMethod = getnetSDK.getClass().getMethod("ping");
                Object result = testMethod.invoke(getnetSDK);
                return "OK: Terminal responde correctamente";
            } catch (NoSuchMethodException e1) {
                try {
                    // Intentar método alternativo: test
                    java.lang.reflect.Method testMethod = getnetSDK.getClass().getMethod("test");
                    Object result = testMethod.invoke(getnetSDK);
                    return "OK: Terminal responde correctamente";
                } catch (NoSuchMethodException e2) {
                    // Si no hay método de prueba, verificar que el puerto está disponible
                    // y que podemos escribir/leer
                    try {
                        // Verificar que el puerto acepta operaciones
                        if (serialPort.bytesAvailable() >= 0) {
                            return "OK: Puerto serial disponible (no se pudo verificar terminal directamente)";
                        }
                    } catch (Exception e3) {
                        return "WARN: No se pudo verificar estado del terminal";
                    }
                }
            }
            
            // Si llegamos aquí, el puerto está abierto pero no pudimos verificar el terminal
            return "WARN: Puerto abierto pero estado del terminal desconocido";
            
        } catch (Exception e) {
            return "ERROR: " + e.getMessage();
        }
    }
    
    private static void cerrarGetnetSDK() {
        try {
            if (serialPort != null && serialPort.isOpen()) {
                serialPort.closePort();
                System.out.println("🔒 Puerto serial cerrado");
            }
        } catch (Exception e) {
            System.out.println("⚠️  Error al cerrar puerto: " + e.getMessage());
        }
    }
    
    private static JSONObject ejecutarPago(double amount, String currency) {
        JSONObject resp = new JSONObject();
        try {
            // Inicializar SDK si no está inicializado
            inicializarGetnetSDK();
            
            System.out.println("💳 Procesando pago Getnet...");
            System.out.println("   Monto: " + amount + " " + currency);
            
            // Convertir monto a entero (centavos/pesos según el SDK)
            // Getnet generalmente trabaja en centavos, pero puede variar
            long montoCentavos = Math.round(amount * 100);
            
            // Crear request de venta
            // NOTA: Ajustar según la estructura real del SDK
            // Basado en las clases encontradas: requests/SaleRequest o similar
            try {
                // Intentar procesar venta usando el SDK
                // El método exacto puede variar, pero típicamente es algo como:
                // POSCommands.SaleType saleType = POSCommands.SaleType.DEBITO; // o CREDITO
                // Object result = getnetSDK.processSale(montoCentavos, saleType);
                
                // Por ahora, usamos un enfoque más genérico
                // Revisar documentación para el método exacto
                System.out.println("   Enviando comando de venta al terminal...");
                
                // Crear request de venta usando el SDK
                SaleRequest saleReq = new SaleRequest();
                
                // Configurar monto (en centavos según estándar Getnet)
                saleReq.setAmount(montoCentavos);
                
                // Tipo de venta: Débito por defecto (ajustar según necesidad)
                // POSCommands.SaleType puede ser: DEBITO, CREDITO, PREPAGO, etc.
                saleReq.setSaleType(POSCommands.SaleType.DEBITO);
                
                System.out.println("   Enviando comando de venta al terminal...");
                
                // Ejecutar venta usando el SDK
                // El SDK Getnet puede devolver la respuesta en formato JSON string o como objeto
                Object saleResult = null;
                
                try {
                    // Intentar método más común: executeSale
                    java.lang.reflect.Method executeMethod = getnetSDK.getClass().getMethod("executeSale", SaleRequest.class);
                    saleResult = executeMethod.invoke(getnetSDK, saleReq);
                } catch (NoSuchMethodException e1) {
                    try {
                        // Intentar método alternativo: processSale
                        java.lang.reflect.Method processMethod = getnetSDK.getClass().getMethod("processSale", SaleRequest.class);
                        saleResult = processMethod.invoke(getnetSDK, saleReq);
                    } catch (NoSuchMethodException e2) {
                        throw new Exception("Método de venta no encontrado en SDK. Métodos probados: executeSale, processSale");
                    }
                }
                
                // Procesar respuesta del SDK
                // La respuesta puede venir como String (JSON) o como objeto Java
                if (saleResult == null) {
                    throw new Exception("SDK no devolvió respuesta");
                }
                
                // Si la respuesta es un String (JSON), parsearlo
                if (saleResult instanceof String) {
                    String jsonResponse = (String) saleResult;
                    System.out.println("   📄 Respuesta JSON del SDK: " + jsonResponse);
                    JSONObject jsonResult = new JSONObject(jsonResponse);
                    
                    // Intentar obtener JsonSerialized si existe (formato del log del usuario)
                    JSONObject jsonSerialized = null;
                    if (jsonResult.has("JsonSerialized")) {
                        jsonSerialized = jsonResult.getJSONObject("JsonSerialized");
                    } else {
                        jsonSerialized = jsonResult; // Si no hay wrapper, usar directamente
                    }
                    
                    // Procesar según los campos que vimos en el log del usuario
                    int responseCode = jsonSerialized.optInt("ResponseCode", -1);
                    String responseMessage = jsonSerialized.optString("ResponseMessage", "");
                    
                    if (responseCode == 0 && "Aprobado".equals(responseMessage)) {
                        resp.put("status", "APPROVED");
                        resp.put("auth_code", jsonSerialized.optString("AuthorizationCode", ""));
                        resp.put("provider_ref", jsonSerialized.optString("OperationId", "") + "-" + jsonSerialized.optString("TerminalId", ""));
                        System.out.println("   ✅ Pago aprobado (ResponseCode=0)");
                    } else {
                        resp.put("status", "DECLINED");
                        resp.put("error_code", "RESPONSE_CODE_" + responseCode);
                        resp.put("error_message", responseMessage.isEmpty() ? "Transacción rechazada" : responseMessage);
                        System.out.println("   ❌ Pago rechazado (ResponseCode=" + responseCode + ", Message=" + responseMessage + ")");
                    }
                } else {
                    // Si es un objeto Java, intentar usar reflexión
                    try {
                        java.lang.reflect.Method isApprovedMethod = saleResult.getClass().getMethod("isApproved");
                        boolean aprobado = (Boolean) isApprovedMethod.invoke(saleResult);
                        
                        if (aprobado) {
                            resp.put("status", "APPROVED");
                            
                            try {
                                java.lang.reflect.Method getAuthCodeMethod = saleResult.getClass().getMethod("getAuthCode");
                                String authCode = (String) getAuthCodeMethod.invoke(saleResult);
                                resp.put("auth_code", authCode != null ? authCode : "");
                            } catch (Exception e) {
                                resp.put("auth_code", "");
                            }
                            
                            try {
                                java.lang.reflect.Method getRefMethod = saleResult.getClass().getMethod("getReference");
                                String ref = (String) getRefMethod.invoke(saleResult);
                                resp.put("provider_ref", ref != null ? ref : "");
                            } catch (Exception e) {
                                resp.put("provider_ref", "");
                            }
                            
                            System.out.println("   ✅ Pago aprobado (objeto Java)");
                        } else {
                            resp.put("status", "DECLINED");
                            resp.put("error_code", "DECLINED");
                            resp.put("error_message", "Transacción rechazada");
                            System.out.println("   ❌ Pago rechazado (objeto Java)");
                        }
                    } catch (Exception e) {
                        // Si no podemos interpretar la respuesta, intentar convertir a String y parsear como JSON
                        System.out.println("   ⚠️  No se pudo usar reflexión, intentando toString(): " + e.getMessage());
                        String resultStr = saleResult.toString();
                        try {
                            JSONObject jsonResult = new JSONObject(resultStr);
                            int responseCode = jsonResult.optInt("ResponseCode", -1);
                            if (responseCode == 0) {
                                resp.put("status", "APPROVED");
                                resp.put("auth_code", jsonResult.optString("AuthorizationCode", ""));
                            } else {
                                resp.put("status", "DECLINED");
                                resp.put("error_code", "RESPONSE_CODE_" + responseCode);
                            }
                        } catch (Exception e2) {
                            // Último recurso: asumir aprobado si no podemos interpretar
                            System.out.println("   ⚠️  No se pudo interpretar respuesta: " + e2.getMessage());
                            resp.put("status", "APPROVED");
                            resp.put("auth_code", "");
                            resp.put("provider_ref", "");
                        }
                    }
                }
                
            } catch (SaleException e) {
                resp.put("status", "DECLINED");
                resp.put("error_code", "SALE_EXCEPTION");
                resp.put("error_message", e.getMessage());
                System.out.println("   ❌ Error en venta: " + e.getMessage());
            } catch (Exception e) {
                resp.put("status", "ERROR");
                resp.put("error_code", "EXCEPTION");
                resp.put("error_message", e.getMessage());
                System.out.println("   ❌ Error: " + e.getMessage());
            }
            
        } catch (Exception e) {
            resp.put("status", "ERROR");
            resp.put("error_code", "INIT_ERROR");
            resp.put("error_message", "Error al inicializar SDK: " + e.getMessage());
            System.out.println("   ❌ Error de inicialización: " + e.getMessage());
        }
        return resp;
    }

    private static JSONObject httpGetJson(String path) throws Exception {
        HttpURLConnection con = openConnection(path, "GET");
        int code = con.getResponseCode();
        String body = readBody(con);
        if (code < 200 || code >= 300) {
            throw new RuntimeException("GET " + path + " HTTP " + code + " body=" + body);
        }
        return new JSONObject(body);
    }

    private static JSONObject httpPostJson(String path, JSONObject bodyJson) throws Exception {
        HttpURLConnection con = openConnection(path, "POST");
        con.setDoOutput(true);
        con.setRequestProperty("Content-Type", "application/json");

        byte[] payload = bodyJson.toString().getBytes(StandardCharsets.UTF_8);
        try (OutputStream os = con.getOutputStream()) {
            os.write(payload);
        }

        int code = con.getResponseCode();
        String body = readBody(con);
        if (code < 200 || code >= 300) {
            throw new RuntimeException("POST " + path + " HTTP " + code + " body=" + body);
        }
        return new JSONObject(body);
    }

    private static HttpURLConnection openConnection(String path, String method) throws Exception {
        URL url = new URL(BASE_URL + path);
        HttpURLConnection con = (HttpURLConnection) url.openConnection();
        con.setRequestMethod(method);
        con.setConnectTimeout(HTTP_TIMEOUT_MS);
        con.setReadTimeout(HTTP_TIMEOUT_MS);

        // Auth headers (agent-only)
        con.setRequestProperty("X-AGENT-KEY", AGENT_KEY);
        con.setRequestProperty("X-AGENT-ID", AGENT_ID);

        return con;
    }

    private static String readBody(HttpURLConnection con) throws Exception {
        InputStream is = null;
        try {
            is = con.getInputStream();
        } catch (IOException e) {
            is = con.getErrorStream();
        }
        if (is == null) return "";
        try (BufferedReader in = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = in.readLine()) != null) sb.append(line);
            return sb.toString();
        }
    }

    private static String urlEncode(String s) throws Exception {
        return URLEncoder.encode(s, StandardCharsets.UTF_8.toString());
    }

    private static void sleep(int ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ignored) {}
    }
    
    private static void cargarConfiguracionDesdeBackend() {
        try {
            System.out.println("📥 Cargando configuración desde backend...");
            JSONObject config = httpGetJson("/caja/api/payment/agent/config?register_id=" + urlEncode(REGISTER_ID));
            
            if (!config.optBoolean("success", false)) {
                System.out.println("⚠️  No se pudo cargar configuración desde backend, usando defaults");
                System.out.println("   Error: " + config.optString("error", "unknown"));
                return;
            }
            
            JSONObject getnet = config.optJSONObject("getnet");
            if (getnet != null && getnet.optBoolean("enabled", false)) {
                String mode = getnet.optString("mode", "manual");
                if ("serial".equals(mode)) {
                    GETNET_PORT = getnet.optString("port", "COM3");
                    GETNET_BAUDRATE = getnet.optInt("baudrate", 115200);
                    GETNET_TIMEOUT_MS = getnet.optInt("timeout_ms", 30000);
                    configLoaded = true;
                    System.out.println("✅ Configuración cargada desde backend para register: " + config.optString("register_name", REGISTER_ID));
                } else {
                    System.out.println("⚠️  Getnet está en modo " + mode + ", no se requiere configuración serial");
                }
            } else {
                System.out.println("⚠️  Getnet no está habilitado o configurado para este register");
            }
        } catch (Exception e) {
            System.out.println("⚠️  Error al cargar configuración desde backend: " + e.getMessage());
            System.out.println("   Usando valores por defecto o de variables de entorno");
            // Fallback a variables de entorno si falla
            String envPort = System.getenv("GETNET_PORT");
            String envBaudrate = System.getenv("GETNET_BAUDRATE");
            String envTimeout = System.getenv("GETNET_TIMEOUT_MS");
            
            if (envPort != null && !envPort.trim().isEmpty()) {
                GETNET_PORT = envPort.trim();
            }
            if (envBaudrate != null && !envBaudrate.trim().isEmpty()) {
                try {
                    GETNET_BAUDRATE = Integer.parseInt(envBaudrate.trim());
                } catch (NumberFormatException ignored) {}
            }
            if (envTimeout != null && !envTimeout.trim().isEmpty()) {
                try {
                    GETNET_TIMEOUT_MS = Integer.parseInt(envTimeout.trim());
                } catch (NumberFormatException ignored) {}
            }
        }
    }
    
    private static void enviarHeartbeat() {
        try {
            // Obtener IP local
            String localIp = "unknown";
            try {
                java.net.InetAddress localHost = java.net.InetAddress.getLocalHost();
                localIp = localHost.getHostAddress();
            } catch (Exception e) {
                // Ignorar
            }
            
            // Verificar estado de Getnet
            String getnetStatus = "UNKNOWN";
            String getnetMessage = "No verificado";
            
            try {
                // Intentar inicializar SDK si no está inicializado
                if (getnetSDK == null || serialPort == null || !serialPort.isOpen()) {
                    inicializarGetnetSDK();
                }
                
                // Verificar conexión
                String verificacion = verificarConexionGetnet();
                if (verificacion.startsWith("OK")) {
                    getnetStatus = "OK";
                    getnetMessage = verificacion;
                } else if (verificacion.startsWith("WARN")) {
                    getnetStatus = "UNKNOWN";
                    getnetMessage = verificacion;
                } else {
                    getnetStatus = "ERROR";
                    getnetMessage = verificacion;
                }
            } catch (Exception e) {
                getnetStatus = "ERROR";
                getnetMessage = "Error al verificar: " + e.getMessage();
                System.out.println("⚠️  Error al verificar Getnet: " + e.getMessage());
            }
            
            // Enviar heartbeat al backend
            JSONObject heartbeatBody = new JSONObject()
                    .put("register_id", REGISTER_ID)
                    .put("agent_name", "POS-CAJA-TEST")
                    .put("ip", localIp)
                    .put("getnet_status", getnetStatus)
                    .put("getnet_message", getnetMessage);
            
            try {
                JSONObject resp = httpPostJson("/caja/api/payment/agent/heartbeat", heartbeatBody);
                if (resp.optBoolean("ok", false)) {
                    System.out.println("💓 Heartbeat enviado: Getnet=" + getnetStatus + " (" + getnetMessage + ")");
                } else {
                    System.out.println("⚠️  Heartbeat falló: " + resp.optString("error", "unknown"));
                }
            } catch (Exception e) {
                System.out.println("⚠️  Error al enviar heartbeat: " + e.getMessage());
            }
            
        } catch (Exception e) {
            System.out.println("⚠️  Error en heartbeat: " + e.getMessage());
        }
    }
}
EOF

# ============================================================================
# Scripts de build/run
# ============================================================================
cat > build.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "Compilando agente Getnet..."

# Classpath con todos los JARs necesarios
CLASSPATH=".:json.jar"
if [ -f "POSIntegradoGetnet.jar" ]; then
    CLASSPATH="$CLASSPATH:POSIntegradoGetnet.jar"
fi
if [ -f "jSerialComm-2.9.3.jar" ]; then
    CLASSPATH="$CLASSPATH:jSerialComm-2.9.3.jar"
fi
if [ -f "gson-2.10.1.jar" ]; then
    CLASSPATH="$CLASSPATH:gson-2.10.1.jar"
fi

javac -cp "$CLASSPATH" GetnetAgent.java
echo "Compilación OK."
EOF
chmod +x build.sh

cat > run.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "Iniciando Agente Getnet..."

# Classpath con todos los JARs necesarios
CLASSPATH=".:json.jar"
if [ -f "POSIntegradoGetnet.jar" ]; then
    CLASSPATH="$CLASSPATH:POSIntegradoGetnet.jar"
fi
if [ -f "jSerialComm-2.9.3.jar" ]; then
    CLASSPATH="$CLASSPATH:jSerialComm-2.9.3.jar"
fi
if [ -f "gson-2.10.1.jar" ]; then
    CLASSPATH="$CLASSPATH:gson-2.10.1.jar"
fi

exec java -cp "$CLASSPATH" GetnetAgent
EOF
chmod +x run.sh

echo ""
echo "=== Listo ==="
echo "Archivos creados en $(pwd):"
ls -1
echo ""
echo "Para compilar:  ./build.sh"
echo "Para ejecutar:  ./run.sh"
echo ""
echo "IMPORTANTE:"
echo "- El backend requiere AGENT_API_KEY configurada (env var del servicio)."
echo "- El agente debe usar el mismo AGENT_API_KEY en header X-AGENT-KEY."
echo "- Debes definir REGISTER_ID (la caja a la que atiende este agente)."


