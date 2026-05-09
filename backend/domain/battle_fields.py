from backend.domain.board_play import attach_meta, default_position_meta, json_from_board_map
from backend.domain.moves import Cell
from backend.domain.pieces import Bishop, King, Knight, Pawn, Piece, Queen, Rook


def empty_board() -> dict[Cell, Piece | None]:
    columns = "abcdefgh"
    return {Cell(f"{file_}{rank}"): None for rank in range(1, 9) for file_ in columns}


class DefaultBattleField:
    def __init__(self) -> None:
        self.field = self._create_default_field()

    def _create_default_field(self) -> dict[Cell, Piece | None]:
        board = empty_board()
        columns = "abcdefgh"

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
        return attach_meta(serialized_field, default_position_meta())


def _serialize_field(board: dict[Cell, Piece | None], meta: dict[str, object]) -> dict[str, dict[str, object] | None]:
    return attach_meta(json_from_board_map(board), meta)


class MateTrainingBattleField:
    """Шах и разминка у мата: ферзь бьёт по чёрному королю (Kg8), белый король на h6."""

    def __init__(self) -> None:
        b = empty_board()
        b[Cell("h6")] = King("white")
        b[Cell("g8")] = King("black")
        b[Cell("f6")] = Queen("white")
        self.field = b

    def get_piece(self, cell: Cell) -> Piece | None:
        return self.field.get(cell)

    def serialize(self) -> dict[str, dict[str, object] | None]:
        meta: dict[str, object] = {"wk": False, "wq": False, "bk": False, "bq": False, "ep": None}
        return _serialize_field(self.field, meta)


class EnPassantTrainingBattleField:
    """Взятие на проходе: пешка e5 × d6, чёрная пешка на d5, в мета указан проходной ход ep=d6."""

    def __init__(self) -> None:
        b = empty_board()
        b[Cell("e1")] = King("white")
        b[Cell("e8")] = King("black")
        b[Cell("e5")] = Pawn("white")
        b[Cell("d5")] = Pawn("black")
        self.field = b

    def get_piece(self, cell: Cell) -> Piece | None:
        return self.field.get(cell)

    def serialize(self) -> dict[str, dict[str, object] | None]:
        meta: dict[str, object] = {"wk": False, "wq": False, "bk": False, "bq": False, "ep": "d6"}
        return _serialize_field(self.field, meta)


class CastleTrainingBattleField:
    """Рокировка: короли и ладьи на обычных полях, линии O-O и O-O-O свободны."""

    def __init__(self) -> None:
        b = empty_board()
        b[Cell("e1")] = King("white")
        b[Cell("h1")] = Rook("white")
        b[Cell("a1")] = Rook("white")
        b[Cell("e8")] = King("black")
        self.field = b

    def get_piece(self, cell: Cell) -> Piece | None:
        return self.field.get(cell)

    def serialize(self) -> dict[str, dict[str, object] | None]:
        meta: dict[str, object] = {"wk": True, "wq": True, "bk": False, "bq": False, "ep": None}
        return _serialize_field(self.field, meta)
