"""Через 2 минуты после потери всех WebSocket без переподключения — покинуть активную партию и уведомить соперника."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from backend.config.game_play import game_play_config
from backend.exceptions import GameForbiddenError, GameNotFoundError
from backend.services import GameService

from .registry import WsRegistry

_logger = logging.getLogger(__name__)

_tasks: dict[UUID, asyncio.Task[None]] = {}


def cancel_scheduled_abandon(user_id: UUID) -> None:
    t = _tasks.pop(user_id, None)
    if t is not None and not t.done():
        t.cancel()


def schedule_delayed_abandon_if_idle(
    user_id: UUID,
    game_service: GameService,
    ws_registry: WsRegistry,
) -> None:
    cancel_scheduled_abandon(user_id)

    async def runner() -> None:
        try:
            try:
                await asyncio.sleep(game_play_config.disconnect_abandon_delay_seconds)
            except asyncio.CancelledError:
                return
            if ws_registry.has_connections(user_id):
                return
            game = await game_service.find_active_pair_game_for_user(user_id)
            if game is None:
                return
            try:
                opponent_id = await game_service.abandon_game(game.id, user_id)
            except (GameNotFoundError, GameForbiddenError):
                return
            except Exception:
                _logger.exception("abandon_on_disconnect: abandon_game failed user_id=%s", user_id)
                return
            if opponent_id is not None:
                await ws_registry.send_json_to_user(
                    opponent_id,
                    {
                        "type": "push",
                        "event": "games.opponent_left",
                        "data": {"game_id": game.id},
                    },
                )
        finally:
            _tasks.pop(user_id, None)

    _tasks[user_id] = asyncio.create_task(runner())
