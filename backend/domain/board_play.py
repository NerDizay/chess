"""Разбор позиции с бэкенда и вычисление допустимых ходов (в т.ч. рокировка, взятие на проходе)."""

from __future__ import annotations

import copy
from typing import Any, Callable

from backend.domain.moves import Cell, down, down_left, down_right, up, up_left, up_right
from backend.domain.pieces import Bishop, King, Knight, Pawn, Piece, Queen, Rook

META_KEY = "_meta"


def piece_from_dict(data: dict[str, object]) -> Piece:
    name = str(data["name"])
    color = str(data["color"])
    factories: dict[str, Callable[[str], Piece]] = {
        "pawn": Pawn,
        "rook": Rook,
        "knight": Knight,
        "bishop": Bishop,
        "queen": Queen,
        "king": King,
    }
    ctor = factories[name]
    return ctor(color)


def board_map_from_json(data: dict[str, dict[str, object] | None]) -> dict[Cell, Piece | None]:
    columns = "abcdefgh"
    board: dict[Cell, Piece | None] = {}
    for rank in range(1, 9):
        for file_ in columns:
            c = Cell(f"{file_}{rank}")
            raw = data.get(str(c))
            board[c] = None if raw is None else piece_from_dict(raw)
    return board


def default_position_meta() -> dict[str, Any]:
    return {"wk": True, "wq": True, "bk": True, "bq": True, "ep": None}


def infer_castle_rights_from_board(board: dict[Cell, Piece | None]) -> dict[str, bool]:
    """Если в сохранённой партии нет _meta — восстанавливаем права по фигурам на «домашних» полях."""

    def corner(color: str, sq: str, name: str) -> bool:
        p = board.get(Cell(sq))
        return p is not None and p.color == color and p.name == name

    wk = corner("white", "e1", "king") and corner("white", "h1", "rook")
    wq = corner("white", "e1", "king") and corner("white", "a1", "rook")
    bk = corner("black", "e8", "king") and corner("black", "h8", "rook")
    bq = corner("black", "e8", "king") and corner("black", "a8", "rook")
    return {"wk": wk, "wq": wq, "bk": bk, "bq": bq}


def get_position_meta(raw_bf: dict[str, Any], board: dict[Cell, Piece | None]) -> dict[str, Any]:
    m = default_position_meta()
    stored = raw_bf.get(META_KEY)
    if isinstance(stored, dict):
        for k in ("wk", "wq", "bk", "bq"):
            if k in stored and isinstance(stored[k], bool):
                m[k] = stored[k]
        ep = stored.get("ep")
        if ep is None or isinstance(ep, str):
            m["ep"] = ep
    else:
        m.update(infer_castle_rights_from_board(board))
    return m


def attach_meta(cell_json: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    out = dict(cell_json)
    out[META_KEY] = {
        "wk": bool(meta["wk"]),
        "wq": bool(meta["wq"]),
        "bk": bool(meta["bk"]),
        "bq": bool(meta["bq"]),
        "ep": meta.get("ep"),
    }
    return out


def ensure_battle_field_has_meta(raw_bf: dict[str, Any]) -> dict[str, Any]:
    """Дописать ``_meta`` к позиции из старых сохранений БД (рокировка / en passant)."""
    if META_KEY in raw_bf:
        return raw_bf
    board = board_map_from_json(raw_bf)
    meta = get_position_meta(raw_bf, board)
    return attach_meta(json_from_board_map(board), meta)


def json_from_board_map(board: dict[Cell, Piece | None]) -> dict[str, dict[str, object] | None]:
    out: dict[str, dict[str, object] | None] = {}
    for cell, piece in board.items():
        out[str(cell)] = None if piece is None else piece.serialize()
    return out


def _occupancy_filter(targets: list[Cell], color: str, board: dict[Cell, Piece | None]) -> list[Cell]:
    out: list[Cell] = []
    for t in targets:
        occ = board.get(t)
        if occ is None or occ.color != color:
            out.append(t)
    return out


def _sliding_legal(cell: Cell, piece: Piece, board: dict[Cell, Piece | None]) -> list[Cell]:
    result: list[Cell] = []
    for direction in piece.possible_moves:
        for step in range(1, piece.max_step + 1):
            t = direction(cell, step)
            if t is None:
                break
            occ = board.get(t)
            if occ is None:
                result.append(t)
            elif occ.color != piece.color:
                result.append(t)
                break
            else:
                break
    return result


def _pawn_push_targets(cell: Cell, piece: Piece, board: dict[Cell, Piece | None]) -> list[Cell]:
    out: list[Cell] = []
    forward = up if piece.color == "white" else down
    one = forward(cell, 1)
    if one is not None and board.get(one) is None:
        out.append(one)

    rank = cell[1]
    if piece.color == "white" and rank == "2":
        mid = forward(cell, 1)
        two = forward(cell, 2)
        if (
            mid is not None
            and two is not None
            and board.get(mid) is None
            and board.get(two) is None
        ):
            out.append(two)
    elif piece.color == "black" and rank == "7":
        mid = forward(cell, 1)
        two = forward(cell, 2)
        if (
            mid is not None
            and two is not None
            and board.get(mid) is None
            and board.get(two) is None
        ):
            out.append(two)
    return out


def _pawn_capture_squares(cell: Cell, piece: Piece, board: dict[Cell, Piece | None]) -> list[Cell]:
    cap_dirs = [up_left, up_right] if piece.color == "white" else [down_left, down_right]
    out: list[Cell] = []
    for direction in cap_dirs:
        t = direction(cell, 1)
        if t is None:
            continue
        occ = board.get(t)
        if occ is not None and occ.color != piece.color:
            out.append(t)
    return out


def _pawn_ep_capture(
    cell: Cell,
    piece: Piece,
    board: dict[Cell, Piece | None],
    meta: dict[str, Any],
) -> list[Cell]:
    ep = meta.get("ep")
    if ep is None or ep == "":
        return []
    ep_cell = Cell(str(ep))
    cap_dirs = [up_left, up_right] if piece.color == "white" else [down_left, down_right]
    out: list[Cell] = []
    for direction in cap_dirs:
        t = direction(cell, 1)
        if t is None or t != ep_cell:
            continue
        if board.get(ep_cell) is not None:
            continue
        cap_rank = cell[1]
        behind = Cell(ep_cell[0] + cap_rank)
        victim = board.get(behind)
        if victim is not None and victim.name == "pawn" and victim.color != piece.color:
            out.append(ep_cell)
    return out


def _pawn_pseudo(
    cell: Cell,
    piece: Piece,
    board: dict[Cell, Piece | None],
    meta: dict[str, Any],
) -> list[Cell]:
    return (
        _pawn_push_targets(cell, piece, board)
        + _pawn_capture_squares(cell, piece, board)
        + _pawn_ep_capture(cell, piece, board, meta)
    )


def _king_castling_targets(
    cell: Cell,
    piece: Piece,
    board: dict[Cell, Piece | None],
    meta: dict[str, Any],
) -> list[Cell]:
    if piece.name != "king":
        return []
    out: list[Cell] = []
    if piece.color == "white" and cell == Cell("e1"):
        rk = board.get(Cell("h1"))
        if meta.get("wk") and rk is not None and rk.name == "rook" and rk.color == "white":
            if board.get(Cell("f1")) is None and board.get(Cell("g1")) is None:
                out.append(Cell("g1"))
        rq = board.get(Cell("a1"))
        if meta.get("wq") and rq is not None and rq.name == "rook" and rq.color == "white":
            if board.get(Cell("b1")) is None and board.get(Cell("c1")) is None and board.get(Cell("d1")) is None:
                out.append(Cell("c1"))
    elif piece.color == "black" and cell == Cell("e8"):
        rk = board.get(Cell("h8"))
        if meta.get("bk") and rk is not None and rk.name == "rook" and rk.color == "black":
            if board.get(Cell("f8")) is None and board.get(Cell("g8")) is None:
                out.append(Cell("g8"))
        rq = board.get(Cell("a8"))
        if meta.get("bq") and rq is not None and rq.name == "rook" and rq.color == "black":
            if board.get(Cell("b8")) is None and board.get(Cell("c8")) is None and board.get(Cell("d8")) is None:
                out.append(Cell("c8"))
    return out


def _pawn_attack_from(cell: Cell, color: str) -> list[Cell]:
    dirs = [up_left, up_right] if color == "white" else [down_left, down_right]
    out: list[Cell] = []
    for d in dirs:
        t = d(cell, 1)
        if t is not None:
            out.append(t)
    return out


def _squares_attacked_by(board: dict[Cell, Piece | None], by_color: str) -> set[Cell]:
    attacked: set[Cell] = set()
    for cell, piece in board.items():
        if piece is None or piece.color != by_color:
            continue
        if piece.name == "pawn":
            attacked.update(_pawn_attack_from(cell, piece.color))
        elif piece.name == "knight":
            for t in piece.get_possible_moves(cell):
                attacked.add(t)
        elif piece.name == "king":
            for direction in piece.possible_moves:
                t = direction(cell, 1)
                if t is not None:
                    attacked.add(t)
        elif piece.name in ("rook", "bishop", "queen"):
            for direction in piece.possible_moves:
                for step in range(1, piece.max_step + 1):
                    t = direction(cell, step)
                    if t is None:
                        break
                    attacked.add(t)
                    occ = board.get(t)
                    if occ is not None:
                        break
    return attacked


def square_attacked(board: dict[Cell, Piece | None], target: Cell, by_color: str) -> bool:
    return target in _squares_attacked_by(board, by_color)


def find_king(board: dict[Cell, Piece | None], color: str) -> Cell | None:
    for cell, piece in board.items():
        if piece is not None and piece.color == color and piece.name == "king":
            return cell
    return None


def in_check(board: dict[Cell, Piece | None], color: str) -> bool:
    k = find_king(board, color)
    if k is None:
        return False
    opp = "black" if color == "white" else "white"
    return square_attacked(board, k, opp)


def side_in_check(board: dict[Cell, Piece | None]) -> str | None:
    """Сторона, чей король под боем (``white`` / ``black``), или ``None``."""
    for color in ("white", "black"):
        if in_check(board, color):
            return color
    return None


def pseudo_legal_targets(
    cell: Cell,
    board: dict[Cell, Piece | None],
    meta: dict[str, Any],
) -> list[Cell]:
    piece = board.get(cell)
    if piece is None:
        return []
    name = piece.name
    if name == "pawn":
        return _pawn_pseudo(cell, piece, board, meta)
    if name == "knight":
        return _occupancy_filter(piece.get_possible_moves(cell), piece.color, board)
    if name == "king":
        base = _sliding_legal(cell, piece, board)
        seen = set(base)
        for t in _king_castling_targets(cell, piece, board, meta):
            if t not in seen:
                base.append(t)
                seen.add(t)
        return base
    if name in ("rook", "bishop", "queen"):
        return _sliding_legal(cell, piece, board)
    return []


def _castling_rook_squares(fc: Cell, tc: Cell, piece: Piece) -> tuple[Cell, Cell] | None:
    """Возвращает (откуда ладья, куда ладья) при рокировке короля или None."""
    if piece.name != "king":
        return None
    if fc == Cell("e1") and tc == Cell("g1"):
        return (Cell("h1"), Cell("f1"))
    if fc == Cell("e1") and tc == Cell("c1"):
        return (Cell("a1"), Cell("d1"))
    if fc == Cell("e8") and tc == Cell("g8"):
        return (Cell("h8"), Cell("f8"))
    if fc == Cell("e8") and tc == Cell("c8"):
        return (Cell("a8"), Cell("d8"))
    return None


def _ep_captured_square(fc: Cell, tc: Cell, piece: Piece, board: dict[Cell, Piece | None]) -> Cell | None:
    if piece.name != "pawn":
        return None
    if board.get(tc) is not None:
        return None
    if fc[0] == tc[0]:
        return None
    return Cell(tc[0] + fc[1])


def apply_move_on_board(
    board: dict[Cell, Piece | None],
    from_cell: Cell,
    to_cell: Cell,
    meta: dict[str, Any] | None = None,
) -> dict[Cell, Piece | None]:
    """Применяет ход; для рокировки и взятия на проходе нужен ``meta`` (права и ep обновляются отдельно)."""
    new_board: dict[Cell, Piece | None] = copy.deepcopy(board)
    piece = new_board[from_cell]
    if piece is None:
        return new_board

    castle_rook = _castling_rook_squares(from_cell, to_cell, piece)
    if castle_rook is not None:
        r_from, r_to = castle_rook
        rook = new_board.get(r_from)
        new_board[to_cell] = piece
        new_board[from_cell] = None
        new_board[r_to] = rook
        new_board[r_from] = None
        return new_board

    ep_sq = _ep_captured_square(from_cell, to_cell, piece, new_board)
    if ep_sq is not None and meta is not None and meta.get("ep") == str(to_cell):
        new_board[to_cell] = piece
        new_board[from_cell] = None
        new_board[ep_sq] = None
        return new_board

    new_board[to_cell] = piece
    new_board[from_cell] = None
    return new_board


def _update_meta_after_move(
    board_before: dict[Cell, Piece | None],
    meta_before: dict[str, Any],
    fc: Cell,
    tc: Cell,
    piece: Piece,
) -> dict[str, Any]:
    m = {
        "wk": bool(meta_before["wk"]),
        "wq": bool(meta_before["wq"]),
        "bk": bool(meta_before["bk"]),
        "bq": bool(meta_before["bq"]),
        "ep": None,
    }

    if piece.name == "king":
        if piece.color == "white":
            m["wk"] = m["wq"] = False
        else:
            m["bk"] = m["bq"] = False
    elif piece.name == "rook":
        if fc == Cell("a1") and piece.color == "white":
            m["wq"] = False
        elif fc == Cell("h1") and piece.color == "white":
            m["wk"] = False
        elif fc == Cell("a8") and piece.color == "black":
            m["bq"] = False
        elif fc == Cell("h8") and piece.color == "black":
            m["bk"] = False

    victim = board_before.get(tc)
    if victim is None and piece.name == "pawn":
        alt = _ep_captured_square(fc, tc, piece, board_before)
        if alt is not None:
            victim = board_before.get(alt)
    if victim is not None:
        if tc == Cell("a1"):
            m["wq"] = False
        if tc == Cell("h1"):
            m["wk"] = False
        if tc == Cell("a8"):
            m["bq"] = False
        if tc == Cell("h8"):
            m["bk"] = False

    # пропуск пешки на два поля — поле «взятия на проходе» на следующий ход
    if piece.name == "pawn":
        fr = int(fc[1])
        tr = int(tc[1])
        if abs(fr - tr) == 2 and fc[0] == tc[0]:
            mid = (fr + tr) // 2
            m["ep"] = fc[0] + str(mid)

    return m


def _castle_path_safe(board: dict[Cell, Piece | None], color: str, side: str) -> bool:
    """side: 'k' | 'q' — поля, которые проходит/занимает король, не под боем."""
    opp = "black" if color == "white" else "white"
    if color == "white":
        if in_check(board, "white"):
            return False
        if side == "k":
            return not square_attacked(board, Cell("f1"), opp) and not square_attacked(board, Cell("g1"), opp)
        return not square_attacked(board, Cell("d1"), opp) and not square_attacked(board, Cell("c1"), opp)
    if in_check(board, "black"):
        return False
    if side == "k":
        return not square_attacked(board, Cell("f8"), opp) and not square_attacked(board, Cell("g8"), opp)
    return not square_attacked(board, Cell("d8"), opp) and not square_attacked(board, Cell("c8"), opp)


def _filter_castling(
    cell: Cell,
    targets: list[Cell],
    board: dict[Cell, Piece | None],
    piece: Piece,
    meta: dict[str, Any],
) -> list[Cell]:
    if piece.name != "king" or piece.color not in ("white", "black"):
        return targets
    out: list[Cell] = []
    for t in targets:
        cr = _castling_rook_squares(cell, t, piece)
        if cr is None:
            out.append(t)
            continue
        if piece.color == "white" and t == Cell("g1"):
            if meta.get("wk") and _castle_path_safe(board, "white", "k"):
                out.append(t)
        elif piece.color == "white" and t == Cell("c1"):
            if meta.get("wq") and _castle_path_safe(board, "white", "q"):
                out.append(t)
        elif piece.color == "black" and t == Cell("g8"):
            if meta.get("bk") and _castle_path_safe(board, "black", "k"):
                out.append(t)
        elif piece.color == "black" and t == Cell("c8"):
            if meta.get("bq") and _castle_path_safe(board, "black", "q"):
                out.append(t)
    return out


def legal_targets(
    cell: Cell,
    board: dict[Cell, Piece | None],
    meta: dict[str, Any],
) -> list[Cell]:
    piece = board.get(cell)
    if piece is None:
        return []
    raw = pseudo_legal_targets(cell, board, meta)
    raw = _filter_castling(cell, raw, board, piece, meta)
    mover = piece.color
    result: list[Cell] = []
    for t in raw:
        nb = apply_move_on_board(board, cell, t, meta)
        if not in_check(nb, mover):
            result.append(t)
    return result


def apply_full_move(
    board: dict[Cell, Piece | None],
    meta_before: dict[str, Any],
    from_cell: Cell,
    to_cell: Cell,
) -> tuple[dict[Cell, Piece | None], dict[str, Any]]:
    piece = board.get(from_cell)
    if piece is None:
        raise ValueError("empty from square")
    nb = apply_move_on_board(board, from_cell, to_cell, meta_before)
    new_meta = _update_meta_after_move(board, meta_before, from_cell, to_cell, piece)
    return nb, new_meta


def opposite_team(whose: str) -> str:
    return "black" if whose == "white" else "white"


def side_has_any_legal_move(
    board: dict[Cell, Piece | None],
    meta: dict[str, Any],
    side: str,
) -> bool:
    for cell, piece in board.items():
        if piece is None or piece.color != side:
            continue
        if legal_targets(cell, board, meta):
            return True
    return False


def is_checkmate(board: dict[Cell, Piece | None], meta: dict[str, Any], side_to_move: str) -> bool:
    """У стороны, чей сейчас ход, нет ходов и король под шахом."""
    return in_check(board, side_to_move) and not side_has_any_legal_move(board, meta, side_to_move)
