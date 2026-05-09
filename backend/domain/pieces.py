from dataclasses import dataclass, field
from typing import Callable

from backend.domain.moves import (
    Cell,
    directional_moves,
    down,
    down_left,
    down_right,
    knight_moves,
    left,
    right,
    up,
    up_left,
    up_right,
)

DirectionMove = Callable[[Cell, int], Cell | None]


@dataclass
class Piece:
    color: str
    name: str
    possible_moves: list[DirectionMove] = field(default_factory=list)
    max_step: int = 1

    def get_possible_moves(self, cell: Cell) -> list[Cell]:
        result: list[Cell] = []
        for move in self.possible_moves:
            result.extend(directional_moves(cell, move, self.max_step))
        return result

    def serialize(self) -> dict[str, object]:
        return {
            "color": self.color,
            "name": self.name,
            "possible_moves": [move.__name__ for move in self.possible_moves],
            "max_step": self.max_step,
        }


class Pawn(Piece):
    def __init__(self, color: str) -> None:
        forward_move = up if color.lower() == "white" else down
        super().__init__(
            color=color,
            name="pawn",
            possible_moves=[forward_move],
            max_step=1,
        )


class Rook(Piece):
    def __init__(self, color: str) -> None:
        super().__init__(
            color=color,
            name="rook",
            possible_moves=[up, right, down, left],
            max_step=8,
        )


class Knight(Piece):
    def __init__(self, color: str) -> None:
        super().__init__(
            color=color,
            name="knight",
            possible_moves=[],
            max_step=1,
        )

    def get_possible_moves(self, cell: Cell) -> list[Cell]:
        return knight_moves(cell)

    def serialize(self) -> dict[str, object]:
        data = super().serialize()
        data["possible_moves"] = ["knight_moves"]
        return data


class Bishop(Piece):
    def __init__(self, color: str) -> None:
        super().__init__(
            color=color,
            name="bishop",
            possible_moves=[up_right, up_left, down_right, down_left],
            max_step=8,
        )


class Queen(Piece):
    def __init__(self, color: str) -> None:
        super().__init__(
            color=color,
            name="queen",
            possible_moves=[up, right, down, left, up_right, up_left, down_right, down_left],
            max_step=8,
        )


class King(Piece):
    def __init__(self, color: str) -> None:
        super().__init__(
            color=color,
            name="king",
            possible_moves=[up, right, down, left, up_right, up_left, down_right, down_left],
            max_step=1,
        )
