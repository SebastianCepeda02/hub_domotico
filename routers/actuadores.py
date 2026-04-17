from fastapi import APIRouter, Depends, HTTPException, Security
import sqlite3
from database import get_db
from dependencies import verificar_api_key
from models.actuadores import ActuadorCreate, ActuadorEstado

router = APIRouter(prefix="/actuadores", tags=["actuadores"])

@router.post("")
def crear_actuador(actuador: ActuadorCreate, conexion = Depends(get_db), key = Security(verificar_api_key)):
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT id FROM dispositivos WHERE id = ?", (actuador.dispositivo_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
        cursor.execute("""
            INSERT INTO actuadores (dispositivo_id, tipo, pin, estado)
            VALUES (?, ?, ?, ?)
        """, (actuador.dispositivo_id, actuador.tipo, actuador.pin, actuador.estado))
        conexion.commit()
        return {"mensaje": "Actuador registrado", "id": cursor.lastrowid}
    except sqlite3.Error as e:
        conexion.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear: {str(e)}")

@router.get("/{dispositivo_id}")
def obtener_actuadores(dispositivo_id: int, conexion = Depends(get_db), key = Security(verificar_api_key)):
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT id FROM dispositivos WHERE id = ?", (dispositivo_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
        cursor.execute("SELECT * FROM actuadores WHERE dispositivo_id = ?", (dispositivo_id,))
        actuadores = cursor.fetchall()
        return {"actuadores": [dict(a) for a in actuadores]}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar: {str(e)}")

@router.put("/{id}/estado")
def actualizar_estado(id: int, datos: ActuadorEstado, conexion = Depends(get_db), key = Security(verificar_api_key)):
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT id FROM actuadores WHERE id = ?", (id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Actuador no encontrado")
        cursor.execute("UPDATE actuadores SET estado = ? WHERE id = ?", (datos.estado, id))
        conexion.commit()
        return {"mensaje": "Estado actualizado", "id": id, "estado": datos.estado}
    except sqlite3.Error as e:
        conexion.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar: {str(e)}")