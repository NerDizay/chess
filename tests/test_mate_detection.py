"""Детектор мата после хода."""

import backend.domain.board_play as board_play
from backend.domain.battle_fields import empty_board
from backend.domain.board_play import attach_meta, default_position_meta, is_checkmate, json_from_board_map
from backend.domain.moves import Cell
from backend.domain.pieces import King, Queen


def test_is_checkmate_adjacent_queen_defended() -> None:
    """Чёрный король на e8, белый ферзь на e7 под защитой белого короля — мат."""
    b = empty_board()
    b[Cell("e8")] = King("black")
    b[Cell("e7")] = Queen("white")
    b[Cell("d6")] = King("white")
    meta = {**default_position_meta(), "wk": False, "wq": False, "bk": False, "bq": False, "ep": None}
    raw = attach_meta(json_from_board_map(b), meta)
    board_map = board_play.board_map_from_json(raw)
    meta_restored = board_play.get_position_meta(raw, board_map)
    assert is_checkmate(board_map, meta_restored, "black")


def test_not_mate_when_can_move() -> None:
    """Чёрный король может уйти на g8 — не мат."""
    b = empty_board()
    b[Cell("h8")] = King("black")
    b[Cell("h7")] = Queen("white")
    b[Cell("f6")] = King("white")
    meta = {**default_position_meta(), "wk": False, "wq": False, "bk": False, "bq": False, "ep": None}
    raw = attach_meta(json_from_board_map(b), meta)
    bp = board_play.board_map_from_json(raw)
    mp = board_play.get_position_meta(raw, bp)
    assert not is_checkmate(bp, mp, "black")
