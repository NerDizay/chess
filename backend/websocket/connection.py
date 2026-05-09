"""JSON по WebSocket: поле `id` в сообщениях — только склейка запрос/ответ, не идентификация пользователя."""

import json

from fastapi import WebSocket
from pydantic import ValidationError

from backend.auth.dependencies import JwtIdentity, jwt_identity_from_websocket
from backend.services import GameService

from . import endpoints  # noqa: F401 — регистрация @api
from .messages import parse_inbound, validation_error_payload
from .dispatch import execute_handler


async def run_api_websocket(websocket: WebSocket, game_service: GameService) -> None:
    await websocket.accept()
    # Cookie с JWT приходит один раз при handshake; для всего соединения один пользователь (или гость).
    connection_user: JwtIdentity | None = jwt_identity_from_websocket(websocket)
    # iter_text() внутри тоже ждёт I/O (await); это не busy-loop и не грузит CPU.
    async for text in websocket.iter_text():
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            await websocket.send_json(
                {"id": None, "ok": False, "error": {"detail": "invalid json"}},
            )
            continue
        if not isinstance(raw, dict):
            await websocket.send_json(
                {
                    "id": None,
                    "ok": False,
                    "error": {"detail": "expected a JSON object"},
                },
            )
            continue
        try:
            inbound = parse_inbound(raw)
        except ValidationError as e:
            await websocket.send_json(validation_error_payload(raw, e))
            continue
        out = await execute_handler(inbound, connection_user, game_service)
        await websocket.send_json(out)
