#pragma once

/*
 * portal_cam.h
 * Declaraciones públicas del módulo de vinculación WiFi para ESP32-CAM.
 * Incluir en el sketch principal con: #include "portal_cam.h"
 */

#include <Arduino.h>

// ─── Configuración del hub ────────────────────────────────────────────────────
#define HUB_URL   "https://api.domotic-dev.online"
#define API_KEY   "tu-clave-secreta-123"
#define CAM_PORT  81

// ─── Configuración guardada en NVS ───────────────────────────────────────────
struct ConfigCam {
  char ssid[65];
  char password[65];
  int  dispositivoId;
  int  actuadorId;
};

extern ConfigCam cfg;
extern bool      configurado;

/*
 * Llama a portalSetup() al inicio de setup().
 * Si no hay config guardada levanta el AP y el portal cautivo.
 * Si hay config guardada conecta al WiFi y actualiza stream_url.
 */
void portalSetup();

/*
 * Llama a portalLoop() al inicio de loop().
 * Solo hace algo mientras el dispositivo está en modo portal.
 * En modo normal retorna inmediatamente.
 */
void portalLoop();