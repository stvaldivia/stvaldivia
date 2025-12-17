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
# Código Java del agente
# ============================================================================
cat > GetnetAgent.java << EOF
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import org.json.*;

public class GetnetAgent {

    // Backend
    private static final String BASE_URL = "${BASE_URL}";
    private static final String REGISTER_ID = "${REGISTER_ID}";
    private static final String AGENT_KEY = "${AGENT_API_KEY}";
    private static final String AGENT_ID = "${AGENT_ID}";

    private static final int POLL_MS = 800;
    private static final int HTTP_TIMEOUT_MS = 15000;

    public static void main(String[] args) {
        System.out.println("Agente Getnet iniciado (Java)...");
        System.out.println("BASE_URL=" + BASE_URL);
        System.out.println("REGISTER_ID=" + REGISTER_ID);
        System.out.println("AGENT_ID=" + AGENT_ID);
        System.out.println("");

        while (true) {
            try {
                JSONObject pending = httpGetJson("/api/payment/agent/pending?register_id=" + urlEncode(REGISTER_ID));

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
                        .put("provider_ref", result.optString("provider_ref", JSONObject.NULL))
                        .put("auth_code", result.optString("auth_code", JSONObject.NULL))
                        .put("error_code", result.optString("error_code", JSONObject.NULL))
                        .put("error_message", result.optString("error_message", JSONObject.NULL));

                JSONObject resp = httpPostJson("/api/payment/agent/result", body);
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

    private static JSONObject ejecutarPago(double amount, String currency) {
        JSONObject resp = new JSONObject();
        try {
            // TODO: reemplazar por SDK/DLL real de Getnet.
            // Simulación:
            boolean aprobado = true;

            if (aprobado) {
                resp.put("status", "APPROVED");
                resp.put("provider_ref", "SIM-" + System.currentTimeMillis());
                resp.put("auth_code", "SIM-AUTH");
            } else {
                resp.put("status", "DECLINED");
                resp.put("error_code", "DECLINED");
                resp.put("error_message", "rejected");
            }
        } catch (Exception e) {
            resp.put("status", "ERROR");
            resp.put("error_code", "EXCEPTION");
            resp.put("error_message", e.getMessage());
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
}
EOF

# ============================================================================
# Scripts de build/run
# ============================================================================
cat > build.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "Compilando agente Getnet..."
javac -cp .:json.jar GetnetAgent.java
echo "Compilación OK."
EOF
chmod +x build.sh

cat > run.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "Iniciando Agente Getnet..."
exec java -cp .:json.jar GetnetAgent
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


