import pytest
from asgi_lifespan import LifespanManager
from uuid_utils.compat import uuid4

from backend.endpoints import app
from backend.exceptions import UserNotFoundError
from backend.models import User
from backend.repositories import GameDB, UserRepository
from backend.services import GameService, UserService


@pytest.fixture
async def game_service_ready():
    async with LifespanManager(app):
        yield GameService(GameDB(), UserService(UserRepository()))


@pytest.mark.asyncio
async def test_game_service_create_game(game_service_ready: GameService):
    user = await User.create(name="bob")
    payload = await game_service_ready.create_game(user.id)
    assert payload["id"] >= 1
    assert payload["white_user"]["name"] == "bob"
    assert payload["white_user"]["id"] == str(user.id)
    assert payload["black_user"] is None


@pytest.mark.asyncio
async def test_game_service_user_not_found(game_service_ready: GameService):
    with pytest.raises(UserNotFoundError):
        await game_service_ready.create_game(uuid4())
