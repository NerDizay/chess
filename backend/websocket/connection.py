"""JSON по WebSocket: поле `id` в сообщениях — только склейка запрос/ответ, не идентификация пользователя."""

import json

from fastapi import WebSocket
from pydantic import ValidationError

from backend.auth.dependencies import JwtIdentity, jwt_identity_from_websocket
from backend.repositories import QueueWhoWantPlayRepository
from backend.services import GameService
from backend.websocket.abandon_on_disconnect import (
    cancel_scheduled_abandon,
    schedule_delayed_abandon_if_idle,
)
from backend.websocket.registry import WsRegistry

from . import endpoints  # noqa: F401 — регистрация @api
from .messages import parse_inbound, validation_error_payload
from .dispatch import execute_handler


async def run_api_websocket(
    websocket: WebSocket,
    game_service: GameService,
    queue_repo: QueueWhoWantPlayRepository,
    ws_registry: WsRegistry,
) -> None:
    await websocket.accept()
    # Cookie с JWT приходит один раз при handshake; для всего соединения один пользователь (или гость).
    connection_user: JwtIdentity | None = jwt_identity_from_websocket(websocket)
    if connection_user is not None:
        cancel_scheduled_abandon(connection_user.user_id)
        ws_registry.register(connection_user.user_id, websocket)
    try:
        await _run_ws_loop(
            websocket,
            connection_user,
            game_service,
            queue_repo,
            ws_registry,
        )
    finally:
        if connection_user is not None:
            ws_registry.unregister(connection_user.user_id, websocket)
            await queue_repo.remove(connection_user.user_id)
            if not ws_registry.has_connections(connection_user.user_id):
                schedule_delayed_abandon_if_idle(
                    connection_user.user_id,
                    game_service,
                    ws_registry,
                )


async def _run_ws_loop(
    websocket: WebSocket,
    connection_user: JwtIdentity | None,
    game_service: GameService,
    queue_repo: QueueWhoWantPlayRepository,
    ws_registry: WsRegistry,
) -> None:
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
        out = await execute_handler(
            inbound,
            connection_user,
            game_service,
            queue_repo,
            ws_registry,
        )
        await websocket.send_json(out)
