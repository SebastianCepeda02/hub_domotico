# Hub Domótico

Hub de automatización del hogar corriendo en una Raspberry Pi 3, con API REST en FastAPI y dashboard web en Alpine.js. Expuesto en internet vía Cloudflare Tunnel.

---

## Estructura del proyecto

```
hub_domotico/
├── main.py                  # Punto de entrada FastAPI
├── database.py              # Conexión SQLite y creación de tablas
├── dependencies.py          # Verificación de API Key
├── models/
│   ├── actuadores.py        # Modelos Pydantic de actuadores y dispositivos
│   └── sensores.py          # Modelos Pydantic de sensores
├── routers/
│   ├── sensores.py          # POST/GET lecturas DHT11 (requiere API Key)
│   ├── dispositivos.py      # Registro de dispositivos ESP32 (requiere API Key)
│   ├── actuadores.py        # CRUD actuadores (requiere API Key)
│   ├── sistema.py           # Estado del hardware Pi (requiere API Key)
│   └── ui.py                # Endpoints públicos para el dashboard web
└── frontend/
    ├── index.html           # Dashboard (Alpine.js + Tailwind CSS)
    └── static/
        └── app.js           # Lógica reactiva del dashboard
```

---

## Base de datos (SQLite)

Ubicación: `/mnt/datos/hub_domotico/hub.db`

| Tabla | Descripción |
|---|---|
| `dispositivos` | ESP32 registrados (MAC, ubicación) |
| `actuadores` | Actuadores por dispositivo (LED, buzzer, relé, etc.) |
| `lecturas_dht11` | Historial de temperatura y humedad |
| `automatizaciones` | Reglas if/then entre sensores y actuadores |

---

## API

### Autenticación

Los endpoints de sensores, dispositivos, actuadores y sistema requieren la cabecera:

```
X-API-Key: <tu_api_key>
```

La clave se define en el archivo `.env`:

```env
HUB_API_KEY=tu_clave_secreta
```

### Endpoints protegidos (ESP32 / administración)

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/sensores/dht11` | Guardar lectura de temperatura y humedad |
| `GET` | `/sensores/dht11/filtrar` | Filtrar lecturas por ubicación o límite |
| `GET` | `/sensores/dht11/{id}` | Obtener lectura por ID |
| `POST` | `/dispositivos/registro` | Registrar un dispositivo ESP32 |
| `POST` | `/actuadores` | Crear un actuador |
| `GET` | `/actuadores/{dispositivo_id}` | Listar actuadores de un dispositivo |
| `PUT` | `/actuadores/{id}/estado` | Cambiar estado de un actuador |
| `GET` | `/sistema/estado` | Estado del hardware (CPU, RAM, disco) |

### Endpoints públicos (dashboard web)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/ui/sistema` | Estado del hardware para el dashboard |
| `GET` | `/ui/dispositivos` | Dispositivos con sus actuadores |
| `GET` | `/ui/sensores/recientes` | Última lectura por ubicación + historial |
| `PUT` | `/ui/actuadores/{id}/estado` | Cambiar estado de actuador desde la UI |
| `GET` | `/ui/automatizaciones` | Listar automatizaciones |
| `POST` | `/ui/automatizaciones` | Crear automatización |
| `PUT` | `/ui/automatizaciones/{id}/toggle` | Activar/desactivar automatización |
| `DELETE` | `/ui/automatizaciones/{id}` | Eliminar automatización |

---

## Dashboard

Accedé desde el navegador en la raíz del dominio: `https://tu-dominio.com`

**Panel izquierdo:**
- Dispositivos registrados con toggle ON/OFF para cada actuador
- Automatizaciones activas con toggle y botón eliminar
- Formulario para crear nuevas reglas (condición sensor → acción actuador)

**Panel principal:**
- Estado del sistema: CPU, RAM, almacenamiento SD y USB
- Última lectura de cada sensor DHT11
- Historial de las últimas 20 lecturas

Se actualiza automáticamente cada 30 segundos.

---

## Despliegue en la Pi

### Requisitos

```bash
pip install fastapi uvicorn python-dotenv
```

### Variables de entorno

Crear archivo `.env` en la raíz del proyecto:

```env
HUB_API_KEY=tu_clave_secreta
```

### Ejecutar

```bash
cd /mnt/datos/hub_domotico
source entorno_domotico/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Exponer con Cloudflare Tunnel

```bash
cloudflared tunnel run <nombre-del-tunnel>
```

---

## Ejemplo: registrar lectura desde ESP32

```python
import urequests

url = "https://tu-dominio.com/sensores/dht11"
headers = {"X-API-Key": "tu_clave_secreta", "Content-Type": "application/json"}
data = {"ubicacion": "sala", "temperatura": 24.5, "humedad": 60.0}

urequests.post(url, json=data, headers=headers)
```

---

## Automatizaciones

Una automatización define una regla:

> Si `[sensor en ubicación X]` supera/baja del `[umbral]` → `[actuador Y]` se `[enciende/apaga]`

Ejemplo: `Si temperatura > 35°C en sala → buzzer encendido`

> **Nota:** La ejecución automática de las reglas (polling de sensores) se implementa como tarea programada separada.
