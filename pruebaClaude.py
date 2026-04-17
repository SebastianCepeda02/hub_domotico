#cd /mnt/datos/hub_domotico
#source entorno_domotico/bin/activate
# python3 main.py
# uvicorn pruebaClaude:app --reload
#uvicorn aromatizador:app --host 0.0.0.0 --port 8000 --reload

from fastapi import FastAPI, Query, HTTPException, Depends
from pydantic import BaseModel
import sqlite3
from datetime import datetime
from typing import Optional
import os
from dotenv import load_dotenv
from fastapi.security import APIKeyHeader
from fastapi import Security


# --- Configuración API Key ---
load_dotenv()

API_KEY = os.environ.get("HUB_API_KEY")

if not API_KEY:
    raise RuntimeError("HUB_API_KEY no está definida en el archivo .env")

api_key_header = APIKeyHeader(name="X-API-Key")

def verificar_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="API Key inválida")
    return key


app = FastAPI()

# --- Manejador global ---
@app.exception_handler(Exception)
async def manejador_global(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Error interno del servidor", "detalle": str(exc)}
    )

@app.exception_handler(sqlite3.Error)
async def manejador_sqlite(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Error en la base de datos", "detalle": str(exc)}
    )
# --- Modelos ---
class DispositivoRegistro(BaseModel):
    mac: str
    ubicacion: str

class ActuadorCreate(BaseModel):
    dispositivo_id: int
    tipo: str
    estado: str
    pin: Optional[int] = None

class LecturaDHT11(BaseModel):
    ubicacion: str
    temperatura: float
    humedad: float

class ActuadorEstado(BaseModel):
    estado: str

def obtener_conexion():
    conexion = sqlite3.connect("hub.db")
    conexion.row_factory = sqlite3.Row
    return conexion

def get_db():
    conexion = obtener_conexion()
    try:
        yield conexion
    finally:
        conexion.close()

def crear_tabla():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lecturas_dht11 (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ubicacion   TEXT NOT NULL,
            temperatura REAL NOT NULL,
            humedad     REAL NOT NULL,
            fecha       TEXT NOT NULL
        )
    """)
    conexion.commit()
    conexion.close()

crear_tabla()

# --- Tabla dispositivos y actuadores ---
def crear_tablas():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dispositivos (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            mac              TEXT    NOT NULL UNIQUE,
            ubicacion        TEXT    NOT NULL,
            fecha_registro   TEXT    NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS actuadores (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            dispositivo_id  INTEGER NOT NULL,
            tipo            TEXT    NOT NULL,
            pin             INTEGER NULL,
            estado          TEXT    NOT NULL,
            FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id)
        )
    """)
    conexion.commit()
    conexion.close()

crear_tablas()

@app.get("/")
def inicio():
    return {"mensaje": "Hub domótico funcionando"}

# --- Endpoints con try/except local ---
@app.post("/sensores/dht11")
def recibir_lectura(lectura: LecturaDHT11, conexion = Depends(get_db), key = Security(verificar_api_key)):
    try:
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO lecturas_dht11 (ubicacion, temperatura, humedad, fecha)
            VALUES (?, ?, ?, ?)
        """, (lectura.ubicacion, lectura.temperatura, lectura.humedad, datetime.now().isoformat()))
        conexion.commit()
        return {"mensaje": "Lectura guardada", "datos": lectura}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar: {str(e)}")

@app.get("/sensores/dht11/filtrar")
def filtrar_lecturas(ubicacion: str = Query(default=None), limite: int = Query(default=None),
    conexion = Depends(get_db), key = Security(verificar_api_key)
):
    try:
        cursor = conexion.cursor()
        
        if ubicacion and limite:
            cursor.execute("""
                SELECT * FROM lecturas_dht11
                WHERE ubicacion = ? LIMIT ?
            """, (ubicacion, limite))
        elif ubicacion:
            cursor.execute("""
                SELECT * FROM lecturas_dht11
                WHERE ubicacion = ?
            """, (ubicacion,))
        elif limite:
            cursor.execute("""
                SELECT * FROM lecturas_dht11
                LIMIT ?
            """, (limite,))
        else:
            cursor.execute("SELECT * FROM lecturas_dht11")
        
        lecturas = cursor.fetchall()
        return {"lecturas": [dict(lectura) for lectura in lecturas]}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar: {str(e)}")

@app.get("/sensores/dht11/{id}")
def obtener_lectura(id: int, conexion = Depends(get_db), key = Security(verificar_api_key)):
    try:
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT * FROM lecturas_dht11
            WHERE id = ?
        """, (id,))
        lectura = cursor.fetchone()

        if lectura is None:
            raise HTTPException(status_code=404, detail="Lectura no encontrada")
        
        return {"lectura": dict(lectura)}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar: {str(e)}")

# --- Endpoints actuadores
@app.post("/dispositivos/registro")
def registrar_dispositivo(dispositivo: DispositivoRegistro, conexion = Depends(get_db), 
    key = Security(verificar_api_key)):
    try:
        cursor = conexion.cursor()

        # verificar si la MAC ya existe
        cursor.execute("""
            SELECT id FROM dispositivos WHERE mac = ?
        """, (dispositivo.mac,))
        existente = cursor.fetchone()

        if existente:
            # borrar actuadores anteriores
            cursor.execute("""
                DELETE FROM actuadores WHERE dispositivo_id = ?
            """, (existente["id"],))
            conexion.commit()
            return {
                "mensaje": "Dispositivo ya registrado, actuadores reiniciados",
                "dispositivo_id": existente["id"]
            }
        else:
            # registrar nuevo dispositivo
            cursor.execute("""
                INSERT INTO dispositivos (mac, ubicacion, fecha_registro)
                VALUES (?, ?, ?)
            """, (dispositivo.mac, dispositivo.ubicacion, datetime.now().isoformat()))
            conexion.commit()
            return {
                "mensaje": "Dispositivo registrado",
                "dispositivo_id": cursor.lastrowid
            }

    except sqlite3.Error as e:
        conexion.rollback()
        raise HTTPException(status_code=500, detail=f"Error al registrar: {str(e)}")

@app.post("/actuadores")
def crear_actuador(actuador: ActuadorCreate, conexion = Depends(get_db), key = Security(verificar_api_key)):
    try:
        cursor = conexion.cursor()

        # verificar que el dispositivo existe
        cursor.execute("""
            SELECT id FROM dispositivos WHERE id = ?
        """, (actuador.dispositivo_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

        cursor.execute("""
            INSERT INTO actuadores (dispositivo_id, tipo, pin, estado)
            VALUES (?, ?, ?, ?)
        """, (actuador.dispositivo_id, actuador.tipo, actuador.pin, actuador.estado))
        conexion.commit()
        return {"mensaje": "Actuador registrado", "id": cursor.lastrowid}

    except sqlite3.Error as e:
        conexion.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear actuador: {str(e)}")

@app.get("/actuadores/{dispositivo_id}")
def obtener_actuadores(dispositivo_id: int, conexion = Depends(get_db), key = Security(verificar_api_key)):
    try:
        cursor = conexion.cursor()

        # verificar que el dispositivo existe
        cursor.execute("""
            SELECT id FROM dispositivos WHERE id = ?
        """, (dispositivo_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

        cursor.execute("""
            SELECT * FROM actuadores WHERE dispositivo_id = ?
        """, (dispositivo_id,))
        actuadores = cursor.fetchall()
        return {"actuadores": [dict(actuador) for actuador in actuadores]}

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar: {str(e)}")

@app.put("/actuadores/{id}/estado")
def actualizar_estado(id: int, datos: ActuadorEstado, conexion = Depends(get_db), key = Security(verificar_api_key)):
    try:
        cursor = conexion.cursor()

        # verificar que el actuador existe
        cursor.execute("""
            SELECT id FROM actuadores WHERE id = ?
        """, (id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Actuador no encontrado")

        cursor.execute("""
            UPDATE actuadores SET estado = ? WHERE id = ?
        """, (datos.estado, id))
        conexion.commit()
        return {"mensaje": "Estado actualizado", "id": id, "estado": datos.estado}

    except sqlite3.Error as e:
        conexion.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar: {str(e)}")

######### enpoint healt raspberry pi

@app.get("/sistema/estado")
def obtener_estado_completo():
    try:
        # 1. TEMPERATURA
        temp_raw = os.popen("vcgencmd measure_temp").read().replace("temp=", "").replace("'C", "").strip()
        temperatura = float(temp_raw)

        # 2. RAM
        ram_info = os.popen("free -m | grep Mem:").read().split()
        total_ram = int(ram_info[1])
        disp_ram = int(ram_info[6])
        uso_ram_porc = round(((total_ram - disp_ram) / total_ram) * 100, 1)

        # 3. DISCO SD (Sistema)
        st_sd = os.statvfs("/")
        sd_total = round((st_sd.f_blocks * st_sd.f_frsize) / (1024**3), 2)
        sd_libre = round((st_sd.f_bavail * st_sd.f_frsize) / (1024**3), 2)

        # 4. DISCO USB (Datos)
        # Apuntamos a la ruta donde montaste tu USB
        ruta_usb = "/mnt/datos"
        try:
            st_usb = os.statvfs(ruta_usb)
            usb_total = round((st_usb.f_blocks * st_usb.f_frsize) / (1024**3), 2)
            usb_libre = round((st_usb.f_bavail * st_usb.f_frsize) / (1024**3), 2)
            usb_uso_porc = round(((usb_total - usb_libre) / usb_total) * 100, 1)
        except Exception:
            # Por si la USB se desconecta, para que no rompa todo el JSON
            usb_total, usb_libre, usb_uso_porc = 0, 0, 0

        return {
            "estado": "online",
            "cpu_temperatura": f"{temperatura}°C",
            "ram": {
                "total_mb": total_ram,
                "disponible_mb": disp_ram,
                "uso_porcentaje": f"{uso_ram_porc}%"
            },
            "almacenamiento_sd": {
                "total_gb": sd_total,
                "libre_gb": sd_libre
            },
            "almacenamiento_usb": {
                "ruta": ruta_usb,
                "total_gb": usb_total,
                "libre_gb": usb_libre,
                "uso_porcentaje": f"{usb_uso_porc}%"
            },
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {"error": "Fallo al leer hardware", "detalle": str(e)}