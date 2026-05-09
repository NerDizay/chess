from datetime import datetime, timedelta, timezone
from uuid import UUID

from backend.domain.battle_fields import DefaultBattleField
from backend.models import Game, User
from backend.utils import new_user_uuid


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
    async def get(self, game_id: int) -> Game:
        return await Game.get(id=game_id).prefetch_related("white_user", "black_user")

    async def create_step_1(self, user_id: UUID) -> Game:
        game = await Game.create(
            white_user_id=user_id,
            black_user=None,
            whose_move="white",
            battle_field=DefaultBattleField().serialize(),
        )
        return await Game.get(id=game.id).prefetch_related("white_user", "black_user")

    async def create_step_2(self, user: User) -> Game:
        game = await Game.filter(black_user__isnull=True).order_by("created_at").first()
        if game is None:
            return await Game.create(
                white_user=None,
                black_user=user,
                whose_move="white",
                battle_field=DefaultBattleField().serialize(),
            )

        game.black_user = user
        await game.save()
        return game


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
            existing.email = email
            existing.name = short_name
            existing.is_anonymous = False
            existing.anonymous_expires_at = None
            await existing.save()
            return existing
        uid = new_user_uuid()
        return await User.create(
            id=uid,
            name=short_name,
            email=email,
            google_sub=google_sub,
            is_anonymous=False,
            anonymous_expires_at=None,
        )
