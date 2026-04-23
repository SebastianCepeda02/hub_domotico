import sqlite3

DB_PATH = "/mnt/mi_usb/hub_domotico/hub.db"

def obtener_conexion():
    conexion = sqlite3.connect(DB_PATH, check_same_thread=False)
    conexion.row_factory = sqlite3.Row
    return conexion

def get_db():
    conexion = obtener_conexion()
    try:
        yield conexion
    finally:
        conexion.close()

def init_db():
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dispositivos (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            mac              TEXT    NOT NULL UNIQUE,
            nombre           TEXT,
            ubicacion        TEXT,
            ultimo_contacto  TEXT,
            fecha_registro   TEXT    NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensores (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            dispositivo_id INTEGER NOT NULL,
            tipo           TEXT    NOT NULL,
            nombre         TEXT,
            unidad         TEXT,
            FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS actuadores (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            dispositivo_id INTEGER NOT NULL,
            tipo           TEXT    NOT NULL,
            nombre         TEXT,
            pin            INTEGER,
            estado         TEXT    NOT NULL DEFAULT 'off',
            ultimo_cambio  TEXT,
            FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lecturas (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id INTEGER NOT NULL,
            valor     REAL    NOT NULL,
            fecha     TEXT    NOT NULL,
            FOREIGN KEY (sensor_id) REFERENCES sensores(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS codigos_vinculacion (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo    TEXT    NOT NULL UNIQUE,
            expira_en TEXT    NOT NULL,
            usado     INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reglas (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre         TEXT    NOT NULL,
            activa         INTEGER NOT NULL DEFAULT 1,
            sensor_id      INTEGER NOT NULL,
            operador       TEXT    NOT NULL,
            umbral         REAL    NOT NULL,
            actuador_id    INTEGER NOT NULL,
            accion         TEXT    NOT NULL,
            fecha_creacion TEXT    NOT NULL,
            FOREIGN KEY (sensor_id)   REFERENCES sensores(id),
            FOREIGN KEY (actuador_id) REFERENCES actuadores(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS escenas (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre         TEXT    NOT NULL,
            activa         INTEGER NOT NULL DEFAULT 1,
            disparador     TEXT    NOT NULL,
            actuador_id    INTEGER NOT NULL,
            accion         TEXT    NOT NULL,
            fecha_creacion TEXT    NOT NULL,
            FOREIGN KEY (actuador_id) REFERENCES actuadores(id)
        )
    """)

    conexion.commit()
    conexion.close()