from domain.game import Game as DomainGame
from domain.game import SerializedBattleField
from domain.user import User as DomainUser
from models import Game, User
from repository import GameDB


class GameService:
    def __init__(self, game_db: GameDB) -> None:
        self.game_db = game_db

    async def get(self, game_id: int) -> dict[str, object]:
        game = await self.game_db.get(game_id)
        white_user = (
            None if game.white_user is None else DomainUser(name=game.white_user.name, team="white")
        )
        black_user = (
            None if game.black_user is None else DomainUser(name=game.black_user.name, team="black")
        )
        domain_game = DomainGame(
            battle_field=SerializedBattleField(data=game.battle_field),
            white_user=white_user,
            black_user=black_user,
            whose_move=game.whose_move,
        )
        serialized_game = domain_game.serialize()
        serialized_game["id"] = game.id
        return serialized_game

    async def create_game(self, user_name: str) -> dict[str, object]:
        user = await User.create(name=user_name)
        game = await self.game_db.create_step_1(user)
        return await self.get(game.id)

    async def create_step_1(self, user: User) -> Game:
        return await self.game_db.create_step_1(user)

    async def create_step_2(self, user: User) -> Game:
        return await self.game_db.create_step_2(user)
