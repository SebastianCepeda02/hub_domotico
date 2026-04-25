/*
 * MiDispositivo.ino — Sensor DHT11 (temperatura + humedad)
 *
 * Envía lecturas de temperatura y humedad al hub cada 30 segundos.
 * Los IDs de sensores son asignados por el hub al registrarse.
 */

#include "portal.h"
#include <DHT.h>
#include <ESP8266HTTPClient.h>
//#include <WiFiClient.h>

// metodo client->setInsecure()
#include <WiFiClientSecure.h>

// ─── Pines y constantes ───────────────────────────────────────────────────────
#define DHT_PIN      4        // GPIO4 (D2)
#define DHT_TYPE     DHT11
#define INTERVALO_MS 30000    // 30 segundos entre lecturas
#define API_KEY      "tu-clave-secreta-123"

// ─── Variables globales ───────────────────────────────────────────────────────
DHT          dht(DHT_PIN, DHT_TYPE);
unsigned long ultimaLectura = 0;

// ─── Sensores y actuadores ────────────────────────────────────────────────────
SensorInfo sensores[] = {
  { "temperature", "\xC2\xB0" "C" },  // °C en UTF-8
  { "humidity",    "%"         },
};
ActuadorInfo actuadores[] = {};

// ─── Helpers ──────────────────────────────────────────────────────────────────
/*
void enviarLectura(int sensorId, float valor) {
  //WiFiClient cliente;
  WiFiClientSecure cliente;
  cliente.setInsecure();
  cliente.setTimeout(10000);
  HTTPClient http;

  String url = String(HUB_URL) + "/sensores/" + String(sensorId) + "/lecturas";
  http.begin(cliente, url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key",    API_KEY);

  String body = "{\"valor\":" + String(valor, 1) + "}";
  int codigo  = http.POST(body);

  Serial.printf("[HTTP] sensor_id=%d valor=%.1f → %d\n", sensorId, valor, codigo);
  Serial.printf("[HTTP] Respuesta: %s\n", http.getString().c_str());
  http.end();
}*/
WiFiClientSecure clienteSensor;
HTTPClient httpSensor;

void enviarLectura(int sensorId, float valor) {
  // 1. Limpieza inicial del socket
  httpSensor.end();
  
  clienteSensor.setInsecure();
  clienteSensor.setBufferSizes(1024, 512); 

  String url = String(HUB_URL) + "/sensores/" + String(sensorId) + "/lecturas";

  if (httpSensor.begin(clienteSensor, url)) {
    httpSensor.addHeader("Content-Type", "application/json");
    httpSensor.addHeader("X-API-Key", API_KEY);
    httpSensor.addHeader("User-Agent", "ESP8266_Sensor");
    httpSensor.setTimeout(7000); 

    String body = "{\"valor\":" + String(valor, 1) + "}";
    
    int codigo = httpSensor.POST(body);

    if (codigo >= 200 && codigo < 300) {
      Serial.printf("[HTTP] sensor_id:%d Valor:%.1f -> OK (%d)\n", sensorId, valor, codigo);
    } else {
      Serial.printf("[HTTP] Error: %d\n", codigo);
      clienteSensor.stop();
      delay(500);
    }
    
    // Cerramos el flujo HTTP pero el objeto global mantiene la reserva de RAM
    httpSensor.end();
  }
}


// ─── setup ───────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(1000);

  portalSetup(
    sensores,   sizeof(sensores)   / sizeof(sensores[0]),
    actuadores, 0
  );

  if (!configurado) return;

  dht.begin();
  Serial.println("[DHT11] Iniciado.");
  Serial.printf("[Hub] sensor temperatura id: %d\n", cfg.sensorIds[0]);
  Serial.printf("[Hub] sensor humedad     id: %d\n", cfg.sensorIds[1]);
}

// ─── loop ────────────────────────────────────────────────────────────────────
void loop() {
  portalLoop();
  if (!configurado) return;

  if (millis() - ultimaLectura >= INTERVALO_MS) {
    ultimaLectura = millis();

    float temp = dht.readTemperature();
    float hum  = dht.readHumidity();

    if (isnan(temp) || isnan(hum)) {
      Serial.println("[DHT11] Error de lectura.");
      return;
    }

    Serial.printf("[DHT11] Temp: %.1f°C  Hum: %.1f%%\n", temp, hum);

    enviarLectura(cfg.sensorIds[0], temp);  // temperatura
    enviarLectura(cfg.sensorIds[1], hum);   // humedad
  }
}