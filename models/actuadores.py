from pydantic import BaseModel
from typing import Optional

class ActuadorCreate(BaseModel):
    dispositivo_id: int
    tipo: str
    estado: str
    pin: Optional[int] = None

class ActuadorEstado(BaseModel):
    estado: str

class DispositivoRegistro(BaseModel):
    mac: str
    ubicacion: str