from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from tortoise.expressions import F, Q
from tortoise.transactions import in_transaction

import backend.domain.board_play as board_play
from backend.config.game_play import START_BATTLE_FIELD_CLASS
from backend.models import Game, QueueWhoWantPlay, User
from backend.utils import new_user_uuid

_MATCHMAKING_TX_ITERS = 12


async def purge_expired_anonymous_users() -> int:
    """Удаляет анонимных пользователей с истёкшим сроком (и связанные игры по CASCADE)."""
    now = datetime.now(timezone.utc)
    result = await User.filter(
        is_anonymous=True,
        anonymous_expires_at__isnull=False,
        anonymous_expires_at__lt=now,
    ).delete()
    if isinstance(result, tuple):
        return int(result[0])
    return int(result)


class GameDB:
    async def _ensure_meta_persisted(self, game: Game) -> Game:
        bf = game.battle_field
        if isinstance(bf, dict) and board_play.META_KEY not in bf:
            new_bf = board_play.ensure_battle_field_has_meta(bf)
            await Game.filter(id=game.id).update(battle_field=new_bf)
            game.battle_field = new_bf
        return game

    async def get(self, game_id: int) -> Game:
        game = await Game.get(id=game_id).prefetch_related("white_user", "black_user")
        return await self._ensure_meta_persisted(game)

    async def save_game_state(
        self,
        game_id: int,
        battle_field: dict[str, dict[str, object] | None],
        whose_move: str,
        winner_side: str | None = None,
    ) -> Game:
        upd: dict[str, object] = {
            "battle_field": battle_field,
            "whose_move": whose_move,
            "state_version": F("state_version") + 1,
        }
        if winner_side is not None:
            upd["winner_side"] = winner_side
        await Game.filter(id=game_id).update(**upd)
        return await self.get(game_id)

    async def create_pair(self, white_user_id: UUID, black_user_id: UUID) -> Game:
        game = await Game.create(
            white_user_id=white_user_id,
            black_user_id=black_user_id,
            whose_move="white",
            battle_field=START_BATTLE_FIELD_CLASS().serialize(),
        )
        return await Game.get(id=game.id).prefetch_related("white_user", "black_user")

    async def find_active_pair_game_for_user(self, user_id: UUID) -> Game | None:
        """Партия с двумя игроками, где участвует user_id (для авто-покидания после закрытия вкладки)."""
        g = (
            await Game.filter(
                Q(white_user_id=user_id) | Q(black_user_id=user_id),
                white_user_id__isnull=False,
                black_user_id__isnull=False,
            )
            .prefetch_related("white_user", "black_user")
            .first()
        )
        if g is None:
            return None
        return await self._ensure_meta_persisted(g)

    async def create_step_1(self, user_id: UUID) -> Game:
        game = await Game.create(
            white_user_id=user_id,
            black_user=None,
            whose_move="white",
            battle_field=START_BATTLE_FIELD_CLASS().serialize(),
        )
        return await Game.get(id=game.id).prefetch_related("white_user", "black_user")

    async def create_step_2(self, user: User) -> Game:
        game = await Game.filter(black_user__isnull=True).order_by("created_at").first()
        if game is None:
            return await Game.create(
                white_user=None,
                black_user=user,
                whose_move="white",
                battle_field=START_BATTLE_FIELD_CLASS().serialize(),
            )

        game.black_user = user
        await game.save()
        return await Game.get(id=game.id).prefetch_related("white_user", "black_user")


class UserRepository:
    async def get_by_id(self, user_id: UUID) -> User | None:
        return await User.get_or_none(id=user_id)

    async def create_anonymous(self, name: str, ttl_hours: int) -> User:
        uid = new_user_uuid()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        return await User.create(
            id=uid,
            name=name[:30],
            is_anonymous=True,
            anonymous_expires_at=expires_at,
            email=None,
            google_sub=None,
        )

    async def upsert_google_user(self, google_sub: str, email: str, name: str) -> User:
        existing = await User.get_or_none(google_sub=google_sub)
        short_name = name[:30] if name else email.split("@")[0][:30]
        if existing:
            await User.filter(id=existing.id).update(
                email=email,
                name=short_name,
                is_anonymous=False,
                anonymous_expires_at=None,
            )
            return await User.get(id=existing.id)
        uid = new_user_uuid()
        return await User.create(
            id=uid,
            name=short_name,
            email=email,
            google_sub=google_sub,
            is_anonymous=False,
            anonymous_expires_at=None,
        )


class QueueWhoWantPlayRepository:
    """Репозиторий для `QueueWhoWantPlay`: очередь подбора соперника."""

    def __init__(self, game_db: GameDB) -> None:
        self._game_db = game_db

    async def count_others_waiting(self, user_id: UUID) -> int:
        """Сколько других пользователей в очереди (не считая ``user_id``)."""
        return await QueueWhoWantPlay.exclude(user_id=user_id).count()

    async def remove(self, user_id: UUID) -> None:
        await QueueWhoWantPlay.filter(user_id=user_id).delete()

    async def try_join_or_match(
        self, user_id: UUID
    ) -> (
        tuple[Literal["matched"], Game]
        | tuple[Literal["waiting"], datetime]
    ):
        """
        В транзакции: ищем другого ожидающего с блокировкой строк (FOR UPDATE),
        при нахождении — удаляем обоих из очереди и создаём партию (белые — кто ждал раньше).
        Иначе ставим в очередь (или подтверждаем ожидание) и возвращаем время постановки.
        """
        async with in_transaction():
            for _ in range(_MATCHMAKING_TX_ITERS):
                other = (
                    await QueueWhoWantPlay.exclude(user_id=user_id)
                    .order_by("created_at")
                    .select_for_update()
                    .first()
                )
                if other is not None:
                    partner_id = other.user_id  # type: ignore[attr-defined]
                    await QueueWhoWantPlay.filter(user_id__in=[partner_id, user_id]).delete()
                    game = await self._game_db.create_pair(partner_id, user_id)
                    return ("matched", game)

                mine = (
                    await QueueWhoWantPlay.filter(user_id=user_id)
                    .select_for_update()
                    .first()
                )
                if mine is not None:
                    return ("waiting", mine.created_at)

                await QueueWhoWantPlay.create(user_id=user_id)

            row = await QueueWhoWantPlay.get(user_id=user_id)
            return ("waiting", row.created_at)
