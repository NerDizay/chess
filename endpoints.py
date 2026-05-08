from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

from database import close_database, init_database
from repository import GameDB
from services import GameService

game_service = GameService(GameDB())


class CreateGameRequest(BaseModel):
    user_name: str = Field(min_length=1, max_length=30)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_database()
    yield
    await close_database()


app = FastAPI(title="Chess API", lifespan=lifespan)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/games")
async def create_game(payload: CreateGameRequest) -> dict[str, object]:
    return await game_service.create_game(user_name=payload.user_name)


@app.get("/games/{game_id}")
async def get_game(game_id: int) -> dict[str, object]:
    return await game_service.get(game_id)
