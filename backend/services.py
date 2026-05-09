import json
from uuid import UUID

from tortoise.exceptions import DoesNotExist

import backend.domain as domain
import backend.domain.board_play as board_play
import backend.exceptions as exceptions
import backend.models as models
import backend.repositories as repositories
from backend.domain.moves import ensure_cell


def _player_team(game: models.Game, user_id: UUID) -> str | None:
    w: UUID | None = game.white_user_id  # type: ignore[attr-defined]
    b: UUID | None = game.black_user_id  # type: ignore[attr-defined]
    if user_id == w:
        return "white"
    if user_id == b:
        return "black"
    return None


def battle_field_patch(
    client_bf: dict[str, object] | None,
    server_bf: dict[str, object],
) -> dict[str, object]:
    """Клетки, где позиция клиента расходится с сервером (значения — как на сервере)."""
    client_bf = client_bf or {}
    patch: dict[str, object] = {}
    keys = set(client_bf.keys()) | set(server_bf.keys())
    for k in keys:
        vc = client_bf.get(k)
        vs = server_bf.get(k)
        if json.dumps(vc, sort_keys=True) != json.dumps(vs, sort_keys=True):
            patch[str(k)] = vs
    return patch


def _opponent_id(game: models.Game, user_id: UUID) -> UUID | None:
    w: UUID | None = game.white_user_id  # type: ignore[attr-defined]
    b: UUID | None = game.black_user_id  # type: ignore[attr-defined]
    if w is None or b is None:
        return None
    if user_id == w:
        return b
    if user_id == b:
        return w
    return None


class UserService:
    def __init__(self, user_repository: repositories.UserRepository) -> None:
        self.user_repository = user_repository

    async def get_user(self, user_id: UUID) -> models.User:
        user = await self.user_repository.get_by_id(user_id)
        if user is None:
            raise exceptions.UserNotFoundError(user_id=str(user_id))
        return user

    async def create_anonymous_user(self, name: str | None, ttl_hours: int) -> models.User:
        display_name = (name or "Guest").strip() or "Guest"
        return await self.user_repository.create_anonymous(display_name, ttl_hours)

    async def upsert_google_user(self, google_sub: str, email: str, name: str) -> models.User:
        return await self.user_repository.upsert_google_user(google_sub, email, name)


class GameService:
    def __init__(self, game_db: repositories.GameDB, user_service: UserService) -> None:
        self.game_db = game_db
        self.user_service = user_service

    async def as_dict(self, game_or_id: int | models.Game) -> dict[str, object]:
        if isinstance(game_or_id, int):
            game = await self.game_db.get(game_or_id)
        else:
            game = game_or_id
        white_user = (
            None
            if game.white_user is None
            else domain.user.User(
                name=game.white_user.name,
                team=domain.user.Team.WHITE,
                id=str(game.white_user.id),
            )
        )
        black_user = (
            None
            if game.black_user is None
            else domain.user.User(
                name=game.black_user.name,
                team=domain.user.Team.BLACK,
                id=str(game.black_user.id),
            )
        )
        chess_game = domain.game.Game(
            battle_field=domain.game.SerializedBattleField(data=game.battle_field),
            white_user=white_user,
            black_user=black_user,
            whose_move=domain.user.Team(game.whose_move),
        )
        serialized_game = chess_game.serialize()
        serialized_game["id"] = game.id
        serialized_game["whose_move"] = str(game.whose_move)
        serialized_game["state_version"] = int(game.state_version)  # type: ignore[arg-type]
        bf = game.battle_field
        board = board_play.board_map_from_json(bf if isinstance(bf, dict) else {})
        serialized_game["check_to"] = board_play.side_in_check(board)
        ws = getattr(game, "winner_side", None)
        serialized_game["winner_side"] = (
            None if ws is None or ws == "" else str(ws).lower()
        )
        return serialized_game

    async def create_game(self, user_id: UUID) -> dict[str, object]:
        await self.user_service.get_user(user_id)
        game = await self.game_db.create_step_1(user_id)
        return await self.as_dict(game)

    async def create_step_1(self, user: models.User) -> models.Game:
        return await self.game_db.create_step_1(user.id)

    async def create_step_2(self, user: models.User) -> models.Game:
        return await self.game_db.create_step_2(user)

    async def find_active_pair_game_for_user(self, user_id: UUID) -> models.Game | None:
        return await self.game_db.find_active_pair_game_for_user(user_id)

    async def active_game_dict(self, user_id: UUID) -> dict[str, object] | None:
        """Текущая парная партия пользователя или None."""
        g = await self.find_active_pair_game_for_user(user_id)
        if g is None:
            return None
        return await self.as_dict(g)

    async def sync_game(
        self,
        game_id: int,
        user_id: UUID,
        client_version: int | None,
        client_battle_field: dict[str, object] | None,
    ) -> dict[str, object]:
        """Дельта относительно кэшированного поля клиента или полная партия."""
        try:
            game = await self.game_db.get(game_id)
        except DoesNotExist:
            raise exceptions.GameNotFoundError(game_id=game_id) from None
        if _player_team(game, user_id) is None:
            raise exceptions.GameForbiddenError()
        sv = int(game.state_version)  # type: ignore[arg-type]
        if client_version is not None and client_version == sv:
            return {"status": "unchanged", "state_version": sv}
        full = await self.as_dict(game)
        if client_battle_field is None:
            return {"status": "full", "game": full}
        patch = battle_field_patch(client_battle_field, game.battle_field)
        gbf = game.battle_field
        board = board_play.board_map_from_json(gbf if isinstance(gbf, dict) else {})
        check_to = board_play.side_in_check(board)
        if not patch:
            return {"status": "unchanged", "state_version": sv}
        out: dict[str, object] = {
            "status": "patch",
            "game_id": game_id,
            "state_version": sv,
            "whose_move": str(game.whose_move),
            "battle_field_patch": patch,
            "check_to": check_to,
        }
        wsg = getattr(game, "winner_side", None)
        if wsg is not None and str(wsg) != "":
            out["winner_side"] = str(wsg).lower()
        return out

    async def abandon_game(self, game_id: int, user_id: UUID) -> UUID | None:
        game = await models.Game.get_or_none(id=game_id)
        if game is None:
            raise exceptions.GameNotFoundError(game_id=game_id)
        opponent = _opponent_id(game, user_id)
        if opponent is None:
            raise exceptions.GameForbiddenError()
        await game.delete()
        return opponent

    async def legal_moves(self, game_id: int, user_id: UUID, from_cell: str) -> list[str]:
        try:
            fc = ensure_cell(from_cell)
        except exceptions.InvalidCellError as e:
            raise exceptions.InvalidMoveError(str(e)) from e

        try:
            game = await self.game_db.get(game_id)
        except DoesNotExist:
            raise exceptions.GameNotFoundError(game_id=game_id) from None
        if game.white_user_id is None or game.black_user_id is None:  # type: ignore[attr-defined]
            raise exceptions.InvalidMoveError("Game is not ready.")
        if getattr(game, "winner_side", None):
            raise exceptions.InvalidMoveError("Game already finished.")

        team = _player_team(game, user_id)
        if team is None:
            raise exceptions.GameForbiddenError()
        if game.whose_move != team:
            raise exceptions.InvalidMoveError("Not your turn.")

        raw_bf = game.battle_field
        board = board_play.board_map_from_json(raw_bf)
        meta = board_play.get_position_meta(raw_bf, board)
        piece = board.get(fc)
        if piece is None:
            raise exceptions.InvalidMoveError("No piece on source square.")
        if piece.color != team:
            raise exceptions.InvalidMoveError("That piece is not yours.")

        allowed = board_play.legal_targets(fc, board, meta)
        return [str(c) for c in allowed]

    async def play_move(self, game_id: int, user_id: UUID, from_cell: str, to_cell: str) -> dict[str, object]:
        try:
            fc = ensure_cell(from_cell)
            tc = ensure_cell(to_cell)
        except exceptions.InvalidCellError as e:
            raise exceptions.InvalidMoveError(str(e)) from e

        try:
            game = await self.game_db.get(game_id)
        except DoesNotExist:
            raise exceptions.GameNotFoundError(game_id=game_id) from None
        if game.white_user_id is None or game.black_user_id is None:  # type: ignore[attr-defined]
            raise exceptions.InvalidMoveError("Game is not ready.")
        if getattr(game, "winner_side", None):
            raise exceptions.InvalidMoveError("Game already finished.")

        team = _player_team(game, user_id)
        if team is None:
            raise exceptions.GameForbiddenError()
        if game.whose_move != team:
            raise exceptions.InvalidMoveError("Not your turn.")

        raw_bf = game.battle_field
        board = board_play.board_map_from_json(raw_bf)
        meta = board_play.get_position_meta(raw_bf, board)
        piece = board.get(fc)
        if piece is None:
            raise exceptions.InvalidMoveError("No piece on source square.")
        if piece.color != team:
            raise exceptions.InvalidMoveError("That piece is not yours.")

        allowed = board_play.legal_targets(fc, board, meta)
        if tc not in allowed:
            raise exceptions.InvalidMoveError("Illegal move.")

        new_board, new_meta = board_play.apply_full_move(board, meta, fc, tc)
        new_json = board_play.attach_meta(board_play.json_from_board_map(new_board), new_meta)
        next_turn = board_play.opposite_team(team)
        winner_side: str | None = None
        if board_play.is_checkmate(new_board, new_meta, next_turn):
            winner_side = team
        updated = await self.game_db.save_game_state(
            game_id,
            new_json,
            next_turn,
            winner_side=winner_side,
        )
        return await self.as_dict(updated)
