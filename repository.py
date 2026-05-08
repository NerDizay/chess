from domain.battle_fields import DefaultBattleField
from models import Game, User


class GameDB:
    async def get(self, game_id: int) -> Game:
        return await Game.get(id=game_id).prefetch_related("white_user", "black_user")

    async def create_step_1(self, user: User) -> Game:
        return await Game.create(
            white_user=user,
            black_user=None,
            whose_move="white",
            battle_field=DefaultBattleField().serialize(),
        )

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
