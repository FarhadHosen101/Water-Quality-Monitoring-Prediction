/*
  AquaAI - Virtual ESP32 Water Quality Node for Wokwi Simulator
  Connects to virtual WiFi: Wokwi-GUEST
  Reads virtual sensors (knobs for pH, Turbidity, TDS, Temp)
  Streams telemetry to backend via HTTP POST
*/

#include <WiFi.h>
#include <HTTPClient.h>

// ====================== CONFIG ======================
// Replace with your public tunnel URL (e.g. from localtunnel or ngrok)
// Example: "https://your-subdomain.loca.lt/api/readings"
const char* SERVER_URL = "http://localhost:8000/api/readings"; 
const char* API_KEY    = "CHANGE_ME";
const char* NODE_ID    = "node-01";

const unsigned long SEND_INTERVAL_MS = 5000; // 5 seconds in simulation

// Pins matching Wokwi diagram.json
#define PIN_PH    34
#define PIN_TURB  35
#define PIN_TDS   32
#define PIN_TEMP  33

unsigned long lastSend = 0;

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("Connecting to Wokwi-GUEST WiFi");
  WiFi.mode(WIFI_STA);
  WiFi.begin("Wokwi-GUEST", "", 6);
  
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(250);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("\n✅ Connected! Virtual IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n⚠️ WiFi connection retry...");
  }
}

bool sendReading(float ph, float turb, float temp, float tds) {
  if (WiFi.status() != WL_CONNECTED) return false;

  char body[256];
  snprintf(body, sizeof(body),
           "{\"node_id\":\"%s\",\"ph\":%.2f,\"turbidity\":%.1f,\"do\":5.5,\"temp\":%.2f,\"tds\":%.1f}",
           NODE_ID, ph, turb, temp, tds);

  WiFiClient client;
  HTTPClient http;
  http.begin(client, SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  
  int code = http.POST(body);
  Serial.printf("📡 POST %s -> HTTP %d\n", body, code);
  http.end();
  return code >= 200 && code < 300;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("==========================================");
  Serial.println("💧 AquaAI - Wokwi Online Virtual ESP32 Node");
  Serial.println("==========================================");
  connectWiFi();
}

void loop() {
  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();
    connectWiFi();

    // Read analog values from potentiometers (0 to 4095 on ESP32 ADC)
    int raw_ph   = analogRead(PIN_PH);
    int raw_turb = analogRead(PIN_TURB);
    int raw_tds  = analogRead(PIN_TDS);
    int raw_temp = analogRead(PIN_TEMP);

    // Map to realistic physical water units
    float ph   = (raw_ph / 4095.0) * 14.0;              // 0.0 to 14.0
    float turb = (raw_turb / 4095.0) * 120.0;           // 0.0 to 120.0 NTU
    float tds  = 50.0 + (raw_tds / 4095.0) * 1450.0;    // 50 to 1500 ppm
    float temp = 15.0 + (raw_temp / 4095.0) * 30.0;     // 15.0 to 45.0 °C

    Serial.printf("\n[SENSORS] pH=%.2f | Turb=%.1f NTU | TDS=%.1f ppm | Temp=%.1f C\n", ph, turb, tds, temp);

    if (!sendReading(ph, turb, temp, tds)) {
      Serial.println("⚠️ Send failed. Check SERVER_URL or tunnel.");
    }
  }
}
