from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from database import crear_tablas
from routers import sensores, dispositivos, actuadores, sistema, ui


app = FastAPI(title="Hub Domótico")

crear_tablas()

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

app.include_router(sensores.router)
app.include_router(dispositivos.router)
app.include_router(actuadores.router)
app.include_router(sistema.router)
app.include_router(ui.router)

@app.exception_handler(Exception)
async def manejador_global(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Error interno del servidor", "detalle": str(exc)}
    )

@app.get("/")
def inicio():
    return FileResponse("frontend/index.html")





#cd /mnt/datos/hub_domotico
#source entorno_domotico/bin/activate
# python3 main.py
# uvicorn main:app --reload
#uvicorn main:app --host 0.0.0.0 --port 8000 --reload