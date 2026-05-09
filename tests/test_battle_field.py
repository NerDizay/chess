from backend.domain.battle_fields import DefaultBattleField
from backend.domain.moves import Cell


def test_default_board_serializes_64_cells():
    field = DefaultBattleField()
    data = field.serialize()
    assert len(data) == 64


def test_white_king_on_e1():
    field = DefaultBattleField()
    piece = field.get_piece(Cell("e1"))
    assert piece is not None
    assert piece.name == "king"
    assert piece.color == "white"


def test_black_king_on_e8():
    field = DefaultBattleField()
    piece = field.get_piece(Cell("e8"))
    assert piece is not None
    assert piece.name == "king"
    assert piece.color == "black"
