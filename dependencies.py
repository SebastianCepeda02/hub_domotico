from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.environ.get("HUB_API_KEY")

if not API_KEY:
    raise RuntimeError("HUB_API_KEY no está definida en el archivo .env")

api_key_header = APIKeyHeader(name="X-API-Key")

def verificar_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="API Key inválida")
    return key