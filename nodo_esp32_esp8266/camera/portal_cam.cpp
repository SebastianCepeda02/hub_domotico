/*
 * portal_cam.cpp
 * Módulo de vinculación WiFi para ESP32-CAM.
 * Portal cautivo + NVS + registro al hub.
 *
 * Librerías requeridas:
 *   - WiFi             (incluida en ESP32 board package)
 *   - WebServer        (incluida en ESP32 board package)
 *   - DNSServer        (incluida en ESP32 board package)
 *   - HTTPClient       (incluida en ESP32 board package)
 *   - WiFiClientSecure (incluida en ESP32 board package)
 *   - ArduinoJson      (Benoit Blanchon, versión 7.x)
 *   - Preferences      (incluida en ESP32 board package)
 */

#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <Preferences.h>

#include "portal_cam.h"

// ─── Pines ───────────────────────────────────────────────────────────────────
#define LED_PIN    33   // LED integrado ESP32-CAM (activo en LOW)

// ─── Configuración del AP ────────────────────────────────────────────────────
static const char*    AP_SSID_PREFIX = "HubDomotico-CAM";
static const byte     DNS_PORT       = 53;
static const int      WEB_PORT       = 80;

// ─── Variables globales ───────────────────────────────────────────────────────
ConfigCam cfg;
bool      configurado = false;

// ─── Variables privadas ───────────────────────────────────────────────────────
static WebServer   server(WEB_PORT);
static DNSServer   dnsServer;
static Preferences prefs;

// Cache del escaneo WiFi
static String        _redesJson  = "[]";
static unsigned long _tScan      = 0;
static bool          _scanListo  = false;


// ─── NVS helpers ─────────────────────────────────────────────────────────────

static void guardarConfig() {
  prefs.begin("cam", false);
  prefs.putString("ssid",          cfg.ssid);
  prefs.putString("password",      cfg.password);
  prefs.putInt("dispositivo_id",   cfg.dispositivoId);
  prefs.putInt("actuador_id",      cfg.actuadorId);
  prefs.end();
  Serial.println("[NVS] Configuración guardada.");
}

static bool cargarConfig() {
  prefs.begin("cam", true);
  String ssid = prefs.getString("ssid", "");
  if (ssid == "") {
    prefs.end();
    return false;
  }
  ssid.toCharArray(cfg.ssid,               sizeof(cfg.ssid));
  prefs.getString("password", "").toCharArray(cfg.password, sizeof(cfg.password));
  cfg.dispositivoId = prefs.getInt("dispositivo_id", 0);
  cfg.actuadorId    = prefs.getInt("actuador_id",    0);
  prefs.end();
  return true;
}

static void borrarConfig() {
  prefs.begin("cam", false);
  prefs.clear();
  prefs.end();
  Serial.println("[NVS] Config borrada. Reiniciando...");
  delay(500);
  ESP.restart();
}


// ─── Escaneo WiFi ─────────────────────────────────────────────────────────────

static void ejecutarScan() {
  _scanListo = false;
  int n      = WiFi.scanNetworks();
  String json = "[";
  for (int i = 0; i < n; i++) {
    if (i > 0) json += ",";
    json += "{\"ssid\":\""  + WiFi.SSID(i) + "\","
            "\"rssi\":"     + String(WiFi.RSSI(i)) + ","
            "\"secure\":"   + String(WiFi.encryptionType(i) != WIFI_AUTH_OPEN ? "true" : "false") + "}";
  }
  json      += "]";
  _redesJson  = json;
  _tScan      = millis();
  _scanListo  = true;
  Serial.printf("[Scan] %d redes encontradas.\n", n);
}


// ─── HTML del portal ──────────────────────────────────────────────────────────

static String construirHTML(String mensaje = "") {
  String msgHtml = "";
  if (mensaje != "") {
    bool esError = mensaje.startsWith("Error") || mensaje.startsWith("No se");
    msgHtml = "<div class=\"msg " + String(esError ? "error" : "ok") + "\">" + mensaje + "</div>";
  }

  return R"rawhtml(
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hub Domótico — Vincular cámara</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:sans-serif;background:#f0f4f8;display:flex;
         justify-content:center;align-items:center;min-height:100vh;padding:16px}
    .card{background:#fff;border-radius:12px;padding:28px 24px;
          max-width:420px;width:100%;box-shadow:0 2px 16px rgba(0,0,0,.1)}
    h1{font-size:1.2rem;font-weight:600;color:#1a202c;margin-bottom:4px}
    p.sub{font-size:.85rem;color:#718096;margin-bottom:20px}
    label{display:block;font-size:.82rem;font-weight:500;
          color:#4a5568;margin-bottom:4px;margin-top:14px}
    select,input[type=text],input[type=password]{
      width:100%;padding:9px 12px;border:1px solid #cbd5e0;
      border-radius:8px;font-size:.9rem;color:#2d3748}
    .scan-row{display:flex;gap:8px;align-items:flex-end}
    .scan-row select{flex:1}
    .scan-btn{padding:9px 12px;border:1px solid #cbd5e0;border-radius:8px;
              font-size:.85rem;cursor:pointer;background:#f7fafc;
              color:#4a5568;white-space:nowrap}
    .scan-btn:active{background:#e2e8f0}
    input[type=submit]{margin-top:22px;width:100%;padding:11px;
      background:#667eea;color:#fff;border:none;border-radius:8px;
      font-size:1rem;font-weight:600;cursor:pointer}
    .msg{margin-top:14px;padding:10px 14px;border-radius:8px;
         font-size:.85rem;font-weight:500}
    .msg.error{background:#fed7d7;color:#c53030}
    .msg.ok{background:#c6f6d5;color:#276749}
    .codigo-hint{font-size:.78rem;color:#718096;margin-top:4px}
  </style>
</head>
<body>
<div class="card">
  <h1>📷 Hub Domótico — Cámara</h1>
  <p class="sub">Vincula esta cámara a tu red</p>
  )rawhtml" + msgHtml + R"rawhtml(
  <form method="POST" action="/guardar">
    <label>Red WiFi</label>
    <div class="scan-row">
      <select name="ssid" id="ssid" required>
        <option value="" disabled selected>Buscando redes…</option>
      </select>
      <button type="button" class="scan-btn" onclick="escanear()">🔄 Buscar</button>
    </div>

    <label>Contraseña WiFi</label>
    <input type="password" name="password" autocomplete="off">

    <label>Código de vinculación</label>
    <input type="text" name="codigo" maxlength="6" placeholder="123456" required>
    <p class="codigo-hint">Encuéntralo en el panel web del hub → Dispositivos → Vincular</p>

    <input type="submit" value="Vincular cámara">
  </form>
</div>

<script>
function escanear() {
  const sel = document.getElementById('ssid');
  sel.innerHTML = '<option disabled selected>Escaneando…</option>';
  fetch('/scan')
    .then(r => r.json())
    .then(redes => {
      sel.innerHTML = '<option value="" disabled selected>Selecciona tu red…</option>';
      redes.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.ssid;
        opt.textContent = r.ssid + ' (' + r.rssi + ' dBm)' + (r.secure ? ' 🔒' : '');
        sel.appendChild(opt);
      });
    })
    .catch(() => {
      sel.innerHTML = '<option disabled selected>Error al escanear</option>';
    });
}
window.onload = escanear;
</script>
</body></html>
  )rawhtml";
}


// ─── Registro en el hub ───────────────────────────────────────────────────────

static bool registrarEnHub(const String& codigo) {
  String url = String(HUB_URL) + "/vincular/registrar";
  Serial.printf("[Hub] POST %s\n", url.c_str());

  WiFiClientSecure cliente;
  cliente.setInsecure();
  cliente.setTimeout(15000);
  HTTPClient http;
  http.begin(cliente, url);
  http.setTimeout(15000);
  http.addHeader("Content-Type", "application/json");

  JsonDocument doc;
  doc["mac"]    = WiFi.macAddress();
  doc["codigo"] = codigo;

  JsonArray sensoresArr   = doc["sensores"].to<JsonArray>();
  JsonArray actuadoresArr = doc["actuadores"].to<JsonArray>();
  JsonObject cam          = actuadoresArr.add<JsonObject>();
  cam["tipo"]             = "camera";
  cam["pin"]              = 0;

  String body;
  serializeJson(doc, body);
  Serial.printf("[Hub] Body: %s\n", body.c_str());

  int    codigo_http = http.POST(body);
  String resp        = http.getString();
  Serial.printf("[Hub] HTTP: %d  Resp: %s\n", codigo_http, resp.c_str());
  http.end();

  if (codigo_http == 200 || codigo_http == 201) {
    JsonDocument respDoc;
    if (!deserializeJson(respDoc, resp)) {
      cfg.dispositivoId = respDoc["dispositivo_id"].as<int>();
      cfg.actuadorId    = respDoc["actuadores"][0]["id"].as<int>();
      guardarConfig();
      Serial.printf("[Hub] Registrado. dispositivo_id=%d actuador_id=%d\n",
                    cfg.dispositivoId, cfg.actuadorId);
      return true;
    }
  }
  return false;
}


// ─── Actualizar stream_url en el hub ─────────────────────────────────────────

static void actualizarStreamUrl() {
  WiFiClientSecure cliente;
  cliente.setInsecure();
  cliente.setTimeout(10000);
  HTTPClient http;

  String streamUrl = "http://" + WiFi.localIP().toString() + ":" + String(CAM_PORT) + "/stream";
  String url       = String(HUB_URL) + "/actuadores/" + String(cfg.actuadorId);

  http.begin(cliente, url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key",    API_KEY);
  http.setTimeout(10000);

  JsonDocument doc;
  doc["stream_url"] = streamUrl;
  String body;
  serializeJson(doc, body);
  http.sendRequest("PATCH", body);
  http.end();

  Serial.printf("[Hub] stream_url actualizada: %s\n", streamUrl.c_str());
}


// ─── Modo AP + portal cautivo ─────────────────────────────────────────────────

static void iniciarModoPortal() {
  uint8_t mac[6];
  WiFi.macAddress(mac);
  char apSSID[32];
  snprintf(apSSID, sizeof(apSSID), "%s-%02X%02X", AP_SSID_PREFIX, mac[4], mac[5]);

  WiFi.mode(WIFI_AP);
  WiFi.softAP(apSSID);
  Serial.printf("[AP] Red: %s  IP: %s\n", apSSID, WiFi.softAPIP().toString().c_str());

  // Escanear redes — en ESP32 es síncrono así que lo hacemos antes de levantar el server
  ejecutarScan();

  dnsServer.start(DNS_PORT, "*", WiFi.softAPIP());

  server.on("/", HTTP_GET, []() {
    server.send(200, "text/html", construirHTML());
  });

  server.on("/scan", HTTP_GET, []() {
    if (millis() - _tScan > 30000) ejecutarScan();
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", _redesJson);
  });

  server.onNotFound([]() {
    server.sendHeader("Location", "http://192.168.4.1/", true);
    server.send(302, "text/plain", "");
  });

  server.on("/guardar", HTTP_POST, []() {
    String ssid     = server.arg("ssid");
    String password = server.arg("password");
    String codigo   = server.arg("codigo");

    if (ssid == "" || codigo == "") {
      server.send(200, "text/html", construirHTML("Error: completa todos los campos obligatorios."));
      return;
    }

    Serial.printf("[Portal] Probando conexión a: %s\n", ssid.c_str());
    WiFi.mode(WIFI_AP_STA);
    WiFi.begin(ssid.c_str(), password.c_str());

    int intentos = 0;
    while (WiFi.status() != WL_CONNECTED && intentos < 20) {
      delay(500);
      intentos++;
    }

    if (WiFi.status() != WL_CONNECTED) {
      WiFi.mode(WIFI_AP);
      server.send(200, "text/html", construirHTML("Error: no se pudo conectar. Verifica SSID y contraseña."));
      return;
    }

    ssid.toCharArray(cfg.ssid,         sizeof(cfg.ssid));
    password.toCharArray(cfg.password, sizeof(cfg.password));
    cfg.dispositivoId = 0;
    cfg.actuadorId    = 0;

    server.send(200, "text/html", construirHTML("✅ WiFi conectado. Registrando en el hub…"));
    delay(500);

    if (registrarEnHub(codigo)) {
      Serial.println("[Portal] Registro exitoso. Reiniciando...");
      delay(1500);
      ESP.restart();
    } else {
      guardarConfig();
      Serial.println("[Portal] Registro fallido. Guardando WiFi y reiniciando...");
      delay(1500);
      ESP.restart();
    }
  });

  server.begin();
  Serial.println("[Portal] Esperando configuración...");
}


// ─── Conectar WiFi ────────────────────────────────────────────────────────────

static void conectarWiFi() {
  Serial.printf("[WiFi] Conectando a: %s\n", cfg.ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(cfg.ssid, cfg.password);
  int intentos = 0;
  while (WiFi.status() != WL_CONNECTED && intentos < 40) {
    delay(500);
    Serial.print(".");
    intentos++;
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[WiFi] Conectado. IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("[WiFi] Fallo. Volviendo al portal...");
    borrarConfig();
  }
}


// ─── API pública ──────────────────────────────────────────────────────────────

void portalSetup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);

  // Botón de reset — GPIO0 en ESP32-CAM
  pinMode(0, INPUT_PULLUP);
  if (digitalRead(0) == LOW) {
    Serial.println("[Reset] Botón detectado. Mantenlo 3 s para borrar config...");
    delay(3000);
    if (digitalRead(0) == LOW) borrarConfig();
  }

  if (cargarConfig()) {
    Serial.println("[NVS] Config encontrada.");
    Serial.printf("  SSID:           %s\n", cfg.ssid);
    Serial.printf("  dispositivo_id: %d\n", cfg.dispositivoId);
    Serial.printf("  actuador_id:    %d\n", cfg.actuadorId);

    conectarWiFi();
    if (cfg.dispositivoId == 0) {
      Serial.println("[Hub] Sin dispositivo_id. Reinicia y usa el portal.");
    }
    configurado = true;
    actualizarStreamUrl();
  } else {
    Serial.println("[NVS] Sin config. Iniciando portal...");
    iniciarModoPortal();
  }
}

void portalLoop() {
  if (configurado) {
    digitalWrite(LED_PIN, LOW);
    return;
  }
  dnsServer.processNextRequest();
  server.handleClient();

  static unsigned long tLed = 0;
  static bool ledOn = false;
  if (millis() - tLed > 800) {
    tLed  = millis();
    ledOn = !ledOn;
    digitalWrite(LED_PIN, ledOn ? LOW : HIGH);
  }
}