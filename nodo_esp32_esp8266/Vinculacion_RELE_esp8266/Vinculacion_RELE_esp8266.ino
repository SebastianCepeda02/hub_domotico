/*
 * MiDispositivo.ino — Actuador Relé
 *
 * Consulta el estado del actuador en el hub cada 5 segundos
 * y activa/desactiva el relé según la respuesta.
 */

#include "portal.h"
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>

// ─── Pines y constantes ───────────────────────────────────────────────────────
#define RELAY_PIN    16        // GPIO16 (D0)
#define INTERVALO_MS 5000     // consultar hub cada 5 segundos
#define API_KEY      "tu-clave-secreta-123"

// ─── Variables globales ───────────────────────────────────────────────────────
unsigned long ultimaConsulta = 0;
bool          estadoActual   = false;

// ─── Sensores y actuadores ────────────────────────────────────────────────────
SensorInfo   sensores[]   = {};
ActuadorInfo actuadores[] = {
  { "relay", RELAY_PIN },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────
// --- Mover a Variables Globales (fuera de las funciones) ---
WiFiClientSecure clienteGlobal;
HTTPClient http;

void consultarEstado(int id) {
// 1. Forzar limpieza si el objeto quedó en un estado extraño
  http.end(); 

  clienteGlobal.setInsecure();
  // Buffer ligeramente más grande para el handshake inicial
  clienteGlobal.setBufferSizes(1024, 1024); 
  
  String url = String(HUB_URL) + "/actuadores/" + String(id);

  if (http.begin(clienteGlobal, url)) {
    http.addHeader("X-API-Key", API_KEY);
    http.addHeader("User-Agent", "ESP8266");
    http.setReuse(true);
    http.setTimeout(7000); // No esperar más de 5 segundos

    int codigo = http.GET();

    if (codigo == 200) {
      StaticJsonDocument<128> doc;
      // Usar getStream es vital para no saturar la RAM
      DeserializationError error = deserializeJson(doc, http.getStream());
      
      if (!error) {
        bool on = (strcmp(doc["estado"] | "", "on") == 0);
        if (on != estadoActual) {
          estadoActual = on;
          digitalWrite(RELAY_PIN, on ? LOW : HIGH);
          Serial.printf("[Relé] %d -> %s\n", id, on ? "ON" : "OFF");
        }
      }
    } else {
      Serial.printf("[HTTP] Fallo %d\n", codigo);
      // LIMPIEZA AGRESIVA
      http.end();
      clienteGlobal.stop(); // Fuerza el cierre físico del socket TCP
      delay(500);
    }
  }
}

// ─── setup ───────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(1000);

  portalSetup(
    sensores,   0,
    actuadores, sizeof(actuadores) / sizeof(actuadores[0])
  );

  if (!configurado) return;

  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH);  // relé apagado al arrancar (activo en LOW)

  Serial.println("[Relé] Iniciado.");
  Serial.printf("[Hub] actuador relé id: %d\n", cfg.actuadorIds[0]);
}

// ─── loop ────────────────────────────────────────────────────────────────────
void loop() {
  portalLoop();
  if (!configurado) return;

  if (millis() - ultimaConsulta >= INTERVALO_MS) {
    ultimaConsulta = millis();
    consultarEstado(cfg.actuadorIds[0]);
  }
}