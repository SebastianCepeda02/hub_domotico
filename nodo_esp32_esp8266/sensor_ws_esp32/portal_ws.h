#pragma once

/*
 * portal_ws.h — ESP32
 * Vinculación WiFi + registro en el hub para dispositivos WebSocket.
 *
 * Librerías requeridas:
 *   - WiFi, WebServer, DNSServer  (ESP32 board package)
 *   - HTTPClient, WiFiClientSecure (ESP32 board package)
 *   - ArduinoJson (Benoit Blanchon, v7.x)
 *   - Preferences (ESP32 board package)
 */

#include <Arduino.h>

#define HUB_URL  "https://api.domotic-dev.online"
#define WS_HOST  "api.domotic-dev.online"
#define WS_PORT  443

#define MAX_SENSORES   4
#define MAX_ACTUADORES 4

struct SensorInfo {
  char tipo[20];
  char unidad[10];
};

struct ActuadorInfo {
  char tipo[20];
  int  pin;
};

struct Config {
  char ssid[65];
  char password[65];
  int  dispositivoId;
  int  sensorIds[MAX_SENSORES];
  int  actuadorIds[MAX_ACTUADORES];
};

extern Config cfg;
extern bool   configurado;

void portalSetup(SensorInfo* sensores,   int numSensores,
                 ActuadorInfo* actuadores, int numActuadores);
void portalLoop();
