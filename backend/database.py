from dataclasses import dataclass

from environs import Env
from tortoise import Tortoise


@dataclass(frozen=True)
class DatabaseSettings:
    database_url: str
    generate_schemas: bool


def get_database_settings() -> DatabaseSettings:
    env = Env()
    env.read_env()
    return DatabaseSettings(
        database_url=env.str("DATABASE_URL"),
        generate_schemas=env.bool("DB_GENERATE_SCHEMAS", False),
    )


def get_tortoise_config(database_url: str) -> dict[str, object]:
    return {
        "connections": {"default": database_url},
        "apps": {
            "models": {
                "models": ["backend.models", "aerich.models"],
                "default_connection": "default",
            }
        },
    }


_settings = get_database_settings()
TORTOISE_ORM = get_tortoise_config(_settings.database_url)


async def init_database() -> None:
    """Схема: Aerich (`migrations/models/`), затем при флаге — доп. таблицы из моделей."""
    from aerich import Command

    command = Command(tortoise_config=TORTOISE_ORM, app="models", location="migrations")
    await command.init()
    if _settings.generate_schemas:
        await Tortoise.generate_schemas()
    await command.upgrade()


async def close_database() -> None:
    await Tortoise.close_connections()
