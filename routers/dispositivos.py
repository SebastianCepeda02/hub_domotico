from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import get_db

router = APIRouter(prefix="/dispositivos", tags=["Dispositivos"])


# ── Modelos ────────────────────────────────────────────────────────────────────

class EditarDispositivo(BaseModel):
    nombre:    str | None = None
    ubicacion: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def calcular_online(ultimo_contacto: str | None) -> bool:
    if not ultimo_contacto:
        return False
    diferencia = datetime.now() - datetime.fromisoformat(ultimo_contacto)
    return diferencia.total_seconds() < 120  # 2 minutos


# ── GET /dispositivos ──────────────────────────────────────────────────────────

@router.get("/")
def listar_dispositivos(db=Depends(get_db)):
    filas = db.execute("SELECT * FROM dispositivos").fetchall()
    return [
        {**dict(f), "online": calcular_online(f["ultimo_contacto"])}
        for f in filas
    ]


# ── GET /dispositivos/{id} ─────────────────────────────────────────────────────

@router.get("/{id}")
def detalle_dispositivo(id: int, db=Depends(get_db)):
    dispositivo = db.execute(
        "SELECT * FROM dispositivos WHERE id = ?", (id,)
    ).fetchone()

    if not dispositivo:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

    sensores = db.execute(
        "SELECT * FROM sensores WHERE dispositivo_id = ?", (id,)
    ).fetchall()

    actuadores = db.execute(
        "SELECT * FROM actuadores WHERE dispositivo_id = ?", (id,)
    ).fetchall()

    return {
        **dict(dispositivo),
        "online":     calcular_online(dispositivo["ultimo_contacto"]),
        "sensores":   [dict(s) for s in sensores],
        "actuadores": [dict(a) for a in actuadores]
    }


# ── PATCH /dispositivos/{id} ───────────────────────────────────────────────────

@router.patch("/{id}")
def editar_dispositivo(id: int, datos: EditarDispositivo, db=Depends(get_db)):
    dispositivo = db.execute(
        "SELECT id FROM dispositivos WHERE id = ?", (id,)
    ).fetchone()

    if not dispositivo:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

    if datos.nombre is not None:
        db.execute("UPDATE dispositivos SET nombre = ? WHERE id = ?", (datos.nombre, id))

    if datos.ubicacion is not None:
        db.execute("UPDATE dispositivos SET ubicacion = ? WHERE id = ?", (datos.ubicacion, id))

    db.commit()
    return db.execute("SELECT * FROM dispositivos WHERE id = ?", (id,)).fetchone()


# ── DELETE /dispositivos/{id} ──────────────────────────────────────────────────

@router.delete("/{id}")
def eliminar_dispositivo(id: int, db=Depends(get_db)):
    dispositivo = db.execute(
        "SELECT id FROM dispositivos WHERE id = ?", (id,)
    ).fetchone()

    if not dispositivo:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

    db.execute("DELETE FROM actuadores WHERE dispositivo_id = ?", (id,))
    db.execute("DELETE FROM sensores    WHERE dispositivo_id = ?", (id,))
    db.execute("DELETE FROM dispositivos WHERE id = ?", (id,))
    db.commit()

    return { "detail": "Dispositivo eliminado" }