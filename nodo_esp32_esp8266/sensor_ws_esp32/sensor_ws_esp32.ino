/*
 * sensor_ws_esp32.ino — Sensor DHT22 vía WebSocket (ESP32)
 *
 * Envía temperatura y humedad al hub por WSS cada 30 segundos.
 * La conexión WebSocket es persistente y se reconecta automáticamente.
 *
 * Librerías requeridas (Library Manager):
 *   - DHT sensor library (Adafruit)
 *   - WebSockets by Markus Sattler
 *   - ArduinoJson (Benoit Blanchon)
 */

#include "portal_ws.h"
#include <DHT.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

#define DHT_PIN      4
#define DHT_TYPE     DHT22
#define INTERVALO_MS 30000
#define API_KEY      "tu-clave-secreta-123"

DHT dht(DHT_PIN, DHT_TYPE);
WebSocketsClient wsClient;
unsigned long ultimaLectura = 0;
bool wsConectado = false;

SensorInfo sensores[] = {
  { "temperature", "\xC2\xB0""C" },
  { "humidity",    "%" },
};
ActuadorInfo actuadores[] = {};


void onWsEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      wsConectado = false;
      Serial.println("[WS] Desconectado. Reconectando...");
      break;
    case WStype_CONNECTED:
      wsConectado = true;
      Serial.println("[WS] Conectado al hub.");
      break;
    case WStype_TEXT:
      // El hub puede enviar cambios de actuadores (ignorados en este dispositivo)
      break;
    default:
      break;
  }
}

void enviarLecturas(float temp, float hum) {
  if (!wsConectado) return;

  JsonDocument doc;
  JsonArray lecturas = doc["lecturas"].to<JsonArray>();

  JsonObject l1 = lecturas.add<JsonObject>();
  l1["sensor_id"] = cfg.sensorIds[0];
  l1["valor"]     = temp;

  JsonObject l2 = lecturas.add<JsonObject>();
  l2["sensor_id"] = cfg.sensorIds[1];
  l2["valor"]     = hum;

  String msg;
  serializeJson(doc, msg);
  wsClient.sendTXT(msg);
  Serial.printf("[WS] Enviado → temp: %.1f°C  hum: %.1f%%\n", temp, hum);
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  portalSetup(sensores, 2, actuadores, 0);
  if (!configurado) return;

  dht.begin();

  String path = "/ws/dispositivo/" + String(cfg.dispositivoId) + "/datos?api_key=" + String(API_KEY);
  wsClient.beginSSL(WS_HOST, WS_PORT, path);
  wsClient.onEvent(onWsEvent);
  wsClient.setReconnectInterval(5000);

  Serial.printf("[WS] Conectando a wss://%s%s\n", WS_HOST, path.c_str());
  Serial.printf("[Sensores] temp_id: %d  hum_id: %d\n", cfg.sensorIds[0], cfg.sensorIds[1]);
}

void loop() {
  portalLoop();
  if (!configurado) return;

  wsClient.loop();

  if (millis() - ultimaLectura >= INTERVALO_MS) {
    ultimaLectura = millis();

    float temp = dht.readTemperature();
    float hum  = dht.readHumidity();

    if (isnan(temp) || isnan(hum)) {
      Serial.println("[DHT] Error de lectura.");
      return;
    }
    Serial.printf("[DHT] Temp: %.1f°C  Hum: %.1f%%\n", temp, hum);
    enviarLecturas(temp, hum);
  }
}
