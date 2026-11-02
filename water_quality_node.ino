/*
  AI-Based Water Quality Monitoring - ESP32 sensor node
  Reads: pH, turbidity, TDS, temperature (DS18B20), optional dissolved oxygen
  Sends: JSON over HTTP POST to your backend every SEND_INTERVAL_MS

  Libraries (Arduino IDE > Library Manager):
    - OneWire
    - DallasTemperature
  Board: "ESP32 Dev Module" (esp32 by Espressif, core 2.x or newer)

  IMPORTANT: ESP32 ADC pins accept 3.3 V maximum.
  pH and turbidity modules often output up to 5 V, so put a voltage divider
  (10k from sensor output to the pin, 20k from the pin to GND = factor 1.5)
  and set the matching *_DIVIDER value below.
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ====================== CONFIG ======================
const char* WIFI_SSID  = "YOUR_WIFI_NAME";
const char* WIFI_PASS  = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL = "https://project-ai-rust-mu.vercel.app/api/readings";  // Or local: "http://YOUR_SERVER_IP:8000/api/readings"
const char* API_KEY    = "CHANGE_ME";
const char* NODE_ID    = "node-01";

const unsigned long SEND_INTERVAL_MS = 15000;   // 15 seconds between readings

// ====================== PINS (use ADC1 pins: 32-39) ======================
#define PIN_PH    34
#define PIN_TURB  35
#define PIN_TDS   32
#define PIN_DO    33
#define PIN_TEMP  4     // DS18B20 data pin, 4.7k pull-up resistor to 3.3 V

#define ENABLE_DO false // set true only when the DO sensor is connected

// ====================== VOLTAGE DIVIDER FACTORS ======================
// 1.0 = sensor wired directly, 1.5 = 10k/20k divider
const float PH_DIVIDER   = 1.5;
const float TURB_DIVIDER = 1.5;
const float TDS_DIVIDER  = 1.0;
const float DO_DIVIDER   = 1.0;

// ====================== CALIBRATION VALUES (replace after calibrating!) ======================
// pH: measure the sensor voltage in pH 7.00 and pH 4.01 buffer solutions
const float PH_V7 = 2.50;   // volts in pH 7.00 buffer  (placeholder)
const float PH_V4 = 3.00;   // volts in pH 4.01 buffer  (placeholder)

// DO (simplified linear model): volts in zero-oxygen solution and in air-saturated water at 25 C
const float DO_V0   = 0.00;  // placeholder
const float DO_VSAT = 1.60;  // placeholder
const float DO_SAT_25C = 8.26; // mg/L saturation at 25 C

// ====================== OBJECTS ======================
OneWire oneWire(PIN_TEMP);
DallasTemperature tempSensor(&oneWire);
unsigned long lastSend = 0;

// ====================== HELPERS ======================
// Average of 30 samples, returns volts at the SENSOR output (divider undone)
float readVolts(int pin, float divider) {
  uint32_t sum = 0;
  for (int i = 0; i < 30; i++) {
    sum += analogReadMilliVolts(pin);
    delay(5);
  }
  return (sum / 30.0f / 1000.0f) * divider;
}

float readTemperatureC() {
  tempSensor.requestTemperatures();
  float t = tempSensor.getTempCByIndex(0);
  if (t == DEVICE_DISCONNECTED_C || t < -20 || t > 85) {
    Serial.println("Temperature sensor error, using 25 C");
    return 25.0f;
  }
  return t;
}

float readPH() {
  float v = readVolts(PIN_PH, PH_DIVIDER);
  float ph = 7.0f + (v - PH_V7) * (4.0f - 7.0f) / (PH_V4 - PH_V7);
  return constrain(ph, 0.0f, 14.0f);
}

// DFRobot Gravity analog turbidity formula, result in NTU. Verify with your own sensor.
float readTurbidityNTU() {
  float v = readVolts(PIN_TURB, TURB_DIVIDER);
  if (v < 2.5f) return 3000.0f;   // very dirty / sensor out of range low
  float ntu = -1120.4f * v * v + 5742.3f * v - 4352.9f;
  return constrain(ntu, 0.0f, 3000.0f);
}

// DFRobot Gravity TDS formula with temperature compensation, result in ppm
float readTDS(float tempC) {
  float v = readVolts(PIN_TDS, TDS_DIVIDER);
  float comp = 1.0f + 0.02f * (tempC - 25.0f);
  float vc = v / comp;
  float tds = (133.42f * vc * vc * vc - 255.86f * vc * vc + 857.39f * vc) * 0.5f;
  return max(tds, 0.0f);
}

// Simplified linear DO estimate in mg/L (calibrate properly for real use)
float readDO() {
  float v = readVolts(PIN_DO, DO_DIVIDER);
  float d = (v - DO_V0) / (DO_VSAT - DO_V0) * DO_SAT_25C;
  return constrain(d, 0.0f, 20.0f);
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("\nConnected, IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi failed, will retry next cycle");
  }
}

bool sendReading(float ph, float turb, float doVal, float temp, float tds) {
  if (WiFi.status() != WL_CONNECTED) return false;

  char doStr[16];
  if (ENABLE_DO) snprintf(doStr, sizeof(doStr), "%.2f", doVal);
  else strcpy(doStr, "null");

  char body[256];
  snprintf(body, sizeof(body),
           "{\"node_id\":\"%s\",\"ph\":%.2f,\"turbidity\":%.1f,\"do\":%s,\"temp\":%.2f,\"tds\":%.1f}",
           NODE_ID, ph, turb, doStr, temp, tds);

  WiFiClient client;
  HTTPClient http;
  http.begin(client, SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  int code = http.POST(body);
  Serial.printf("POST %s -> HTTP %d\n", body, code);
  http.end();
  return code >= 200 && code < 300;
}

// ====================== MAIN ======================
void setup() {
  Serial.begin(115200);
  delay(500);
  analogSetAttenuation(ADC_11db);   // 0 to ~3.1 V input range
  tempSensor.begin();
  connectWiFi();
  Serial.println("Water quality node ready");
}

void loop() {
  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();
    connectWiFi();

    float temp = readTemperatureC();
    float ph   = readPH();
    float turb = readTurbidityNTU();
    float tds  = readTDS(temp);
    float doV  = ENABLE_DO ? readDO() : 0.0f;

    Serial.printf("pH=%.2f  Turb=%.1f NTU  TDS=%.1f ppm  Temp=%.2f C", ph, turb, tds, temp);
    if (ENABLE_DO) Serial.printf("  DO=%.2f mg/L", doV);
    Serial.println();

    if (!sendReading(ph, turb, doV, temp, tds)) {
      Serial.println("Send failed (check WiFi, server IP, firewall, API key)");
    }
  }
}
