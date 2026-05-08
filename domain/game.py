from dataclasses import dataclass
from typing import Protocol

from domain.user import Team, User
from exceptions import InvalidGameUserAssignmentError


class BattleFieldLike(Protocol):
    def serialize(self) -> dict[str, object]:
        ...


@dataclass
class SerializedBattleField:
    data: dict[str, object]

    def serialize(self) -> dict[str, object]:
        return self.data


@dataclass
class Game:
    battle_field: BattleFieldLike
    white_user: User | None
    black_user: User | None
    whose_move: Team = "white"

    def __post_init__(self) -> None:
        if self.white_user is not None and self.white_user.team != "white":
            raise InvalidGameUserAssignmentError(
                expected_team="white",
                actual_team=self.white_user.team,
                role="white_user",
            )
        if self.black_user is not None and self.black_user.team != "black":
            raise InvalidGameUserAssignmentError(
                expected_team="black",
                actual_team=self.black_user.team,
                role="black_user",
            )

    def serialize(self) -> dict[str, object]:
        return {
            "battle_field": self.battle_field.serialize(),
            "white_user": None if self.white_user is None else self.white_user.serialize(),
            "black_user": None if self.black_user is None else self.black_user.serialize(),
            "whose_move": self.whose_move,
        }
