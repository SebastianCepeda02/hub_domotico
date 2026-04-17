from fastapi import APIRouter, HTTPException, Security
from dependencies import verificar_api_key
from datetime import datetime
import os

router = APIRouter(prefix="/sistema", tags=["sistema"])

@router.get("/estado")
def obtener_estado_completo(key = Security(verificar_api_key)):
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