import pytest

from backend.domain.moves import Cell, down, knight_moves, left, right, up
from backend.exceptions import InvalidCellError


def test_up_one_step():
    assert up(Cell("e4"), 1) == Cell("e5")


def test_down_one_step():
    assert down(Cell("e4"), 1) == Cell("e3")


def test_right_two_steps():
    assert right(Cell("e4"), 2) == Cell("g4")


def test_left_off_board_returns_none():
    assert left(Cell("a4"), 1) is None


def test_invalid_cell_raises():
    with pytest.raises(InvalidCellError):
        up(Cell("z9"), 1)


def test_knight_moves_from_center_count():
    cells = knight_moves(Cell("e4"))
    assert len(cells) == 8


def test_knight_moves_from_corner():
    cells = knight_moves(Cell("a1"))
    assert len(cells) == 2
    assert Cell("b3") in cells
    assert Cell("c2") in cells
