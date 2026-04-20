from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import get_db
from datetime import datetime
import os

router = APIRouter(prefix="/ui", tags=["ui"])


class ActuadorEstado(BaseModel):
    estado: str


class AutomatizacionCreate(BaseModel):
    nombre: str
    condicion_tipo: str
    condicion_valor: float
    condicion_ubicacion: str
    accion_actuador_id: int
    accion_estado: str


@router.get("/sistema")
def estado_sistema():
    try:
        temp_raw = os.popen("vcgencmd measure_temp").read().replace("temp=", "").replace("'C", "").strip()
        temperatura = float(temp_raw)
        cpu_temp = f"{temperatura}°C"
    except Exception:
        cpu_temp = "N/A"

    try:
        ram_info = os.popen("free -m | grep Mem:").read().split()
        total_ram = int(ram_info[1])
        disp_ram = int(ram_info[6])
        uso_ram_porc = round(((total_ram - disp_ram) / total_ram) * 100, 1)
        ram = {"total_mb": total_ram, "disponible_mb": disp_ram, "uso_porcentaje": f"{uso_ram_porc}%"}
    except Exception:
        ram = None

    try:
        st_sd = os.statvfs("/")
        sd = {
            "total_gb": round((st_sd.f_blocks * st_sd.f_frsize) / (1024**3), 2),
            "libre_gb": round((st_sd.f_bavail * st_sd.f_frsize) / (1024**3), 2),
        }
    except Exception:
        sd = None

    try:
        st_usb = os.statvfs("/mnt/datos")
        usb_total = round((st_usb.f_blocks * st_usb.f_frsize) / (1024**3), 2)
        usb_libre = round((st_usb.f_bavail * st_usb.f_frsize) / (1024**3), 2)
        usb = {
            "total_gb": usb_total,
            "libre_gb": usb_libre,
            "uso_porcentaje": f"{round(((usb_total - usb_libre) / usb_total) * 100, 1)}%" if usb_total else "0%",
        }
    except Exception:
        usb = {"total_gb": 0, "libre_gb": 0, "uso_porcentaje": "0%"}

    return {
        "estado": "online",
        "cpu_temperatura": cpu_temp,
        "ram": ram,
        "almacenamiento_sd": sd,
        "almacenamiento_usb": usb,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/dispositivos")
def listar_dispositivos(conexion=Depends(get_db)):
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM dispositivos ORDER BY fecha_registro DESC")
    dispositivos = [dict(d) for d in cursor.fetchall()]
    for disp in dispositivos:
        cursor.execute("SELECT * FROM actuadores WHERE dispositivo_id = ?", (disp["id"],))
        disp["actuadores"] = [dict(a) for a in cursor.fetchall()]
    return dispositivos


@router.get("/sensores/recientes")
def sensores_recientes(conexion=Depends(get_db)):
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT l.* FROM lecturas_dht11 l
        INNER JOIN (
            SELECT ubicacion, MAX(id) as max_id FROM lecturas_dht11 GROUP BY ubicacion
        ) sub ON l.id = sub.max_id
        ORDER BY l.fecha DESC
    """)
    recientes = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM lecturas_dht11 ORDER BY id DESC LIMIT 20")
    historial = [dict(r) for r in cursor.fetchall()]

    return {"recientes": recientes, "historial": historial}


@router.put("/actuadores/{id}/estado")
def cambiar_estado_actuador(id: int, datos: ActuadorEstado, conexion=Depends(get_db)):
    cursor = conexion.cursor()
    cursor.execute("SELECT id FROM actuadores WHERE id = ?", (id,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="Actuador no encontrado")
    cursor.execute("UPDATE actuadores SET estado = ? WHERE id = ?", (datos.estado, id))
    conexion.commit()
    return {"id": id, "estado": datos.estado}


@router.get("/automatizaciones")
def listar_automatizaciones(conexion=Depends(get_db)):
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM automatizaciones ORDER BY fecha_creacion DESC")
    return [dict(a) for a in cursor.fetchall()]


@router.post("/automatizaciones")
def crear_automatizacion(auto: AutomatizacionCreate, conexion=Depends(get_db)):
    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO automatizaciones
        (nombre, condicion_tipo, condicion_valor, condicion_ubicacion, accion_actuador_id, accion_estado, activa, fecha_creacion)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
    """, (auto.nombre, auto.condicion_tipo, auto.condicion_valor, auto.condicion_ubicacion,
          auto.accion_actuador_id, auto.accion_estado, datetime.now().isoformat()))
    conexion.commit()
    return {"mensaje": "Automatización creada", "id": cursor.lastrowid}


@router.put("/automatizaciones/{id}/toggle")
def toggle_automatizacion(id: int, conexion=Depends(get_db)):
    cursor = conexion.cursor()
    cursor.execute("SELECT id, activa FROM automatizaciones WHERE id = ?", (id,))
    auto = cursor.fetchone()
    if auto is None:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")
    nuevo_estado = 0 if auto["activa"] else 1
    cursor.execute("UPDATE automatizaciones SET activa = ? WHERE id = ?", (nuevo_estado, id))
    conexion.commit()
    return {"id": id, "activa": bool(nuevo_estado)}


@router.delete("/automatizaciones/{id}")
def eliminar_automatizacion(id: int, conexion=Depends(get_db)):
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM automatizaciones WHERE id = ?", (id,))
    conexion.commit()
    return {"mensaje": "Automatización eliminada"}
