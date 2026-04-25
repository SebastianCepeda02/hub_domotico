import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from routers.auth import verificar_token, COOKIE_NAME

router = APIRouter(prefix="/ws/camera", tags=["Cámara WebSocket"])


class GestorCamaras:
    def __init__(self):
        # device_id → WebSocket del ESP32-CAM
        self._publicadores: dict[int, WebSocket] = {}
        # device_id → set de WebSockets de navegadores
        self._espectadores: dict[int, set[WebSocket]] = {}

    async def conectar_publicador(self, device_id: int, ws: WebSocket):
        await ws.accept()
        self._publicadores[device_id] = ws
        self._espectadores.setdefault(device_id, set())

    async def conectar_espectador(self, device_id: int, ws: WebSocket):
        await ws.accept()
        self._espectadores.setdefault(device_id, set()).add(ws)

    def desconectar_publicador(self, device_id: int):
        self._publicadores.pop(device_id, None)

    def desconectar_espectador(self, device_id: int, ws: WebSocket):
        espectadores = self._espectadores.get(device_id)
        if espectadores:
            espectadores.discard(ws)

    def hay_espectadores(self, device_id: int) -> bool:
        return bool(self._espectadores.get(device_id))

    async def difundir_frame(self, device_id: int, frame: bytes):
        espectadores = self._espectadores.get(device_id, set())
        desconectados = set()
        for ws in espectadores:
            try:
                await ws.send_bytes(frame)
            except Exception:
                desconectados.add(ws)
        espectadores -= desconectados


gestor = GestorCamaras()


@router.websocket("/{device_id}/publish")
async def ws_publicar(
    device_id: int,
    websocket: WebSocket,
    api_key: str = Query(...)
):
    """ESP32-CAM se conecta aquí y envía frames JPEG como mensajes binarios."""
    if api_key != os.getenv("HUB_API_KEY", ""):
        await websocket.close(code=1008)
        return

    await gestor.conectar_publicador(device_id, websocket)
    try:
        while True:
            frame = await websocket.receive_bytes()
            if gestor.hay_espectadores(device_id):
                await gestor.difundir_frame(device_id, frame)
    except WebSocketDisconnect:
        gestor.desconectar_publicador(device_id)


@router.websocket("/{device_id}/view")
async def ws_ver(device_id: int, websocket: WebSocket):
    """Navegador se conecta aquí para recibir frames JPEG en tiempo real."""
    cookie = websocket.cookies.get(COOKIE_NAME)
    if not cookie or not verificar_token(cookie):
        await websocket.close(code=1008)
        return

    await gestor.conectar_espectador(device_id, websocket)
    try:
        while True:
            # Mantener conexión viva; el navegador no envía datos
            await websocket.receive_text()
    except WebSocketDisconnect:
        gestor.desconectar_espectador(device_id, websocket)
