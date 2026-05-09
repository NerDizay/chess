from tortoise import fields
from tortoise.models import Model

from backend.utils import new_user_uuid


class User(Model):
    id = fields.UUIDField(primary_key=True, default=new_user_uuid)
    name = fields.CharField(max_length=30)
    email = fields.CharField(max_length=255, null=True)
    google_sub = fields.CharField(max_length=255, null=True, unique=True)
    is_anonymous = fields.BooleanField(default=False)
    anonymous_expires_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table = "users"


class QueueWhoWantPlay(Model):
    """Очередь игроков, ожидающих соперника для автоподбора."""

    user = fields.ForeignKeyField(
        "models.User",
        related_name="queue_who_want_play_entry",
        on_delete=fields.CASCADE,
        unique=True,
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table = "queue_who_want_play"


class Game(Model):
    id = fields.IntField(primary_key=True)
    white_user = fields.ForeignKeyField(
        "models.User",
        related_name="white_games",
        on_delete=fields.CASCADE,
        null=True,
    )
    black_user = fields.ForeignKeyField(
        "models.User",
        related_name="black_games",
        on_delete=fields.CASCADE,
        null=True,
    )
    whose_move = fields.CharField(max_length=5)
    """После мата: ``white`` или ``black`` — кто выиграл; иначе ``None``."""
    winner_side = fields.CharField(max_length=5, null=True)
    battle_field = fields.JSONField()
    # Монотонно растёт при каждом сохранении позиции (клиент: дельта / IndexedDB).
    state_version = fields.IntField(default=1)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table = "games"
