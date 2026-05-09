from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE games ADD COLUMN IF NOT EXISTS winner_side VARCHAR(5);
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE games DROP COLUMN IF EXISTS winner_side;
    """
