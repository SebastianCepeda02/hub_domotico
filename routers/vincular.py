import random
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import get_db

router = APIRouter(prefix="/vincular", tags=["Vinculación"])


# ── Modelos ────────────────────────────────────────────────────────────────────

class SensorRegistro(BaseModel):
    tipo:   str
    unidad: str

class ActuadorRegistro(BaseModel):
    tipo: str
    pin:  int

class RegistroDispositivo(BaseModel):
    mac:        str
    codigo:     str
    sensores:   list[SensorRegistro]
    actuadores: list[ActuadorRegistro]


# ── POST /vincular/codigo ──────────────────────────────────────────────────────

@router.post("/codigo")
def generar_codigo(db=Depends(get_db)):
    codigo    = str(random.randint(100000, 999999))
    expira_en = (datetime.now() + timedelta(minutes=5)).isoformat()

    db.execute(
        "INSERT INTO codigos_vinculacion (codigo, expira_en, usado) VALUES (?, ?, 0)",
        (codigo, expira_en)
    )
    db.commit()

    return { "codigo": codigo, "expira_en": expira_en }


# ── POST /vincular/registrar ───────────────────────────────────────────────────

@router.post("/registrar")
def registrar_dispositivo(datos: RegistroDispositivo, db=Depends(get_db)):

    # 1 — Validar código
    fila = db.execute(
        "SELECT * FROM codigos_vinculacion WHERE codigo = ? AND usado = 0",
        (datos.codigo,)
    ).fetchone()

    if not fila:
        raise HTTPException(status_code=400, detail="Código inválido o ya utilizado")

    if datetime.fromisoformat(fila["expira_en"]) < datetime.now():
        raise HTTPException(status_code=400, detail="Código expirado")

    # 2 — Marcar código como usado
    db.execute(
        "UPDATE codigos_vinculacion SET usado = 1 WHERE codigo = ?",
        (datos.codigo,)
    )

    # 3 — Crear o actualizar dispositivo
    ahora = datetime.now().isoformat()

    existente = db.execute(
        "SELECT id FROM dispositivos WHERE mac = ?",
        (datos.mac,)
    ).fetchone()

    if existente:
        dispositivo_id = existente["id"]
        db.execute(
            "UPDATE dispositivos SET ultimo_contacto = ? WHERE id = ?",
            (ahora, dispositivo_id)
        )
    else:
        cursor = db.execute(
            "INSERT INTO dispositivos (mac, ultimo_contacto, fecha_registro) VALUES (?, ?, ?)",
            (datos.mac, ahora, ahora)
        )
        dispositivo_id = cursor.lastrowid

    # 4 — Crear sensores
    sensores_creados = []
    for s in datos.sensores:
        cursor = db.execute(
            "INSERT INTO sensores (dispositivo_id, tipo, unidad) VALUES (?, ?, ?)",
            (dispositivo_id, s.tipo, s.unidad)
        )
        sensores_creados.append({ "tipo": s.tipo, "id": cursor.lastrowid })

    # 5 — Crear actuadores
    actuadores_creados = []
    for a in datos.actuadores:
        cursor = db.execute(
            "INSERT INTO actuadores (dispositivo_id, tipo, pin, estado) VALUES (?, ?, ?, 'off')",
            (dispositivo_id, a.tipo, a.pin)
        )
        actuadores_creados.append({ "tipo": a.tipo, "pin": a.pin, "id": cursor.lastrowid })

    db.commit()

    return {
        "dispositivo_id": dispositivo_id,
        "sensores":       sensores_creados,
        "actuadores":     actuadores_creados
    }