from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import get_db

router = APIRouter(prefix="/actuadores", tags=["Actuadores"])


# ── Modelos ────────────────────────────────────────────────────────────────────

class EditarActuador(BaseModel):
    nombre: str

class CambiarEstado(BaseModel):
    estado: str  # "on" | "off" | "toggle"


# ── GET /actuadores ────────────────────────────────────────────────────────────

@router.get("/")
def listar_actuadores(db=Depends(get_db)):
    filas = db.execute("""
        SELECT a.*, d.ubicacion, d.nombre AS dispositivo_nombre
        FROM actuadores a
        JOIN dispositivos d ON a.dispositivo_id = d.id
    """).fetchall()
    return [dict(f) for f in filas]


# ── GET /actuadores/{id} ───────────────────────────────────────────────────────

@router.get("/{id}")
def detalle_actuador(id: int, db=Depends(get_db)):
    actuador = db.execute("SELECT * FROM actuadores WHERE id = ?", (id,)).fetchone()

    if not actuador:
        raise HTTPException(status_code=404, detail="Actuador no encontrado")

    # actualizar ultimo_contacto del dispositivo
    ahora = datetime.now().isoformat()
    db.execute(
        "UPDATE dispositivos SET ultimo_contacto = ? WHERE id = ?",
        (ahora, actuador["dispositivo_id"])
    )
    db.commit()

    return dict(actuador)


# ── PATCH /actuadores/{id} ─────────────────────────────────────────────────────

@router.patch("/{id}")
def editar_actuador(id: int, datos: EditarActuador, db=Depends(get_db)):
    actuador = db.execute("SELECT id FROM actuadores WHERE id = ?", (id,)).fetchone()

    if not actuador:
        raise HTTPException(status_code=404, detail="Actuador no encontrado")

    db.execute("UPDATE actuadores SET nombre = ? WHERE id = ?", (datos.nombre, id))
    db.commit()
    return db.execute("SELECT * FROM actuadores WHERE id = ?", (id,)).fetchone()

@router.patch("/{id}/favorito")
def toggle_favorito(id: int, db=Depends(get_db)):
    tabla = "actuadores"  
    fila  = db.execute(f"SELECT favorito FROM {tabla} WHERE id = ?", (id,)).fetchone()
    if not fila:
        raise HTTPException(status_code=404, detail="No encontrado")
    nuevo = 0 if fila["favorito"] else 1
    db.execute(f"UPDATE {tabla} SET favorito = ? WHERE id = ?", (nuevo, id))
    db.commit()
    return { "id": id, "favorito": bool(nuevo) }
    
# ── PUT /actuadores/{id}/estado ────────────────────────────────────────────────

@router.put("/{id}/estado")
def cambiar_estado(id: int, datos: CambiarEstado, db=Depends(get_db)):
    actuador = db.execute("SELECT * FROM actuadores WHERE id = ?", (id,)).fetchone()

    if not actuador:
        raise HTTPException(status_code=404, detail="Actuador no encontrado")

    ahora = datetime.now().isoformat()

    if datos.estado == "toggle":
        nuevo_estado = "off" if actuador["estado"] == "on" else "on"
    elif datos.estado in ("on", "off"):
        nuevo_estado = datos.estado
    else:
        raise HTTPException(status_code=400, detail="Estado inválido. Usa 'on', 'off' o 'toggle'")

    db.execute(
        "UPDATE actuadores SET estado = ?, ultimo_cambio = ? WHERE id = ?",
        (nuevo_estado, ahora, id)
    )
    db.commit()

    return {
        **dict(actuador),
        "estado":        nuevo_estado,
        "ultimo_cambio": ahora
    }