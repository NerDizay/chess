from dataclasses import dataclass
from typing import Literal

from backend.exceptions import InvalidTeamError, InvalidUserNameError


MAX_USER_NAME_LENGTH = 30
Team = Literal["black", "white"]


@dataclass
class User:
    name: str
    team: Team
    id: str | None = None

    def __post_init__(self) -> None:
        if not self.name or len(self.name) > MAX_USER_NAME_LENGTH:
            raise InvalidUserNameError(name=self.name, max_length=MAX_USER_NAME_LENGTH)
        if self.team not in ("black", "white"):
            raise InvalidTeamError(team=self.team)

    def serialize(self) -> dict[str, str]:
        data = {"name": self.name, "team": self.team}
        if self.id is not None:
            data["id"] = self.id
        return data
