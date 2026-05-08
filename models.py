from tortoise import fields
from tortoise.models import Model


class User(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=30)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"


class Game(Model):
    id = fields.IntField(pk=True)
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
