
"""from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from database import init_db
from routers import sensores, dispositivos, actuadores, sistema, ui, vincular, automatizaciones, dashboard

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

app.include_router(sensores.router)
app.include_router(dispositivos.router)
app.include_router(actuadores.router)
app.include_router(sistema.router)
app.include_router(vincular.router)
app.include_router(automatizaciones.router)
app.include_router(dashboard.router)
app.include_router(ui.router)
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.responses import RedirectResponse
from routers.auth import verificar_token, COOKIE_NAME

from database import init_db, obtener_conexion
from dependencies import verificar_api_key

from routers.vincular        import router as vincular_router
from routers.dispositivos    import router as dispositivos_router
from routers.sensores        import router as sensores_router
from routers.actuadores      import router as actuadores_router
from routers.automatizaciones import router as automatizaciones_router
from routers.dashboard       import router as dashboard_router
from routers.sistema         import router as sistema_router
from routers.auth import router as auth_router
from starlette.datastructures import Headers
import os

# ── Cron job de escenas ───────────────────────────────────────────────────────

async def evaluar_escenas_por_hora():
    while True:
        try:
            ahora_hora = datetime.now().strftime("%H:%M")
            db         = obtener_conexion()

            escenas = db.execute("""
                SELECT * FROM escenas
                WHERE activa = 1 AND disparador = ?
            """, (ahora_hora,)).fetchall()

            for escena in escenas:
                actuador = db.execute(
                    "SELECT * FROM actuadores WHERE id = ?", (escena["actuador_id"],)
                ).fetchone()

                if actuador:
                    if escena["accion"] == "toggle":
                        nuevo_estado = "off" if actuador["estado"] == "on" else "on"
                    elif escena["accion"] in ("on", "off"):
                        nuevo_estado = escena["accion"]
                    else:
                        continue

                    db.execute(
                        "UPDATE actuadores SET estado = ?, ultimo_cambio = ? WHERE id = ?",
                        (nuevo_estado, datetime.now().isoformat(), escena["actuador_id"])
                    )

            db.commit()
            db.close()

        except Exception as e:
            print(f"[cron] Error evaluando escenas: {e}")

        await asyncio.sleep(60)  # revisa cada minuto


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    tarea = asyncio.create_task(evaluar_escenas_por_hora())
    yield
    tarea.cancel()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Hub Domótico",
    version="2.0.0",
    lifespan=lifespan
)

app.mount("/app", StaticFiles(directory="/mnt/mi_usb/hub_domotico/frontend", html=True), name="frontend")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción cambia por tu dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # rutas que no requieren autenticación
    rutas_publicas = [
        "/auth/login",
        "/auth/logout",
        "/app/login.html",
        "/app/css/",
        "/app/js/",
    ]

    path = request.url.path

    # si es una ruta pública dejar pasar
    if any(path.startswith(r) for r in rutas_publicas):
        return await call_next(request)

    # si es una ruta de /app verificar cookie
    if path.startswith("/app"):
        token = request.cookies.get(COOKIE_NAME)
        if not token or not verificar_token(token):
            return RedirectResponse(url="/app/login.html")

    return await call_next(request)

###############################################################################################3
@app.middleware("http")
async def inyectar_api_key(request: Request, call_next):
    rutas_frontend = [
        "/dashboard/",
        "/sistema/",
        "/actuadores/",
        "/dispositivos/",
        "/sensores/",
        "/automatizaciones/",
        "/vincular/codigo",
        "/auth/",
    ]

    path = request.url.path

    # solo inyectar si viene del frontend (tiene cookie válida) y no trae key
    tiene_key    = request.headers.get("x-api-key")
    tiene_cookie = request.cookies.get(COOKIE_NAME)

    if not tiene_key and tiene_cookie and any(path.startswith(r) for r in rutas_frontend):
        from routers.auth import verificar_token
        if verificar_token(tiene_cookie):
            headers_dict = dict(request.headers)
            headers_dict["x-api-key"] = os.getenv("HUB_API_KEY", "")
            scope          = request.scope
            scope["headers"] = [
                (k.lower().encode(), v.encode())
                for k, v in headers_dict.items()
            ]
            request = Request(scope, request.receive)

    return await call_next(request)
######################################################################################3
# ── Manejador global de errores ───────────────────────────────────────────────

@app.exception_handler(Exception)
async def manejador_global(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={ "detail": f"Error interno: {str(exc)}" }
    )


# ── Dependencia global de API Key ─────────────────────────────────────────────

app.include_router(vincular_router)  # vinculación sin API key — es pública
app.include_router(auth_router)
app.include_router(sistema_router,    dependencies=[Depends(verificar_api_key)])
app.include_router(actuadores_router,    dependencies=[Depends(verificar_api_key)])
app.include_router(dashboard_router,    dependencies=[Depends(verificar_api_key)])
app.include_router(dispositivos_router,    dependencies=[Depends(verificar_api_key)])
app.include_router(sensores_router,        dependencies=[Depends(verificar_api_key)])
app.include_router(automatizaciones_router, dependencies=[Depends(verificar_api_key)])



# ── Raíz ──────────────────────────────────────────────────────────────────────

@app.get("/")
def raiz():
    return {
        "proyecto": "Hub Domótico",
        "version":  "2.0.0",
        "estado":   "online"
    }


#cd /mnt/datos/hub_domotico
#source entorno_domotico/bin/activate
# python3 main.py
# uvicorn main:app --reload
#uvicorn main:app --host 0.0.0.0 --port 8000 --reload

#cloudflared tunnel --url http://localhost:8000


#cloudflared tunnel run --token eyJhIjoiMWE4MWQwODdmY2Q0MmQwODlmZTViMjYxZDIxZjVjODAiLCJ0IjoiYWY3MzUyM2YtNTE3Yy00ZTM0LTk4Y2EtMWEyZDUxNTkxY2MyIiwicyI6Ik5qZGtObUkwTUdVdE9HTXhNUzAwWWpaa0xUZzVNV0l0WWpNME56SmhZVEV5T0RReSJ9

#nohup uvicorn main:app --host 0.0.0.0 --port 8000 &

#sudo fuser -k 8000/tcp
#pkill -f uvicorn



#############################

#sudo nano /etc/systemd/system/hubdomotico.service
#sudo systemctl daemon-reload
#sudo systemctl enable hubdomotico
#sudo systemctl start hubdomotico
#sudo systemctl status hubdomotico