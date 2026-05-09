from backend.domain.moves import Cell
from backend.domain.pieces import Bishop, King, Knight, Pawn, Piece, Queen, Rook


class DefaultBattleField:
    def __init__(self) -> None:
        self.field = self._create_default_field()

    def _create_default_field(self) -> dict[Cell, Piece | None]:
        columns = "abcdefgh"
        board = {Cell(f"{file_}{rank}"): None for rank in range(1, 9) for file_ in columns}

        board[Cell("a1")] = Rook("white")
        board[Cell("b1")] = Knight("white")
        board[Cell("c1")] = Bishop("white")
        board[Cell("d1")] = Queen("white")
        board[Cell("e1")] = King("white")
        board[Cell("f1")] = Bishop("white")
        board[Cell("g1")] = Knight("white")
        board[Cell("h1")] = Rook("white")

        for file_ in columns:
            board[Cell(f"{file_}2")] = Pawn("white")

        board[Cell("a8")] = Rook("black")
        board[Cell("b8")] = Knight("black")
        board[Cell("c8")] = Bishop("black")
        board[Cell("d8")] = Queen("black")
        board[Cell("e8")] = King("black")
        board[Cell("f8")] = Bishop("black")
        board[Cell("g8")] = Knight("black")
        board[Cell("h8")] = Rook("black")

        for file_ in columns:
            board[Cell(f"{file_}7")] = Pawn("black")

        return board

    def get_piece(self, cell: Cell) -> Piece | None:
        return self.field.get(cell)

    def serialize(self) -> dict[str, dict[str, object] | None]:
        serialized_field: dict[str, dict[str, object] | None] = {}
        for cell, piece in self.field.items():
            serialized_field[str(cell)] = None if piece is None else piece.serialize()
        return serialized_field
