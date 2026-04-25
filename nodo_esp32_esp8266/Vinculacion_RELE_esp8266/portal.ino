/*
 * portal.ino
 * Módulo de vinculación WiFi — portal cautivo + EEPROM + registro al hub.
 *
 * Este archivo no necesita modificarse para cada dispositivo nuevo.
 * Solo edita MiDispositivo.ino con tu lógica de negocio.
 *
 * Librerías requeridas:
 *   - ESP8266WiFi       (incluida en ESP8266 board package)
 *   - ESP8266WebServer  (incluida en ESP8266 board package)
 *   - DNSServer         (incluida en ESP8266 board package)
 *   - ESP8266HTTPClient (incluida en ESP8266 board package)
 *   - ArduinoJson       (Benoit Blanchon, versión 7.x)
 *   - EEPROM            (incluida en ESP8266 board package)
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <DNSServer.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>
#include <EEPROM.h>

#include "portal.h"

// ─── Pines ───────────────────────────────────────────────────────────────────
#define RESET_PIN  0   // GPIO0 (D3): mantener 3 s al arrancar para borrar config
#define LED_PIN    2   // LED integrado (activo en LOW)

// ─── Configuración del AP ────────────────────────────────────────────────────
static const char* AP_SSID_PREFIX = "HubDomotico";
static const byte  DNS_PORT       = 53;
static const int   WEB_PORT       = 80;

// ─── EEPROM layout ───────────────────────────────────────────────────────────
#define EEPROM_SIZE        512
#define EEPROM_FLAG_ADDR     0
#define EEPROM_SSID_ADDR     1
#define EEPROM_PASS_ADDR    66
#define EEPROM_UBIC_ADDR   131
#define EEPROM_DEVID_ADDR  167
#define EEPROM_SIDS_ADDR   171   // 4 ints × 4 bytes = 16 bytes
#define EEPROM_AIDS_ADDR   187   // 4 ints × 4 bytes = 16 bytes
#define VALID_FLAG        0xAB

// ─── Variables globales ───────────────────────────────────────────────────────
Config cfg;
bool   configurado = false;

// ─── Variables privadas ───────────────────────────────────────────────────────
static ESP8266WebServer server(WEB_PORT);
static DNSServer        dnsServer;

// Sensores y actuadores pasados desde MiDispositivo.ino
static SensorInfo*   _sensores      = nullptr;
static int           _numSensores   = 0;
static ActuadorInfo* _actuadores    = nullptr;
static int           _numActuadores = 0;

// Cache del escaneo WiFi
static String  _redesJson     = "[]";
static unsigned long _tScan   = 0;
static bool    _scanEnCurso   = false;


// ─── EEPROM helpers ───────────────────────────────────────────────────────────

static void eepromWriteString(int addr, const char* str, int maxLen) {
  for (int i = 0; i < maxLen; i++)
    EEPROM.write(addr + i, i < (int)strlen(str) ? str[i] : 0);
}

static void eepromReadString(int addr, char* buf, int maxLen) {
  for (int i = 0; i < maxLen; i++)
    buf[i] = EEPROM.read(addr + i);
  buf[maxLen - 1] = '\0';
}

static void eepromWriteInt(int addr, int val) {
  EEPROM.write(addr,     (val >> 24) & 0xFF);
  EEPROM.write(addr + 1, (val >> 16) & 0xFF);
  EEPROM.write(addr + 2, (val >>  8) & 0xFF);
  EEPROM.write(addr + 3,  val        & 0xFF);
}

static int eepromReadInt(int addr) {
  return ((int)EEPROM.read(addr)     << 24)
       | ((int)EEPROM.read(addr + 1) << 16)
       | ((int)EEPROM.read(addr + 2) <<  8)
       |  (int)EEPROM.read(addr + 3);
}

static void guardarConfig() {
  EEPROM.write(EEPROM_FLAG_ADDR, VALID_FLAG);
  eepromWriteString(EEPROM_SSID_ADDR, cfg.ssid,      64);
  eepromWriteString(EEPROM_PASS_ADDR, cfg.password,  64);
  eepromWriteString(EEPROM_UBIC_ADDR, cfg.ubicacion, 35);
  eepromWriteInt(EEPROM_DEVID_ADDR, cfg.dispositivoId);
  for (int i = 0; i < MAX_SENSORES; i++)
    eepromWriteInt(EEPROM_SIDS_ADDR + i * 4, cfg.sensorIds[i]);
  for (int i = 0; i < MAX_ACTUADORES; i++)
    eepromWriteInt(EEPROM_AIDS_ADDR + i * 4, cfg.actuadorIds[i]);
  EEPROM.commit();
  Serial.println("[EEPROM] Configuración guardada.");
}

static bool cargarConfig() {
  if (EEPROM.read(EEPROM_FLAG_ADDR) != VALID_FLAG) return false;
  eepromReadString(EEPROM_SSID_ADDR, cfg.ssid,      65);
  eepromReadString(EEPROM_PASS_ADDR, cfg.password,  65);
  eepromReadString(EEPROM_UBIC_ADDR, cfg.ubicacion, 36);
  cfg.dispositivoId = eepromReadInt(EEPROM_DEVID_ADDR);
  for (int i = 0; i < MAX_SENSORES; i++)
    cfg.sensorIds[i]   = eepromReadInt(EEPROM_SIDS_ADDR + i * 4);
  for (int i = 0; i < MAX_ACTUADORES; i++)
    cfg.actuadorIds[i] = eepromReadInt(EEPROM_AIDS_ADDR + i * 4);
  return true;
}

static void borrarConfig() {
  EEPROM.write(EEPROM_FLAG_ADDR, 0x00);
  EEPROM.commit();
  Serial.println("[EEPROM] Config borrada. Reiniciando...");
  delay(500);
  ESP.restart();
}


// ─── Escaneo WiFi ─────────────────────────────────────────────────────────────

static void iniciarScan() {
  if (_scanEnCurso) return;
  _scanEnCurso = true;
  WiFi.scanNetworksAsync([](int n) {
    String json = "[";
    for (int i = 0; i < n; i++) {
      if (i > 0) json += ",";
      json += "{\"ssid\":\"" + WiFi.SSID(i) + "\","
              "\"rssi\":"    + String(WiFi.RSSI(i)) + ","
              "\"secure\":"  + String(WiFi.encryptionType(i) != ENC_TYPE_NONE ? "true" : "false") + "}";
    }
    json += "]";
    _redesJson   = json;
    _tScan       = millis();
    _scanEnCurso = false;
    Serial.printf("[Scan] %d redes encontradas.\n", n);
  });
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
  <title>Hub Domótico — Vincular</title>
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
  <h1>🏠 Hub Domótico</h1>
  <p class="sub">Vincula este dispositivo a tu red</p>
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

    <!--<label>Ubicación (ej: sala, cocina)</label>
    <input type="text" name="ubicacion" placeholder="sala" required>
    -->
    <input type="submit" value="Vincular dispositivo">
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
// Escanear automáticamente al cargar
window.onload = escanear;
</script>
</body></html>
  )rawhtml";
}


// ─── Registro en el hub ───────────────────────────────────────────────────────

static bool registrarEnHub(const String& codigo) {
  String url = String(HUB_URL) + "/vincular/registrar";
  Serial.printf("[Hub] POST %s\n", url.c_str());

  //WiFiClient cliente;
  //HTTPClient http;
  //http.begin(cliente, url);
  WiFiClientSecure cliente;
  cliente.setInsecure();
  cliente.setTimeout(10000);
  HTTPClient http;
  http.begin(cliente, url);
  http.setTimeout(10000); 
  http.addHeader("Content-Type", "application/json");

  // Construir JSON
  JsonDocument doc;
  doc["mac"]      = WiFi.macAddress();
  doc["codigo"]   = codigo;

  JsonArray sensoresArr = doc["sensores"].to<JsonArray>();
  for (int i = 0; i < _numSensores; i++) {
    JsonObject s = sensoresArr.add<JsonObject>();
    s["tipo"]   = _sensores[i].tipo;
    s["unidad"] = _sensores[i].unidad;
  }

  JsonArray actuadoresArr = doc["actuadores"].to<JsonArray>();
  for (int i = 0; i < _numActuadores; i++) {
    JsonObject a = actuadoresArr.add<JsonObject>();
    a["tipo"] = _actuadores[i].tipo;
    a["pin"]  = _actuadores[i].pin;
  }

  String body;
  serializeJson(doc, body);
  Serial.printf("[Hub] Body: %s\n", body.c_str());

  int codigo_http = http.POST(body);

  if (codigo_http == 200 || codigo_http == 201) {
    String resp = http.getString();
    Serial.printf("[Hub] Respuesta: %s\n", resp.c_str());

    JsonDocument respDoc;
    if (!deserializeJson(respDoc, resp)) {
      cfg.dispositivoId = respDoc["dispositivo_id"].as<int>();

      // Guardar IDs de sensores
      JsonArray sIds = respDoc["sensores"].as<JsonArray>();
      int i = 0;
      for (JsonObject s : sIds) {
        if (i < MAX_SENSORES) cfg.sensorIds[i++] = s["id"].as<int>();
      }

      // Guardar IDs de actuadores
      JsonArray aIds = respDoc["actuadores"].as<JsonArray>();
      i = 0;
      for (JsonObject a : aIds) {
        if (i < MAX_ACTUADORES) cfg.actuadorIds[i++] = a["id"].as<int>();
      }

      guardarConfig();
      Serial.printf("[Hub] Registrado. dispositivo_id: %d\n", cfg.dispositivoId);
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
  snprintf(apSSID, sizeof(apSSID), "%s-%02X%02X", AP_SSID_PREFIX, mac[4], mac[5]);

  WiFi.mode(WIFI_AP);
  WiFi.softAP(apSSID);
  Serial.printf("[AP] Red: %s  IP: %s\n", apSSID, WiFi.softAPIP().toString().c_str());

  // Escanear redes inmediatamente al levantar el AP
  iniciarScan();

  dnsServer.start(DNS_PORT, "*", WiFi.softAPIP());

  // Página principal
  server.on("/", HTTP_GET, []() {
    server.send(200, "text/html", construirHTML());
  });

  // Endpoint de escaneo WiFi — el frontend lo llama con fetch()
  server.on("/scan", HTTP_GET, []() {
    // Si el scan tiene más de 30 s, lanzar uno nuevo
    if (millis() - _tScan > 30000 && !_scanEnCurso) iniciarScan();
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", _redesJson);
  });

  // Redirect captive portal
  server.onNotFound([]() {
    server.sendHeader("Location", "http://192.168.4.1/", true);
    server.send(302, "text/plain", "");
  });

  // Guardar configuración
  server.on("/guardar", HTTP_POST, []() {
    String ssid      = server.arg("ssid");
    String password  = server.arg("password");
    String codigo    = server.arg("codigo");
    //String ubicacion = server.arg("ubicacion");

    if (ssid == "" || codigo == "") {// || ubicacion == ""
      server.send(200, "text/html", construirHTML("Error: completa todos los campos obligatorios."));
      return;
    }

    // Probar conexión WiFi
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

    // Guardar credenciales
    ssid.toCharArray(cfg.ssid,          sizeof(cfg.ssid));
    password.toCharArray(cfg.password,  sizeof(cfg.password));
    //ubicacion.toCharArray(cfg.ubicacion,sizeof(cfg.ubicacion));
    cfg.dispositivoId = 0;
    memset(cfg.sensorIds,   0, sizeof(cfg.sensorIds));
    memset(cfg.actuadorIds, 0, sizeof(cfg.actuadorIds));

    // Registrar en el hub
    server.send(200, "text/html", construirHTML("✅ WiFi conectado. Registrando en el hub…"));
    delay(500);

    if (registrarEnHub(codigo)) {
      Serial.println("[Portal] Registro exitoso. Reiniciando...");
      delay(1500);
      ESP.restart();
    } else {
      // Si falla el registro igual guardamos WiFi y reiniciamos
      // — el dispositivo intentará registrarse en el próximo boot
      guardarConfig();
      Serial.println("[Portal] Registro fallido. Guardando WiFi y reiniciando...");
      delay(1500);
      ESP.restart();
    }
  });

  server.begin();
  Serial.println("[Portal] Esperando configuración...");
}


// ─── Conectar WiFi (modo operación normal) ────────────────────────────────────

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

void portalSetup(SensorInfo* sensores,   int numSensores,
                 ActuadorInfo* actuadores, int numActuadores) {
  _sensores      = sensores;
  _numSensores   = numSensores;
  _actuadores    = actuadores;
  _numActuadores = numActuadores;

  pinMode(LED_PIN,   OUTPUT);
  pinMode(RESET_PIN, INPUT_PULLUP);
  digitalWrite(LED_PIN, HIGH);

  EEPROM.begin(EEPROM_SIZE);

  // Botón de reset: 3 s al arrancar → borra config
  if (digitalRead(RESET_PIN) == LOW) {
    Serial.println("[Reset] Botón detectado. Mantenlo 3 s para borrar config...");
    delay(3000);
    if (digitalRead(RESET_PIN) == LOW) borrarConfig();
  }

  if (cargarConfig()) {
    Serial.println("[EEPROM] Config encontrada.");
    Serial.printf("  SSID:          %s\n", cfg.ssid);
    //Serial.printf("  Ubicación:     %s\n", cfg.ubicacion);
    Serial.printf("  dispositivo_id:%d\n", cfg.dispositivoId);
    for (int i = 0; i < _numSensores; i++)
      Serial.printf("  sensor[%d] id:  %d\n", i, cfg.sensorIds[i]);
    for (int i = 0; i < _numActuadores; i++)
      Serial.printf("  actuador[%d] id:%d\n", i, cfg.actuadorIds[i]);

    conectarWiFi();

    // Si no tiene IDs registrados, intentar registro de nuevo
    if (cfg.dispositivoId == 0) {
      Serial.println("[Hub] Sin dispositivo_id. El portal asignará uno en el próximo reset.");
    }

    configurado = true;
  } else {
    Serial.println("[EEPROM] Sin config. Iniciando portal...");
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