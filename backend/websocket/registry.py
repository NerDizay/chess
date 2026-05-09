"""Реестр WebSocket по user_id для push-сообщений (подбор соперника, отмена партии)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from starlette.websockets import WebSocket


class WsRegistry:
    def __init__(self) -> None:
        self._by_user: dict[UUID, list[WebSocket]] = defaultdict(list)

    def register(self, user_id: UUID, ws: WebSocket) -> None:
        self._by_user[user_id].append(ws)

    def unregister(self, user_id: UUID, ws: WebSocket) -> None:
        conns = self._by_user.get(user_id)
        if not conns:
            return
        try:
            conns.remove(ws)
        except ValueError:
            return
        if not conns:
            del self._by_user[user_id]

    def has_connections(self, user_id: UUID) -> bool:
        return bool(self._by_user.get(user_id))

    async def send_json_to_user(self, user_id: UUID, payload: dict[str, Any]) -> None:
        for ws in list(self._by_user.get(user_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                continue


ws_registry = WsRegistry()
