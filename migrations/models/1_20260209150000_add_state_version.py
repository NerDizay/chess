from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE games ADD COLUMN IF NOT EXISTS state_version INTEGER NOT NULL DEFAULT 1;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE games DROP COLUMN IF EXISTS state_version;
    """
