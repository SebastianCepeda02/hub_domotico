/*
 * rele_ws_esp32.ino — Relé vía WebSocket (ESP32)
 *
 * Se conecta al hub por WSS y recibe cambios de estado en tiempo real.
 * Al conectar, el hub envía el estado actual inmediatamente.
 * Envía heartbeat cada 60 s para mantener ultimo_contacto actualizado.
 *
 * Librerías requeridas (Library Manager):
 *   - WebSockets by Markus Sattler
 *   - ArduinoJson (Benoit Blanchon)
 */

#include "portal_ws.h"
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

#define RELAY_PIN      16
#define HEARTBEAT_MS   60000
#define API_KEY        "tu-clave-secreta-123"

WebSocketsClient wsClient;
unsigned long ultimoHeartbeat = 0;
bool wsConectado = false;

SensorInfo   sensores[]   = {};
ActuadorInfo actuadores[] = {
  { "relay", RELAY_PIN },
};


void aplicarEstado(const char* estado) {
  bool encendido = (strcmp(estado, "on") == 0);
  digitalWrite(RELAY_PIN, encendido ? LOW : HIGH);  // relé activo en LOW
  Serial.printf("[Relé] Estado → %s\n", estado);
}

void onWsEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      wsConectado = false;
      Serial.println("[WS] Desconectado.");
      break;

    case WStype_CONNECTED:
      wsConectado = true;
      Serial.println("[WS] Conectado al hub. Esperando estado inicial...");
      break;

    case WStype_TEXT: {
      // Mensaje del hub: {"actuadores": [{"actuador_id": X, "estado": "on/off"}]}
      JsonDocument doc;
      if (!deserializeJson(doc, payload, length)) {
        JsonArray actuadoresArr = doc["actuadores"].as<JsonArray>();
        for (JsonObject a : actuadoresArr) {
          int id = a["actuador_id"].as<int>();
          if (id == cfg.actuadorIds[0]) {
            aplicarEstado(a["estado"].as<const char*>());
          }
        }
      }
      break;
    }

    default:
      break;
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  portalSetup(sensores, 0, actuadores, 1);
  if (!configurado) return;

  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH);  // apagado al arrancar

  String path = "/ws/dispositivo/" + String(cfg.dispositivoId) + "/datos?api_key=" + String(API_KEY);
  wsClient.beginSSL(WS_HOST, WS_PORT, path);
  wsClient.onEvent(onWsEvent);
  wsClient.setReconnectInterval(5000);

  Serial.printf("[WS] Conectando a wss://%s%s\n", WS_HOST, path.c_str());
  Serial.printf("[Relé] actuador_id: %d  pin: %d\n", cfg.actuadorIds[0], RELAY_PIN);
}

void loop() {
  portalLoop();
  if (!configurado) return;

  wsClient.loop();

  // Heartbeat para mantener ultimo_contacto actualizado
  if (wsConectado && millis() - ultimoHeartbeat >= HEARTBEAT_MS) {
    ultimoHeartbeat = millis();
    wsClient.sendTXT("{\"heartbeat\":true}");
    Serial.println("[WS] Heartbeat enviado.");
  }
}
