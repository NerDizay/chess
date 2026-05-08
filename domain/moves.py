from typing import Callable, NewType

from exceptions import InvalidCellError, InvalidKnightDeltaError, InvalidStepError


MIN_STEP = 1
MAX_STEP = 8
BOARD_COLUMNS = "abcdefgh"
BOARD_ROWS = "12345678"
Cell = NewType("Cell", str)


def _validate_step(step: int) -> None:
    if not MIN_STEP <= step <= MAX_STEP:
        raise InvalidStepError(step=step, min_step=MIN_STEP, max_step=MAX_STEP)


def _to_coords(cell: Cell) -> tuple[int, int]:
    if len(cell) != 2 or cell[0] not in BOARD_COLUMNS or cell[1] not in BOARD_ROWS:
        raise InvalidCellError(cell=str(cell))
    col_index = BOARD_COLUMNS.index(cell[0])
    row_index = BOARD_ROWS.index(cell[1])
    return col_index, row_index


def _from_coords(col_index: int, row_index: int) -> Cell | None:
    if not (0 <= col_index < 8 and 0 <= row_index < 8):
        return None
    return Cell(f"{BOARD_COLUMNS[col_index]}{BOARD_ROWS[row_index]}")


def _move(cell: Cell, d_col: int, d_row: int, step: int = 1) -> Cell | None:
    _validate_step(step)
    col_index, row_index = _to_coords(cell)
    return _from_coords(col_index + d_col * step, row_index + d_row * step)


def up(cell: Cell, step: int = 1) -> Cell | None:
    return _move(cell, 0, 1, step)


def right(cell: Cell, step: int = 1) -> Cell | None:
    return _move(cell, 1, 0, step)


def down(cell: Cell, step: int = 1) -> Cell | None:
    return _move(cell, 0, -1, step)


def left(cell: Cell, step: int = 1) -> Cell | None:
    return _move(cell, -1, 0, step)


def _compose(
    cell: Cell,
    first: Callable[[Cell, int], Cell | None],
    second: Callable[[Cell, int], Cell | None],
    step: int = 1,
) -> Cell | None:
    first_target = first(cell, step)
    if first_target is None:
        return None
    return second(first_target, step)


def up_right(cell: Cell, step: int = 1) -> Cell | None:
    return _compose(cell, up, right, step)


def up_left(cell: Cell, step: int = 1) -> Cell | None:
    return _compose(cell, up, left, step)


def down_right(cell: Cell, step: int = 1) -> Cell | None:
    return _compose(cell, down, right, step)


def down_left(cell: Cell, step: int = 1) -> Cell | None:
    return _compose(cell, down, left, step)


KNIGHT_DELTAS: tuple[tuple[int, int], ...] = (
    (2, 1),
    (2, -1),
    (-2, 1),
    (-2, -1),
    (1, 2),
    (1, -2),
    (-1, 2),
    (-1, -2),
)


def knight_move(cell: Cell, d_col: int, d_row: int) -> Cell | None:
    if (d_col, d_row) not in KNIGHT_DELTAS:
        raise InvalidKnightDeltaError(d_col=d_col, d_row=d_row)
    col_index, row_index = _to_coords(cell)
    return _from_coords(col_index + d_col, row_index + d_row)


def knight_moves(cell: Cell) -> list[Cell]:
    col_index, row_index = _to_coords(cell)
    result: list[Cell] = []
    for d_col, d_row in KNIGHT_DELTAS:
        target = _from_coords(col_index + d_col, row_index + d_row)
        if target is not None:
            result.append(target)
    return result


def directional_moves(
    cell: Cell,
    direction: Callable[[Cell, int], Cell | None],
    max_step: int = 8,
) -> list[Cell]:
    _validate_step(max_step)
    result: list[Cell] = []
    for step in range(1, max_step + 1):
        target = direction(cell, step)
        if target is None:
            break
        result.append(target)
    return result
