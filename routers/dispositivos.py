from fastapi import APIRouter, Depends, HTTPException, Security
import sqlite3
from datetime import datetime
from database import get_db
from dependencies import verificar_api_key
from models.actuadores import DispositivoRegistro

router = APIRouter(prefix="/dispositivos", tags=["dispositivos"])

@router.post("/registro")
def registrar_dispositivo(dispositivo: DispositivoRegistro, conexion = Depends(get_db), key = Security(verificar_api_key)):
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT id FROM dispositivos WHERE mac = ?", (dispositivo.mac,))
        existente = cursor.fetchone()
        if existente:
            cursor.execute("DELETE FROM actuadores WHERE dispositivo_id = ?", (existente["id"],))
            conexion.commit()
            return {"mensaje": "Dispositivo ya registrado, actuadores reiniciados", "dispositivo_id": existente["id"]}
        else:
            cursor.execute("""
                INSERT INTO dispositivos (mac, ubicacion, fecha_registro)
                VALUES (?, ?, ?)
            """, (dispositivo.mac, dispositivo.ubicacion, datetime.now().isoformat()))
            conexion.commit()
            return {"mensaje": "Dispositivo registrado", "dispositivo_id": cursor.lastrowid}
    except sqlite3.Error as e:
        conexion.rollback()
        raise HTTPException(status_code=500, detail=f"Error al registrar: {str(e)}")