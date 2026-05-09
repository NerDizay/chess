from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import HTTPException, Request
from starlette.websockets import WebSocket

from .config import get_settings
from .jwt_tokens import decode_access_token


@dataclass(frozen=True)
class JwtIdentity:
    user_id: UUID
    name: str


async def require_jwt_identity(request: Request) -> JwtIdentity:
    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    ident = jwt_identity_from_cookie(token)
    if ident is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return ident


def jwt_identity_from_cookie(token: str | None) -> JwtIdentity | None:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
        name = str(payload["name"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    return JwtIdentity(user_id=user_id, name=name)


async def optional_jwt_identity(request: Request) -> JwtIdentity | None:
    settings = get_settings()
    return jwt_identity_from_cookie(request.cookies.get(settings.cookie_name))


def jwt_identity_from_websocket(websocket: WebSocket) -> JwtIdentity | None:
    settings = get_settings()
    return jwt_identity_from_cookie(websocket.cookies.get(settings.cookie_name))
