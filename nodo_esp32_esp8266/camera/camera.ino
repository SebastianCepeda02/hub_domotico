/*
 * camera.ino — ESP32-CAM vía WebSocket
 *
 * Captura frames JPEG y los envía al hub por WSS como mensajes binarios.
 * El hub los reenvía a los navegadores conectados en tiempo real.
 * Vinculación inicial por portal cautivo (mismo flujo que otros dispositivos).
 *
 * Librerías requeridas (Library Manager):
 *   - WebSockets by Markus Sattler
 *   - ArduinoJson (Benoit Blanchon)
 * Board: AI Thinker ESP32-CAM
 */

#include "portal_cam.h"
#include <WebSocketsClient.h>
#include <WiFiClientSecure.h>
#include <esp_camera.h>

// ─── Pines cámara (AI Thinker ESP32-CAM) ─────────────────────────────────────
#define PWDN_GPIO_NUM   32
#define RESET_GPIO_NUM  -1
#define XCLK_GPIO_NUM    0
#define SIOD_GPIO_NUM   26
#define SIOC_GPIO_NUM   27
#define Y9_GPIO_NUM     35
#define Y8_GPIO_NUM     34
#define Y7_GPIO_NUM     39
#define Y6_GPIO_NUM     36
#define Y5_GPIO_NUM     21
#define Y4_GPIO_NUM     19
#define Y3_GPIO_NUM     18
#define Y2_GPIO_NUM      5
#define VSYNC_GPIO_NUM  25
#define HREF_GPIO_NUM   23
#define PCLK_GPIO_NUM   22

#define FRAME_INTERVAL_MS  100   // ~10 fps
#define HEARTBEAT_MS       30000

WebSocketsClient wsClient;
unsigned long ultimoFrame     = 0;
unsigned long ultimoHeartbeat = 0;
bool wsConectado = false;


// ─── Cámara ───────────────────────────────────────────────────────────────────

bool iniciarCamara() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_VGA;
  config.jpeg_quality = 15;
  config.fb_count     = 2;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("[CAM] Error al iniciar.");
    return false;
  }
  Serial.println("[CAM] Iniciada.");
  return true;
}


// ─── WebSocket ────────────────────────────────────────────────────────────────

void onWsEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      wsConectado = false;
      Serial.println("[WS] Desconectado. Reconectando...");
      break;
    case WStype_CONNECTED:
      wsConectado = true;
      Serial.println("[WS] Conectado al hub. Iniciando stream...");
      break;
    default:
      break;
  }
}

void enviarFrame() {
  if (!wsConectado) return;

  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) { Serial.println("[CAM] Error capturando frame."); return; }

  wsClient.sendBIN(fb->buf, fb->len);
  esp_camera_fb_return(fb);
}


// ─── setup / loop ─────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1000);

  portalSetup();
  if (!configurado) return;

  if (!iniciarCamara()) {
    Serial.println("[ERROR] Cámara no iniciada.");
    while (true) delay(1000);
  }

  String path = "/ws/camera/" + String(cfg.dispositivoId) + "/publish?api_key=" + String(API_KEY);
  wsClient.beginSSL(WS_HOST, WS_PORT, path);
  wsClient.onEvent(onWsEvent);
  wsClient.setReconnectInterval(5000);

  Serial.printf("[WS] Conectando a wss://%s%s\n", WS_HOST, path.c_str());
}

void loop() {
  portalLoop();
  if (!configurado) return;

  wsClient.loop();

  if (wsConectado && millis() - ultimoFrame >= FRAME_INTERVAL_MS) {
    ultimoFrame = millis();
    enviarFrame();
  }
}
