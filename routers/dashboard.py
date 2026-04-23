from datetime import datetime
from fastapi import APIRouter, Depends
from database import get_db

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def calcular_online(ultimo_contacto: str | None) -> bool:
    if not ultimo_contacto:
        return False
    diferencia = datetime.now() - datetime.fromisoformat(ultimo_contacto)
    return diferencia.total_seconds() < 120


def calcular_last_seen(ultimo_contacto: str | None) -> str | None:
    if not ultimo_contacto:
        return None
    segundos = (datetime.now() - datetime.fromisoformat(ultimo_contacto)).total_seconds()
    if segundos < 60:
        return f"hace {int(segundos)} s"
    elif segundos < 3600:
        return f"hace {int(segundos // 60)} min"
    else:
        return f"hace {int(segundos // 3600)} h"


# ── GET /dashboard ────────────────────────────────────────────────────────────

@router.get("/")
def obtener_dashboard(db=Depends(get_db)):
    dispositivos = db.execute("SELECT * FROM dispositivos").fetchall()
    resultado    = []

    for dispositivo in dispositivos:
        online    = calcular_online(dispositivo["ultimo_contacto"])
        last_seen = calcular_last_seen(dispositivo["ultimo_contacto"])

        # ── Sensores del dispositivo ──────────────────────────────────────────
        sensores = db.execute(
            "SELECT * FROM sensores WHERE dispositivo_id = ?", (dispositivo["id"],)
        ).fetchall()

        for sensor in sensores:
            ultima = db.execute("""
                SELECT valor FROM lecturas
                WHERE sensor_id = ?
                ORDER BY id DESC LIMIT 1
            """, (sensor["id"],)).fetchone()

            resultado.append({
                "id":       sensor["id"],
                "kind":     sensor["tipo"],
                "name":     sensor["nombre"] or sensor["tipo"],
                "room":     dispositivo["ubicacion"] or "Sin ubicación",
                "unit":     sensor["unidad"],
                "value":    ultima["valor"] if ultima else None,
                "online":   online,
                "lastSeen": last_seen,
                "category": "sensor",
                "dispositivo_id": dispositivo["id"], 
                "favorite":       bool(sensor["favorito"])
            })

        # ── Actuadores del dispositivo ────────────────────────────────────────
        actuadores = db.execute(
            "SELECT * FROM actuadores WHERE dispositivo_id = ?", (dispositivo["id"],)
        ).fetchall()

        for actuador in actuadores:
            resultado.append({
                "id":       actuador["id"],
                "kind":     actuador["tipo"],
                "name":     actuador["nombre"] or actuador["tipo"],
                "room":     dispositivo["ubicacion"] or "Sin ubicación",
                "on":       actuador["estado"] == "on",
                "online":   online,
                "lastSeen": last_seen,
                "category": "actuador",
                "dispositivo_id": dispositivo["id"],  
                "favorite":       bool(actuador["favorito"])
            })

    return resultado