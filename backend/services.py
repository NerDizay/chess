from uuid import UUID

import backend.domain as domain
import backend.exceptions as exceptions
import backend.models as models
import backend.repositories as repositories


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
                team="white",
                id=str(game.white_user.id),
            )
        )
        black_user = (
            None
            if game.black_user is None
            else domain.user.User(
                name=game.black_user.name,
                team="black",
                id=str(game.black_user.id),
            )
        )
        chess_game = domain.game.Game(
            battle_field=domain.game.SerializedBattleField(data=game.battle_field),
            white_user=white_user,
            black_user=black_user,
            whose_move=game.whose_move,
        )
        serialized_game = chess_game.serialize()
        serialized_game["id"] = game.id
        return serialized_game

    async def create_game(self, user_id: UUID) -> dict[str, object]:
        await self.user_service.get_user(user_id)
        game = await self.game_db.create_step_1(user_id)
        return await self.as_dict(game)

    async def create_step_1(self, user: models.User) -> models.Game:
        return await self.game_db.create_step_1(user.id)

    async def create_step_2(self, user: models.User) -> models.Game:
        return await self.game_db.create_step_2(user)
