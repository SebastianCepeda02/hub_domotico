import sqlite3

def obtener_conexion():
    conexion = sqlite3.connect("/mnt/datos/hub_domotico/hub.db")
    conexion.row_factory = sqlite3.Row
    return conexion

def get_db():
    conexion = obtener_conexion()
    try:
        yield conexion
    finally:
        conexion.close()

def crear_tablas():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lecturas_dht11 (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ubicacion   TEXT    NOT NULL,
            temperatura REAL    NOT NULL,
            humedad     REAL    NOT NULL,
            fecha       TEXT    NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dispositivos (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            mac              TEXT    NOT NULL UNIQUE,
            ubicacion        TEXT    NOT NULL,
            fecha_registro   TEXT    NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS actuadores (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            dispositivo_id  INTEGER NOT NULL,
            tipo            TEXT    NOT NULL,
            pin             INTEGER NULL,
            estado          TEXT    NOT NULL,
            FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id)
        )
    """)
    conexion.commit()
    conexion.close()