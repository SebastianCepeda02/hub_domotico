from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import get_db

router = APIRouter(prefix="/automatizaciones", tags=["Automatizaciones"])


# ── Modelos ────────────────────────────────────────────────────────────────────

class NuevaRegla(BaseModel):
    nombre:      str
    sensor_id:   int
    operador:    str   # ">" | "<" | "==" | "!="
    umbral:      float
    actuador_id: int
    accion:      str   # "on" | "off" | "toggle"

class EditarRegla(BaseModel):
    nombre:      str | None = None
    operador:    str | None = None
    umbral:      float | None = None
    accion:      str | None = None
    activa:      int | None = None

class NuevaEscena(BaseModel):
    nombre:      str
    disparador:  str   # "manual" | "HH:MM"
    actuador_id: int
    accion:      str   # "on" | "off" | "toggle"

class EditarEscena(BaseModel):
    nombre:      str | None = None
    disparador:  str | None = None
    accion:      str | None = None
    activa:      int | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def ejecutar_accion(actuador_id: int, accion: str, ahora: str, db):
    actuador = db.execute(
        "SELECT * FROM actuadores WHERE id = ?", (actuador_id,)
    ).fetchone()

    if not actuador:
        raise HTTPException(status_code=404, detail="Actuador no encontrado")

    if accion == "toggle":
        nuevo_estado = "off" if actuador["estado"] == "on" else "on"
    elif accion in ("on", "off"):
        nuevo_estado = accion
    else:
        raise HTTPException(status_code=400, detail="Acción inválida")

    db.execute(
        "UPDATE actuadores SET estado = ?, ultimo_cambio = ? WHERE id = ?",
        (nuevo_estado, ahora, actuador_id)
    )
    return nuevo_estado


# ══ REGLAS ════════════════════════════════════════════════════════════════════

# ── GET /automatizaciones/reglas ───────────────────────────────────────────────

@router.get("/reglas")
def listar_reglas(db=Depends(get_db)):
    filas = db.execute("""
        SELECT r.*,
               s.nombre AS sensor_nombre,  s.tipo AS sensor_tipo,
               a.nombre AS actuador_nombre, a.tipo AS actuador_tipo
        FROM reglas r
        JOIN sensores   s ON r.sensor_id   = s.id
        JOIN actuadores a ON r.actuador_id = a.id
    """).fetchall()
    return [dict(f) for f in filas]


# ── POST /automatizaciones/reglas ──────────────────────────────────────────────

@router.post("/reglas")
def crear_regla(datos: NuevaRegla, db=Depends(get_db)):
    operadores_validos = (">", "<", "==", "!=")
    if datos.operador not in operadores_validos:
        raise HTTPException(status_code=400, detail=f"Operador inválido. Usa: {operadores_validos}")

    if datos.accion not in ("on", "off", "toggle"):
        raise HTTPException(status_code=400, detail="Acción inválida. Usa 'on', 'off' o 'toggle'")

    if not db.execute("SELECT id FROM sensores   WHERE id = ?", (datos.sensor_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Sensor no encontrado")

    if not db.execute("SELECT id FROM actuadores WHERE id = ?", (datos.actuador_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Actuador no encontrado")

    ahora = datetime.now().isoformat()
    cursor = db.execute("""
        INSERT INTO reglas (nombre, sensor_id, operador, umbral, actuador_id, accion, activa, fecha_creacion)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
    """, (datos.nombre, datos.sensor_id, datos.operador, datos.umbral, datos.actuador_id, datos.accion, ahora))
    db.commit()

    return db.execute("SELECT * FROM reglas WHERE id = ?", (cursor.lastrowid,)).fetchone()


# ── PATCH /automatizaciones/reglas/{id} ───────────────────────────────────────

@router.patch("/reglas/{id}")
def editar_regla(id: int, datos: EditarRegla, db=Depends(get_db)):
    if not db.execute("SELECT id FROM reglas WHERE id = ?", (id,)).fetchone():
        raise HTTPException(status_code=404, detail="Regla no encontrada")

    campos = {
        "nombre":   datos.nombre,
        "operador": datos.operador,
        "umbral":   datos.umbral,
        "accion":   datos.accion,
        "activa":   datos.activa
    }
    for campo, valor in campos.items():
        if valor is not None:
            db.execute(f"UPDATE reglas SET {campo} = ? WHERE id = ?", (valor, id))

    db.commit()
    return db.execute("SELECT * FROM reglas WHERE id = ?", (id,)).fetchone()


# ── DELETE /automatizaciones/reglas/{id} ──────────────────────────────────────

@router.delete("/reglas/{id}")
def eliminar_regla(id: int, db=Depends(get_db)):
    if not db.execute("SELECT id FROM reglas WHERE id = ?", (id,)).fetchone():
        raise HTTPException(status_code=404, detail="Regla no encontrada")

    db.execute("DELETE FROM reglas WHERE id = ?", (id,))
    db.commit()
    return { "detail": "Regla eliminada" }


# ══ ESCENAS ═══════════════════════════════════════════════════════════════════

# ── GET /automatizaciones/escenas ─────────────────────────────────────────────

@router.get("/escenas")
def listar_escenas(db=Depends(get_db)):
    filas = db.execute("""
        SELECT e.*,
               a.nombre AS actuador_nombre, a.tipo AS actuador_tipo
        FROM escenas e
        JOIN actuadores a ON e.actuador_id = a.id
    """).fetchall()
    return [dict(f) for f in filas]


# ── POST /automatizaciones/escenas ────────────────────────────────────────────

@router.post("/escenas")
def crear_escena(datos: NuevaEscena, db=Depends(get_db)):
    if datos.accion not in ("on", "off", "toggle"):
        raise HTTPException(status_code=400, detail="Acción inválida. Usa 'on', 'off' o 'toggle'")

    if not db.execute("SELECT id FROM actuadores WHERE id = ?", (datos.actuador_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Actuador no encontrado")

    ahora = datetime.now().isoformat()
    cursor = db.execute("""
        INSERT INTO escenas (nombre, disparador, actuador_id, accion, activa, fecha_creacion)
        VALUES (?, ?, ?, ?, 1, ?)
    """, (datos.nombre, datos.disparador, datos.actuador_id, datos.accion, ahora))
    db.commit()

    return db.execute("SELECT * FROM escenas WHERE id = ?", (cursor.lastrowid,)).fetchone()


# ── POST /automatizaciones/escenas/{id}/activar ───────────────────────────────

@router.post("/escenas/{id}/activar")
def activar_escena(id: int, db=Depends(get_db)):
    escena = db.execute("SELECT * FROM escenas WHERE id = ?", (id,)).fetchone()

    if not escena:
        raise HTTPException(status_code=404, detail="Escena no encontrada")

    ahora        = datetime.now().isoformat()
    nuevo_estado = ejecutar_accion(escena["actuador_id"], escena["accion"], ahora, db)
    db.commit()

    return {
        "escena":        escena["nombre"],
        "actuador_id":   escena["actuador_id"],
        "estado_nuevo":  nuevo_estado
    }


# ── PATCH /automatizaciones/escenas/{id} ──────────────────────────────────────

@router.patch("/escenas/{id}")
def editar_escena(id: int, datos: EditarEscena, db=Depends(get_db)):
    if not db.execute("SELECT id FROM escenas WHERE id = ?", (id,)).fetchone():
        raise HTTPException(status_code=404, detail="Escena no encontrada")

    campos = {
        "nombre":     datos.nombre,
        "disparador": datos.disparador,
        "accion":     datos.accion,
        "activa":     datos.activa
    }
    for campo, valor in campos.items():
        if valor is not None:
            db.execute(f"UPDATE escenas SET {campo} = ? WHERE id = ?", (valor, id))

    db.commit()
    return db.execute("SELECT * FROM escenas WHERE id = ?", (id,)).fetchone()


# ── DELETE /automatizaciones/escenas/{id} ─────────────────────────────────────

@router.delete("/escenas/{id}")
def eliminar_escena(id: int, db=Depends(get_db)):
    if not db.execute("SELECT id FROM escenas WHERE id = ?", (id,)).fetchone():
        raise HTTPException(status_code=404, detail="Escena no encontrada")

    db.execute("DELETE FROM escenas WHERE id = ?", (id,))
    db.commit()
    return { "detail": "Escena eliminada" }