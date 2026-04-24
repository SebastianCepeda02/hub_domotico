import os
import jwt
from datetime import datetime, timedelta
from fastapi import APIRouter, Response, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/auth", tags=["Auth"])

SECRET_KEY   = os.getenv("SECRET_KEY",   "cambia_esto")
HUB_PASSWORD = os.getenv("HUB_PASSWORD", "admin")
COOKIE_NAME  = "hub_token"
TOKEN_TTL_H  = 24


# ── Modelos ───────────────────────────────────────────────────────────────────

class LoginData(BaseModel):
    password: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def generar_token() -> str:
    payload = {
        "sub": "admin",
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_TTL_H)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verificar_token(token: str) -> bool:
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return True
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post("/login")
def login(datos: LoginData, response: Response):
    if datos.password != HUB_PASSWORD:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    token = generar_token()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=TOKEN_TTL_H * 3600
    )
    return { "detail": "Login exitoso" }


# ── POST /auth/logout ─────────────────────────────────────────────────────────

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return { "detail": "Sesión cerrada" }


# ── GET /auth/verificar ───────────────────────────────────────────────────────

@router.get("/verificar")
def verificar(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token or not verificar_token(token):
        raise HTTPException(status_code=401, detail="No autenticado")
    return { "detail": "Autenticado" }