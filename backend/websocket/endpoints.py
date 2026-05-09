"""Обработчики действий по WebSocket (`@api`). Импорт модуля регистрирует реестр."""

from __future__ import annotations

from typing import Any

from tortoise.exceptions import DoesNotExist

from backend.exceptions import UserNotFoundError

from .messages import AuthMeIn, GamesCreateIn, GamesGetIn, PingIn
from .dispatch import HandlerContext, HandlerError, api


@api("ping")
async def ping(_msg: PingIn, _ctx: HandlerContext) -> dict[str, Any]:
    return {"status": "ok"}


@api("auth.me")
async def auth_me(_msg: AuthMeIn, ctx: HandlerContext) -> dict[str, Any]:
    if ctx.connection_user is None:
        raise HandlerError("Not authenticated", code=401)
    return {
        "user_id": str(ctx.connection_user.user_id),
        "name": ctx.connection_user.name,
    }


@api("games.create")
async def games_create(_msg: GamesCreateIn, ctx: HandlerContext) -> dict[str, Any]:
    if ctx.connection_user is None:
        raise HandlerError("Not authenticated", code=401)
    try:
        return await ctx.game_service.create_game(ctx.connection_user.user_id)
    except UserNotFoundError as e:
        raise HandlerError(str(e), code=404) from e


@api("games.get")
async def games_get(msg: GamesGetIn, ctx: HandlerContext) -> dict[str, Any]:
    try:
        return await ctx.game_service.as_dict(msg.game_id)
    except DoesNotExist:
        raise HandlerError("Game not found", code=404)
