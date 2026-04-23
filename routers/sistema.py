from fastapi import APIRouter, HTTPException
from datetime import datetime
import os

router = APIRouter(prefix="/sistema", tags=["sistema"])

@router.get("/estado")
def obtener_estado_completo():
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
        st_usb = os.statvfs("/mnt/mi_usb")
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