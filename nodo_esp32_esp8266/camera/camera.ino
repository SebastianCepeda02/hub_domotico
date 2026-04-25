/*
 * MiDispositivo.ino — ESP32-CAM
 *
 * Stream MJPEG + portal cautivo + heartbeat al hub.
 * portal_cam.cpp se encarga de WiFi, NVS y registro.
 */

#include "portal_cam.h"
#include <WebServer.h>
#include <WiFi.h>                
#include <WiFiClient.h>
#include <esp_camera.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

// ─── Pines cámara (AI Thinker ESP32-CAM) ─────────────────────────────────────
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ─── Constantes ───────────────────────────────────────────────────────────────
#define HEARTBEAT_MS  60000   // heartbeat cada 60 segundos

// ─── Variables globales ───────────────────────────────────────────────────────
WebServer        camServer(CAM_PORT);
unsigned long    ultimoHeartbeat = 0;


// ─── Cámara ───────────────────────────────────────────────────────────────────

bool iniciarCamara() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
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
  config.jpeg_quality = 12;
  config.fb_count     = 2;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("[CAM] Error al iniciar.");
    return false;
  }
  Serial.println("[CAM] Iniciada.");
  return true;
}


// ─── Stream MJPEG ────────────────────────────────────────────────────────────

void handleStream() {
  WiFiClient cliente = camServer.client();
  cliente.println("HTTP/1.1 200 OK");
  cliente.println("Content-Type: multipart/x-mixed-replace; boundary=frame");
  cliente.println("Access-Control-Allow-Origin: *");
  cliente.println();

  while (cliente.connected()) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) { Serial.println("[CAM] Error frame."); break; }
    cliente.println("--frame");
    cliente.println("Content-Type: image/jpeg");
    cliente.printf("Content-Length: %u\r\n\r\n", fb->len);
    cliente.write(fb->buf, fb->len);
    cliente.println();
    esp_camera_fb_return(fb);
    delay(50);
  }
}

void handleSnapshot() {
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) { camServer.send(500, "text/plain", "Error"); return; }
  camServer.sendHeader("Access-Control-Allow-Origin", "*");
  camServer.send_P(200, "image/jpeg", (const char*)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}


// ─── Heartbeat ───────────────────────────────────────────────────────────────

void enviarHeartbeat() {
  WiFiClientSecure cliente;
  cliente.setInsecure();
  cliente.setTimeout(10000);
  HTTPClient http;

  String url = String(HUB_URL) + "/actuadores/" + String(cfg.actuadorId);
  http.begin(cliente, url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key",    API_KEY);
  http.setTimeout(10000);
  http.GET();
  http.end();
  Serial.println("[CAM] Heartbeat enviado.");
}


// ─── setup ───────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1000);

  portalSetup();  // WiFi + NVS + registro + stream_url

  if (!configurado) return;

  if (!iniciarCamara()) {
    Serial.println("[ERROR] Cámara no iniciada. Reinicia.");
    while(true) delay(1000);
  }

  camServer.on("/stream",   handleStream);
  camServer.on("/snapshot", handleSnapshot);
  camServer.begin();

  Serial.printf("[CAM] Stream en:   http://%s:%d/stream\n",
                WiFi.localIP().toString().c_str(), CAM_PORT);
  Serial.printf("[CAM] Snapshot en: http://%s:%d/snapshot\n",
                WiFi.localIP().toString().c_str(), CAM_PORT);
}


// ─── loop ────────────────────────────────────────────────────────────────────

void loop() {
  portalLoop();
  if (!configurado) return;

  camServer.handleClient();

  if (millis() - ultimoHeartbeat >= HEARTBEAT_MS) {
    ultimoHeartbeat = millis();
    enviarHeartbeat();
  }
}