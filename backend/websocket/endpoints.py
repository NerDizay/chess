"""Обработчики действий по WebSocket (`@api`). Импорт модуля регистрирует реестр."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from tortoise.exceptions import DoesNotExist

from backend.exceptions import (
    GameForbiddenError,
    GameNotFoundError,
    InvalidMoveError,
    UserNotFoundError,
)
from backend.models import Game as GameModel

from .messages import (
    AuthMeIn,
    GamesAbandonIn,
    GamesActiveIn,
    GamesCreateIn,
    GamesGetIn,
    GamesLegalMovesIn,
    GamesMoveIn,
    GamesSyncIn,
    MatchmakingCancelIn,
    MatchmakingPlayIn,
    PingIn,
)
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


@api("games.active")
async def games_active_handler(_msg: GamesActiveIn, ctx: HandlerContext) -> dict[str, Any]:
    if ctx.connection_user is None:
        raise HandlerError("Not authenticated", code=401)
    game = await ctx.game_service.active_game_dict(ctx.connection_user.user_id)
    return {"game": game}


@api("games.sync")
async def games_sync_handler(msg: GamesSyncIn, ctx: HandlerContext) -> dict[str, Any]:
    if ctx.connection_user is None:
        raise HandlerError("Not authenticated", code=401)
    uid = ctx.connection_user.user_id
    try:
        return await ctx.game_service.sync_game(
            msg.game_id,
            uid,
            msg.client_version,
            msg.battle_field,
        )
    except GameNotFoundError as e:
        raise HandlerError(str(e), code=404) from e
    except GameForbiddenError as e:
        raise HandlerError(str(e), code=403) from e


@api("games.legal_moves")
async def games_legal_moves(msg: GamesLegalMovesIn, ctx: HandlerContext) -> dict[str, Any]:
    if ctx.connection_user is None:
        raise HandlerError("Not authenticated", code=401)
    uid = ctx.connection_user.user_id
    try:
        targets = await ctx.game_service.legal_moves(msg.game_id, uid, msg.from_cell)
    except GameNotFoundError as e:
        raise HandlerError(str(e), code=404) from e
    except GameForbiddenError as e:
        raise HandlerError(str(e), code=403) from e
    except InvalidMoveError as e:
        raise HandlerError(str(e), code=400) from e
    return {"targets": targets}


@api("matchmaking.play")
async def matchmaking_play(_msg: MatchmakingPlayIn, ctx: HandlerContext) -> dict[str, Any]:
    if ctx.connection_user is None:
        raise HandlerError("Not authenticated", code=401)
    uid = ctx.connection_user.user_id
    status, payload = await ctx.queue_repo.try_join_or_match(uid)
    if status == "matched":
        if not isinstance(payload, GameModel):
            raise HandlerError("internal matchmaking error")
        game = payload
        game_dict = await ctx.game_service.as_dict(game)
        white_id: UUID = game.white_user_id  # type: ignore[attr-defined]
        black_id: UUID = game.black_user_id  # type: ignore[attr-defined]
        opponent_id = black_id if uid == white_id else white_id
        await ctx.ws_registry.send_json_to_user(
            opponent_id,
            {
                "type": "push",
                "event": "matchmaking.matched",
                "data": {"game": game_dict},
            },
        )
        return {
            "status": "matched",
            "game": game_dict,
        }
    if not isinstance(payload, datetime):
        raise HandlerError("internal matchmaking error")
    created_at = payload
    return {
        "status": "waiting",
        "queued_at": created_at.isoformat(),
    }


@api("matchmaking.cancel")
async def matchmaking_cancel(_msg: MatchmakingCancelIn, ctx: HandlerContext) -> dict[str, Any]:
    if ctx.connection_user is None:
        raise HandlerError("Not authenticated", code=401)
    await ctx.queue_repo.remove(ctx.connection_user.user_id)
    return {"status": "cancelled"}


@api("games.move")
async def games_move(msg: GamesMoveIn, ctx: HandlerContext) -> dict[str, Any]:
    if ctx.connection_user is None:
        raise HandlerError("Not authenticated", code=401)
    uid = ctx.connection_user.user_id
    try:
        game_dict = await ctx.game_service.play_move(
            msg.game_id,
            uid,
            msg.from_cell,
            msg.to_cell,
        )
    except GameNotFoundError as e:
        raise HandlerError(str(e), code=404) from e
    except GameForbiddenError as e:
        raise HandlerError(str(e), code=403) from e
    except InvalidMoveError as e:
        raise HandlerError(str(e), code=400) from e

    wu = game_dict.get("white_user")
    bu = game_dict.get("black_user")
    if isinstance(wu, dict) and isinstance(bu, dict):
        wid = wu.get("id")
        bid = bu.get("id")
        if wid and bid:
            opp_id = UUID(bid) if str(uid) == str(wid) else UUID(str(wid))
            if opp_id != uid:
                await ctx.ws_registry.send_json_to_user(
                    opp_id,
                    {
                        "type": "push",
                        "event": "games.updated",
                        "data": {"game": game_dict},
                    },
                )
    return {"game": game_dict}


@api("games.abandon")
async def games_abandon(msg: GamesAbandonIn, ctx: HandlerContext) -> dict[str, Any]:
    if ctx.connection_user is None:
        raise HandlerError("Not authenticated", code=401)
    try:
        opponent_id = await ctx.game_service.abandon_game(msg.game_id, ctx.connection_user.user_id)
    except GameNotFoundError as e:
        raise HandlerError(str(e), code=404) from e
    except GameForbiddenError as e:
        raise HandlerError(str(e), code=403) from e
    if opponent_id is not None:
        await ctx.ws_registry.send_json_to_user(
            opponent_id,
            {
                "type": "push",
                "event": "games.opponent_left",
                "data": {"game_id": msg.game_id},
            },
        )
    return {"status": "abandoned"}
