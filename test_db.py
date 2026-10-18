import asyncio
from sqlalchemy import text
from app.db import engine

async def main():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        print("Connected:", result.scalar())

asyncio.run(main())