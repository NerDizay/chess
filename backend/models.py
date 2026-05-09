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

    class Meta:
        table = "users"


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
    battle_field = fields.JSONField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "games"
