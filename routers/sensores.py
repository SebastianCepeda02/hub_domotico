from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import get_db

router = APIRouter(prefix="/sensores", tags=["Sensores"])


# ── Modelos ────────────────────────────────────────────────────────────────────

class EditarSensor(BaseModel):
    nombre: str

class NuevaLectura(BaseModel):
    valor: float


# ── GET /sensores ──────────────────────────────────────────────────────────────

@router.get("/")
def listar_sensores(db=Depends(get_db)):
    filas = db.execute("""
        SELECT s.*, d.ubicacion, d.nombre AS dispositivo_nombre
        FROM sensores s
        JOIN dispositivos d ON s.dispositivo_id = d.id
    """).fetchall()
    return [dict(f) for f in filas]


# ── GET /sensores/{id} ─────────────────────────────────────────────────────────

@router.get("/{id}")
def detalle_sensor(id: int, db=Depends(get_db)):
    sensor = db.execute("SELECT * FROM sensores WHERE id = ?", (id,)).fetchone()

    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor no encontrado")

    ultima = db.execute("""
        SELECT valor, fecha FROM lecturas
        WHERE sensor_id = ?
        ORDER BY id DESC LIMIT 1
    """, (id,)).fetchone()

    return {
        **dict(sensor),
        "ultima_lectura": dict(ultima) if ultima else None
    }


# ── PATCH /sensores/{id} ───────────────────────────────────────────────────────

@router.patch("/{id}")
def editar_sensor(id: int, datos: EditarSensor, db=Depends(get_db)):
    sensor = db.execute("SELECT id FROM sensores WHERE id = ?", (id,)).fetchone()

    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor no encontrado")

    db.execute("UPDATE sensores SET nombre = ? WHERE id = ?", (datos.nombre, id))
    db.commit()
    return db.execute("SELECT * FROM sensores WHERE id = ?", (id,)).fetchone()

@router.patch("/{id}/favorito")
def toggle_favorito(id: int, db=Depends(get_db)):
    tabla = "sensores"  # cambia por "actuadores" en actuadores.py
    fila  = db.execute(f"SELECT favorito FROM {tabla} WHERE id = ?", (id,)).fetchone()
    if not fila:
        raise HTTPException(status_code=404, detail="No encontrado")
    nuevo = 0 if fila["favorito"] else 1
    db.execute(f"UPDATE {tabla} SET favorito = ? WHERE id = ?", (nuevo, id))
    db.commit()
    return { "id": id, "favorito": bool(nuevo) }
    
# ── GET /sensores/{id}/lecturas ────────────────────────────────────────────────

@router.get("/{id}/lecturas")
def historial_lecturas(id: int, limite: int = 50, db=Depends(get_db)):
    sensor = db.execute("SELECT id FROM sensores WHERE id = ?", (id,)).fetchone()

    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor no encontrado")

    filas = db.execute("""
        SELECT * FROM lecturas
        WHERE sensor_id = ?
        ORDER BY id DESC LIMIT ?
    """, (id, limite)).fetchall()

    return [dict(f) for f in filas]


# ── POST /sensores/{id}/lecturas ───────────────────────────────────────────────

@router.post("/{id}/lecturas")
def nueva_lectura(id: int, datos: NuevaLectura, db=Depends(get_db)):
    sensor = db.execute("SELECT * FROM sensores WHERE id = ?", (id,)).fetchone()

    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor no encontrado")

    ahora = datetime.now().isoformat()

    # Guardar lectura
    db.execute(
        "INSERT INTO lecturas (sensor_id, valor, fecha) VALUES (?, ?, ?)",
        (id, datos.valor, ahora)
    )

    # Actualizar ultimo_contacto del dispositivo
    db.execute(
        "UPDATE dispositivos SET ultimo_contacto = ? WHERE id = ?",
        (ahora, sensor["dispositivo_id"])
    )

    # Evaluar reglas activas para este sensor
    reglas = db.execute("""
        SELECT * FROM reglas
        WHERE sensor_id = ? AND activa = 1
    """, (id,)).fetchall()

    reglas_disparadas = []
    for regla in reglas:
        op      = regla["operador"]
        umbral  = regla["umbral"]
        valor   = datos.valor
        cumple  = (
            (op == ">"  and valor >  umbral) or
            (op == "<"  and valor <  umbral) or
            (op == "==" and valor == umbral) or
            (op == "!=" and valor != umbral)
        )
        if cumple:
            db.execute(
                "UPDATE actuadores SET estado = ?, ultimo_cambio = ? WHERE id = ?",
                (regla["accion"], ahora, regla["actuador_id"])
            )
            reglas_disparadas.append(regla["nombre"])

    db.commit()

    return {
        "sensor_id":        id,
        "valor":            datos.valor,
        "fecha":            ahora,
        "reglas_disparadas": reglas_disparadas
    }