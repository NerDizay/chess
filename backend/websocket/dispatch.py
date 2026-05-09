"""Диспетчеризация входящих WS-сообщений по `action`: реестр, декоратор `@api`, `execute_handler`."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from backend.services import GameService

from backend.auth.dependencies import JwtIdentity

HandlerFn = Callable[..., Awaitable[Any]]

_REGISTRY: dict[str, HandlerFn] = {}


@dataclass(frozen=True, slots=True)
class HandlerContext:
    connection_user: JwtIdentity | None
    game_service: GameService


class HandlerError(Exception):
    """Ошибка ответа WS: `detail` и опциональный HTTP-подобный `code` в теле `error`."""

    __slots__ = ("code", "detail")

    def __init__(self, detail: str, *, code: int | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code


def api(action: str) -> Callable[[HandlerFn], HandlerFn]:
    """Регистрирует хэндлер для строки `action` (как в Literal у входящей модели)."""

    def decorator(fn: HandlerFn | Callable[..., Any]) -> HandlerFn:
        if action in _REGISTRY:
            raise ValueError(f"duplicate api handler for action {action!r}")

        if inspect.iscoroutinefunction(fn):
            handler: HandlerFn = fn  # type: ignore[assignment]
        else:

            @functools.wraps(fn)
            async def handler(msg: Any, ctx: HandlerContext) -> Any:  # type: ignore[misc]
                return fn(msg, ctx)

        _REGISTRY[action] = handler
        return handler

    return decorator


async def execute_handler(
    msg: Any,
    connection_user: JwtIdentity | None,
    game_service: GameService,
) -> dict[str, Any]:
    """Вызывает зарегистрированный хэндлер по `msg.action`; собирает ответ запрос/ответ."""
    action = getattr(msg, "action", None)
    if not isinstance(action, str):
        mid = getattr(msg, "id", None)
        return {
            "id": mid,
            "ok": False,
            "error": {"detail": "invalid message: missing action"},
        }

    handler = _REGISTRY.get(action)
    if handler is None:
        mid = getattr(msg, "id", None)
        return {
            "id": mid,
            "ok": False,
            "error": {"detail": f"unknown action: {action}"},
        }

    ctx = HandlerContext(
        connection_user=connection_user,
        game_service=game_service,
    )
    mid = msg.id
    try:
        data = await handler(msg, ctx)
        return {"id": mid, "ok": True, "data": data}
    except HandlerError as e:
        err: dict[str, Any] = {"detail": e.detail}
        if e.code is not None:
            err["code"] = e.code
        return {"id": mid, "ok": False, "error": err}
