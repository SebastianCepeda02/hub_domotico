import json
import os
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from database import obtener_conexion

router = APIRouter(prefix="/ws", tags=["WebSocket Dispositivos"])

# device_id → WebSocket activo
_dispositivos_ws: dict[int, WebSocket] = {}


async def notificar_estado_actuador(actuador_id: int, estado: str):
    """Envía el nuevo estado de un actuador al dispositivo ESP32 conectado por WS."""
    db = obtener_conexion()
    fila = db.execute(
        "SELECT dispositivo_id FROM actuadores WHERE id = ?", (actuador_id,)
    ).fetchone()
    db.close()
    if not fila:
        return
    ws = _dispositivos_ws.get(fila["dispositivo_id"])
    if ws:
        try:
            await ws.send_text(json.dumps({
                "actuadores": [{"actuador_id": actuador_id, "estado": estado}]
            }))
        except Exception:
            _dispositivos_ws.pop(fila["dispositivo_id"], None)


@router.websocket("/dispositivo/{device_id}/datos")
async def ws_dispositivo(
    device_id: int,
    websocket: WebSocket,
    api_key: str = Query(...)
):
    if api_key != os.getenv("HUB_API_KEY", ""):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    _dispositivos_ws[device_id] = websocket

    # Enviar estado actual de todos los actuadores del dispositivo
    db = obtener_conexion()
    actuadores = db.execute(
        "SELECT id, estado FROM actuadores WHERE dispositivo_id = ?", (device_id,)
    ).fetchall()
    ahora = datetime.now().isoformat()
    db.execute(
        "UPDATE dispositivos SET ultimo_contacto = ? WHERE id = ?", (ahora, device_id)
    )
    db.commit()
    db.close()

    if actuadores:
        await websocket.send_text(json.dumps({
            "actuadores": [{"actuador_id": a["id"], "estado": a["estado"]} for a in actuadores]
        }))

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            ahora = datetime.now().isoformat()

            db = obtener_conexion()
            db.execute(
                "UPDATE dispositivos SET ultimo_contacto = ? WHERE id = ?", (ahora, device_id)
            )

            if "lecturas" in payload:
                actuadores_cambiados = []

                for lectura in payload["lecturas"]:
                    sensor_id = int(lectura["sensor_id"])
                    valor = float(lectura["valor"])

                    sensor = db.execute(
                        "SELECT * FROM sensores WHERE id = ? AND dispositivo_id = ?",
                        (sensor_id, device_id)
                    ).fetchone()
                    if not sensor:
                        continue

                    db.execute(
                        "INSERT INTO lecturas (sensor_id, valor, fecha) VALUES (?, ?, ?)",
                        (sensor_id, valor, ahora)
                    )

                    reglas = db.execute(
                        "SELECT * FROM reglas WHERE sensor_id = ? AND activa = 1", (sensor_id,)
                    ).fetchall()
                    for regla in reglas:
                        op, umbral = regla["operador"], regla["umbral"]
                        cumple = (
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
                            actuadores_cambiados.append({
                                "actuador_id": regla["actuador_id"],
                                "estado": regla["accion"]
                            })

                db.commit()
                db.close()

                for cambio in actuadores_cambiados:
                    await notificar_estado_actuador(cambio["actuador_id"], cambio["estado"])
            else:
                db.commit()
                db.close()

    except WebSocketDisconnect:
        _dispositivos_ws.pop(device_id, None)
    except Exception as e:
        print(f"[WS dispositivo {device_id}] Error: {e}")
        _dispositivos_ws.pop(device_id, None)
