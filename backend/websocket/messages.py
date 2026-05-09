"""Схемы входящих сообщений WebSocket API (discriminated union по `action`)."""

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

__all__ = [
    "PingIn",
    "AuthMeIn",
    "GamesCreateIn",
    "GamesGetIn",
    "MatchmakingPlayIn",
    "MatchmakingCancelIn",
    "GamesAbandonIn",
    "GamesMoveIn",
    "GamesActiveIn",
    "GamesSyncIn",
    "GamesLegalMovesIn",
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


class MatchmakingPlayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | int
    action: Literal["matchmaking.play"]


class MatchmakingCancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | int
    action: Literal["matchmaking.cancel"]


class GamesAbandonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | int
    action: Literal["games.abandon"]
    game_id: int


class GamesMoveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | int
    action: Literal["games.move"]
    game_id: int
    from_cell: str
    to_cell: str


class GamesActiveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | int
    action: Literal["games.active"]


class GamesSyncIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | int
    action: Literal["games.sync"]
    game_id: int
    client_version: int | None = None
    battle_field: dict[str, Any] | None = None


class GamesLegalMovesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | int
    action: Literal["games.legal_moves"]
    game_id: int
    from_cell: str


Msg = Union[
    PingIn,
    AuthMeIn,
    GamesCreateIn,
    GamesGetIn,
    MatchmakingPlayIn,
    MatchmakingCancelIn,
    GamesAbandonIn,
    GamesMoveIn,
    GamesActiveIn,
    GamesSyncIn,
    GamesLegalMovesIn,
]

Inbound = Annotated[
    Union[
        PingIn,
        AuthMeIn,
        GamesCreateIn,
        GamesGetIn,
        MatchmakingPlayIn,
        MatchmakingCancelIn,
        GamesAbandonIn,
        GamesMoveIn,
        GamesActiveIn,
        GamesSyncIn,
        GamesLegalMovesIn,
    ],
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
