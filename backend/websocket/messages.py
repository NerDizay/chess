"""Схемы входящих сообщений WebSocket API (discriminated union по `action`)."""

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

__all__ = [
    "PingIn",
    "AuthMeIn",
    "GamesCreateIn",
    "GamesGetIn",
    "Msg",
    "Inbound",
    "parse_inbound",
    "validation_error_payload",
]


class PingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | int
    action: Literal["ping"]


class AuthMeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | int
    action: Literal["auth.me"]


class GamesCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | int
    action: Literal["games.create"]


class GamesGetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | int
    action: Literal["games.get"]
    game_id: int


Msg = Union[PingIn, AuthMeIn, GamesCreateIn, GamesGetIn]

Inbound = Annotated[
    Union[PingIn, AuthMeIn, GamesCreateIn, GamesGetIn],
    Field(discriminator="action"),
]

_inbound_adapter: TypeAdapter[Inbound] = TypeAdapter(Inbound)


def parse_inbound(data: Any) -> Inbound:
    return _inbound_adapter.validate_python(data)


def validation_error_payload(raw: dict[str, Any], exc: ValidationError) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "ok": False,
        "error": {"detail": "invalid message", "errors": exc.errors()},
    }
