from fastapi import APIRouter, Depends, HTTPException, Query, Security
import sqlite3
from datetime import datetime
from database import get_db
from dependencies import verificar_api_key
from models.sensores import LecturaDHT11

router = APIRouter(prefix="/sensores", tags=["sensores"])

@router.post("/dht11")
def recibir_lectura(lectura: LecturaDHT11, conexion = Depends(get_db), key = Security(verificar_api_key)):
    try:
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO lecturas_dht11 (ubicacion, temperatura, humedad, fecha)
            VALUES (?, ?, ?, ?)
        """, (lectura.ubicacion, lectura.temperatura, lectura.humedad, datetime.now().isoformat()))
        conexion.commit()
        return {"mensaje": "Lectura guardada", "datos": lectura}
    except sqlite3.Error as e:
        conexion.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar: {str(e)}")

@router.get("/dht11/filtrar")
def filtrar_lecturas(
    ubicacion: str = Query(default=None),
    limite: int = Query(default=None),
    conexion = Depends(get_db),
    key = Security(verificar_api_key)
):
    try:
        cursor = conexion.cursor()
        if ubicacion and limite:
            cursor.execute("SELECT * FROM lecturas_dht11 WHERE ubicacion = ? LIMIT ?", (ubicacion, limite))
        elif ubicacion:
            cursor.execute("SELECT * FROM lecturas_dht11 WHERE ubicacion = ?", (ubicacion,))
        elif limite:
            cursor.execute("SELECT * FROM lecturas_dht11 LIMIT ?", (limite,))
        else:
            cursor.execute("SELECT * FROM lecturas_dht11")
        lecturas = cursor.fetchall()
        return {"lecturas": [dict(lectura) for lectura in lecturas]}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar: {str(e)}")

@router.get("/dht11/filtrar")
def filtrar_lecturas(
    ubicacion: str = Query(default=None),
    limite: int = Query(default=None),
    conexion = Depends(get_db),
    key = Security(verificar_api_key)
):
    try:
        cursor = conexion.cursor()
        if ubicacion and limite:
            cursor.execute("SELECT * FROM lecturas_dht11 WHERE ubicacion = ? LIMIT ?", (ubicacion, limite))
        elif ubicacion:
            cursor.execute("SELECT * FROM lecturas_dht11 WHERE ubicacion = ?", (ubicacion,))
        elif limite:
            cursor.execute("SELECT * FROM lecturas_dht11 LIMIT ?", (limite,))
        else:
            cursor.execute("SELECT * FROM lecturas_dht11")
        lecturas = cursor.fetchall()
        return {"lecturas": [dict(lectura) for lectura in lecturas]}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar: {str(e)}")

@router.get("/dht11/{id}")
def obtener_lectura(id: int, conexion = Depends(get_db), key = Security(verificar_api_key)):
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM lecturas_dht11 WHERE id = ?", (id,))
        lectura = cursor.fetchone()
        if lectura is None:
            raise HTTPException(status_code=404, detail="Lectura no encontrada")
        return {"lectura": dict(lectura)}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar: {str(e)}")