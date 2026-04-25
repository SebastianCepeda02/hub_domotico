/*
 * portal_ws.ino — ESP32
 * Portal cautivo WiFi + registro al hub (protocolo "ws").
 * No modificar para cada dispositivo nuevo; edita solo el .ino principal.
 */

#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <Preferences.h>

#include "portal_ws.h"

#define RESET_PIN  0
#define LED_PIN    2
static const byte DNS_PORT = 53;

Config cfg;
bool   configurado = false;

static WebServer  server(80);
static DNSServer  dnsServer;
static Preferences prefs;

static SensorInfo*   _sensores      = nullptr;
static int           _numSensores   = 0;
static ActuadorInfo* _actuadores    = nullptr;
static int           _numActuadores = 0;

static String  _redesJson   = "[]";
static unsigned long _tScan = 0;


// ─── NVS helpers ─────────────────────────────────────────────────────────────

static void guardarConfig() {
  prefs.begin("hub", false);
  prefs.putString("ssid",   cfg.ssid);
  prefs.putString("pass",   cfg.password);
  prefs.putInt   ("devId",  cfg.dispositivoId);
  for (int i = 0; i < MAX_SENSORES;   i++) prefs.putInt(("sid" + String(i)).c_str(), cfg.sensorIds[i]);
  for (int i = 0; i < MAX_ACTUADORES; i++) prefs.putInt(("aid" + String(i)).c_str(), cfg.actuadorIds[i]);
  prefs.end();
  Serial.println("[NVS] Config guardada.");
}

static bool cargarConfig() {
  prefs.begin("hub", true);
  bool existe = prefs.isKey("ssid");
  if (existe) {
    prefs.getString("ssid", cfg.ssid,     sizeof(cfg.ssid));
    prefs.getString("pass", cfg.password, sizeof(cfg.password));
    cfg.dispositivoId = prefs.getInt("devId", 0);
    for (int i = 0; i < MAX_SENSORES;   i++) cfg.sensorIds[i]   = prefs.getInt(("sid" + String(i)).c_str(), 0);
    for (int i = 0; i < MAX_ACTUADORES; i++) cfg.actuadorIds[i] = prefs.getInt(("aid" + String(i)).c_str(), 0);
  }
  prefs.end();
  return existe;
}

static void borrarConfig() {
  prefs.begin("hub", false);
  prefs.clear();
  prefs.end();
  Serial.println("[NVS] Config borrada. Reiniciando...");
  delay(500);
  ESP.restart();
}


// ─── Escaneo WiFi ─────────────────────────────────────────────────────────────

static void escanearRedes() {
  int n = WiFi.scanNetworks();
  String json = "[";
  for (int i = 0; i < n; i++) {
    if (i > 0) json += ",";
    json += "{\"ssid\":\"" + WiFi.SSID(i) + "\","
            "\"rssi\":"    + String(WiFi.RSSI(i)) + ","
            "\"secure\":"  + String(WiFi.encryptionType(i) != WIFI_AUTH_OPEN ? "true" : "false") + "}";
  }
  json += "]";
  _redesJson = json;
  _tScan = millis();
}


// ─── HTML portal ─────────────────────────────────────────────────────────────

static String construirHTML(String mensaje = "") {
  String msgHtml = "";
  if (mensaje != "") {
    bool esError = mensaje.startsWith("Error") || mensaje.startsWith("No se");
    msgHtml = "<div class=\"msg " + String(esError ? "error" : "ok") + "\">" + mensaje + "</div>";
  }
  return R"rawhtml(
<!DOCTYPE html><html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hub Domótico — Vincular</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:sans-serif;background:#f0f4f8;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:16px}
.card{background:#fff;border-radius:12px;padding:28px 24px;max-width:420px;width:100%;box-shadow:0 2px 16px rgba(0,0,0,.1)}
h1{font-size:1.2rem;font-weight:600;color:#1a202c;margin-bottom:4px}
p.sub{font-size:.85rem;color:#718096;margin-bottom:20px}
label{display:block;font-size:.82rem;font-weight:500;color:#4a5568;margin-bottom:4px;margin-top:14px}
select,input[type=text],input[type=password]{width:100%;padding:9px 12px;border:1px solid #cbd5e0;border-radius:8px;font-size:.9rem;color:#2d3748}
.scan-row{display:flex;gap:8px;align-items:flex-end}
.scan-row select{flex:1}
.scan-btn{padding:9px 12px;border:1px solid #cbd5e0;border-radius:8px;font-size:.85rem;cursor:pointer;background:#f7fafc;color:#4a5568;white-space:nowrap}
input[type=submit]{margin-top:22px;width:100%;padding:11px;background:#667eea;color:#fff;border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer}
.msg{margin-top:14px;padding:10px 14px;border-radius:8px;font-size:.85rem;font-weight:500}
.msg.error{background:#fed7d7;color:#c53030}
.msg.ok{background:#c6f6d5;color:#276749}
.codigo-hint{font-size:.78rem;color:#718096;margin-top:4px}
</style></head><body>
<div class="card">
<h1>🏠 Hub Domótico</h1>
<p class="sub">Vincula este dispositivo ESP32 a tu red</p>
)rawhtml" + msgHtml + R"rawhtml(
<form method="POST" action="/guardar">
<label>Red WiFi</label>
<div class="scan-row">
<select name="ssid" id="ssid" required><option value="" disabled selected>Buscando redes…</option></select>
<button type="button" class="scan-btn" onclick="escanear()">🔄 Buscar</button>
</div>
<label>Contraseña WiFi</label>
<input type="password" name="password" autocomplete="off">
<label>Código de vinculación</label>
<input type="text" name="codigo" maxlength="6" placeholder="123456" required>
<p class="codigo-hint">Encuéntralo en el panel web → Dispositivos → Vincular</p>
<input type="submit" value="Vincular dispositivo">
</form></div>
<script>
function escanear(){
  const sel=document.getElementById('ssid');
  sel.innerHTML='<option disabled selected>Escaneando…</option>';
  fetch('/scan').then(r=>r.json()).then(redes=>{
    sel.innerHTML='<option value="" disabled selected>Selecciona tu red…</option>';
    redes.forEach(r=>{
      const o=document.createElement('option');
      o.value=r.ssid;
      o.textContent=r.ssid+' ('+r.rssi+' dBm)'+(r.secure?' 🔒':'');
      sel.appendChild(o);
    });
  }).catch(()=>{sel.innerHTML='<option disabled selected>Error al escanear</option>';});
}
window.onload=escanear;
</script></body></html>)rawhtml";
}


// ─── Registro en el hub ───────────────────────────────────────────────────────

static bool registrarEnHub(const String& codigo) {
  String url = String(HUB_URL) + "/vincular/registrar";
  WiFiClientSecure cliente;
  cliente.setInsecure();
  HTTPClient http;
  http.begin(cliente, url);
  http.setTimeout(10000);
  http.addHeader("Content-Type", "application/json");

  JsonDocument doc;
  doc["mac"]       = WiFi.macAddress();
  doc["codigo"]    = codigo;
  doc["protocolo"] = "ws";

  JsonArray sArr = doc["sensores"].to<JsonArray>();
  for (int i = 0; i < _numSensores; i++) {
    JsonObject s = sArr.add<JsonObject>();
    s["tipo"]   = _sensores[i].tipo;
    s["unidad"] = _sensores[i].unidad;
  }
  JsonArray aArr = doc["actuadores"].to<JsonArray>();
  for (int i = 0; i < _numActuadores; i++) {
    JsonObject a = aArr.add<JsonObject>();
    a["tipo"] = _actuadores[i].tipo;
    a["pin"]  = _actuadores[i].pin;
  }

  String body;
  serializeJson(doc, body);
  Serial.printf("[Hub] POST %s\nBody: %s\n", url.c_str(), body.c_str());

  int codigo_http = http.POST(body);
  if (codigo_http == 200 || codigo_http == 201) {
    String resp = http.getString();
    Serial.printf("[Hub] Respuesta: %s\n", resp.c_str());
    JsonDocument respDoc;
    if (!deserializeJson(respDoc, resp)) {
      cfg.dispositivoId = respDoc["dispositivo_id"].as<int>();
      JsonArray sIds = respDoc["sensores"].as<JsonArray>();
      int i = 0;
      for (JsonObject s : sIds) if (i < MAX_SENSORES)   cfg.sensorIds[i++]   = s["id"].as<int>();
      JsonArray aIds = respDoc["actuadores"].as<JsonArray>();
      i = 0;
      for (JsonObject a : aIds) if (i < MAX_ACTUADORES) cfg.actuadorIds[i++] = a["id"].as<int>();
      guardarConfig();
      http.end();
      return true;
    }
  }
  Serial.printf("[Hub] Error al registrar. HTTP: %d\n", codigo_http);
  http.end();
  return false;
}


// ─── Modo AP + portal cautivo ─────────────────────────────────────────────────

static void iniciarModoPortal() {
  uint8_t mac[6];
  WiFi.softAPmacAddress(mac);
  char apSSID[32];
  snprintf(apSSID, sizeof(apSSID), "HubDomotico-%02X%02X", mac[4], mac[5]);

  WiFi.mode(WIFI_AP);
  WiFi.softAP(apSSID);
  Serial.printf("[AP] Red: %s  IP: %s\n", apSSID, WiFi.softAPIP().toString().c_str());

  escanearRedes();
  dnsServer.start(DNS_PORT, "*", WiFi.softAPIP());

  server.on("/", HTTP_GET, []() { server.send(200, "text/html", construirHTML()); });

  server.on("/scan", HTTP_GET, []() {
    if (millis() - _tScan > 30000) escanearRedes();
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", _redesJson);
  });

  server.onNotFound([]() {
    server.sendHeader("Location", "http://192.168.4.1/", true);
    server.send(302, "text/plain", "");
  });

  server.on("/guardar", HTTP_POST, []() {
    String ssid    = server.arg("ssid");
    String pass    = server.arg("password");
    String codigo  = server.arg("codigo");

    if (ssid == "" || codigo == "") {
      server.send(200, "text/html", construirHTML("Error: completa todos los campos."));
      return;
    }

    WiFi.mode(WIFI_AP_STA);
    WiFi.begin(ssid.c_str(), pass.c_str());
    int intentos = 0;
    while (WiFi.status() != WL_CONNECTED && intentos < 20) { delay(500); intentos++; }

    if (WiFi.status() != WL_CONNECTED) {
      WiFi.mode(WIFI_AP);
      server.send(200, "text/html", construirHTML("Error: no se pudo conectar. Verifica SSID y contraseña."));
      return;
    }

    ssid.toCharArray(cfg.ssid,      sizeof(cfg.ssid));
    pass.toCharArray(cfg.password,  sizeof(cfg.password));
    cfg.dispositivoId = 0;
    memset(cfg.sensorIds,   0, sizeof(cfg.sensorIds));
    memset(cfg.actuadorIds, 0, sizeof(cfg.actuadorIds));

    server.send(200, "text/html", construirHTML("✅ WiFi conectado. Registrando en el hub…"));
    delay(500);

    if (registrarEnHub(codigo)) {
      Serial.println("[Portal] Registro exitoso. Reiniciando...");
    } else {
      guardarConfig();
      Serial.println("[Portal] Registro fallido. Guardando WiFi y reiniciando...");
    }
    delay(1500);
    ESP.restart();
  });

  server.begin();
  Serial.println("[Portal] Esperando configuración...");
}


// ─── API pública ──────────────────────────────────────────────────────────────

void portalSetup(SensorInfo* sensores,   int numSensores,
                 ActuadorInfo* actuadores, int numActuadores) {
  _sensores      = sensores;
  _numSensores   = numSensores;
  _actuadores    = actuadores;
  _numActuadores = numActuadores;

  pinMode(LED_PIN,   OUTPUT);
  pinMode(RESET_PIN, INPUT_PULLUP);
  digitalWrite(LED_PIN, HIGH);

  if (digitalRead(RESET_PIN) == LOW) {
    Serial.println("[Reset] Botón detectado. Mantenlo 3 s para borrar config...");
    delay(3000);
    if (digitalRead(RESET_PIN) == LOW) borrarConfig();
  }

  if (cargarConfig()) {
    Serial.printf("[NVS] Config encontrada. SSID: %s  dispositivo_id: %d\n",
                  cfg.ssid, cfg.dispositivoId);
    WiFi.mode(WIFI_STA);
    WiFi.begin(cfg.ssid, cfg.password);
    int intentos = 0;
    while (WiFi.status() != WL_CONNECTED && intentos < 40) { delay(500); Serial.print("."); intentos++; }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) {
      Serial.printf("[WiFi] Conectado. IP: %s\n", WiFi.localIP().toString().c_str());
      configurado = true;
    } else {
      Serial.println("[WiFi] Fallo. Volviendo al portal...");
      borrarConfig();
    }
  } else {
    Serial.println("[NVS] Sin config. Iniciando portal...");
    iniciarModoPortal();
  }
}

void portalLoop() {
  if (configurado) { digitalWrite(LED_PIN, LOW); return; }
  dnsServer.processNextRequest();
  server.handleClient();
  static unsigned long tLed = 0;
  static bool ledOn = false;
  if (millis() - tLed > 800) { tLed = millis(); ledOn = !ledOn; digitalWrite(LED_PIN, ledOn ? LOW : HIGH); }
}
