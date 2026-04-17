from pydantic import BaseModel

class LecturaDHT11(BaseModel):
    ubicacion: str
    temperatura: float
    humedad: float