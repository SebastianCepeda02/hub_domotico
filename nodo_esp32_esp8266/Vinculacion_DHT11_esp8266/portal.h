#pragma once

/*
 * portal.h
 * Declaraciones públicas del módulo de vinculación WiFi.
 * Incluir en el sketch principal con: #include "portal.h"
 */

#include <Arduino.h>

// ─── Configuración del hub ────────────────────────────────────────────────────
// Cambia esta URL si tu hub cambia de dirección
#define HUB_URL "https://api.domotic-dev.online"

// ─── Máximos de sensores y actuadores por dispositivo ────────────────────────
#define MAX_SENSORES   4
#define MAX_ACTUADORES 4

// ─── Estructura de un sensor a registrar ─────────────────────────────────────
struct SensorInfo {
  char tipo[20];    // "temperature" | "humidity" | "motion" | ...
  char unidad[10];  // "°C" | "%" | "" | ...
};

// ─── Estructura de un actuador a registrar ───────────────────────────────────
struct ActuadorInfo {
  char tipo[20];  // "relay" | "light" | "plug" | ...
  int  pin;
};

// ─── Configuración guardada en EEPROM ────────────────────────────────────────
struct Config {
  char ssid[65];
  char password[65];
  char ubicacion[36];
  int  dispositivoId;
  int  sensorIds[MAX_SENSORES];
  int  actuadorIds[MAX_ACTUADORES];
};

extern Config cfg;
extern bool   configurado;

/*
 * Llama a portalSetup() al inicio de setup().
 * Pasa los sensores y actuadores que tiene este dispositivo
 * para que el hub los registre y devuelva sus IDs.
 *
 * Ejemplo:
 *   SensorInfo sensores[] = { {"temperature","°C"}, {"humidity","%"} };
 *   ActuadorInfo actuadores[] = {};
 *   portalSetup(sensores, 2, actuadores, 0);
 */
void portalSetup(SensorInfo* sensores,   int numSensores,
                 ActuadorInfo* actuadores, int numActuadores);

/*
 * Llama a portalLoop() al inicio de loop().
 * Solo hace algo mientras el dispositivo está en modo portal.
 * En modo normal retorna inmediatamente.
 */
void portalLoop();