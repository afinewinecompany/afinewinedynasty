"""Get column names from milb_game_logs table"""
import asyncio
import asyncpg
from pathlib import Path
import sys
import os

sys.path.append(str(Path(__file__).parent.parent.parent))
os.chdir(Path(__file__).parent.parent.parent)

from app.core.config import settings

async def get_columns():
    db_url = str(settings.SQLALCHEMY_DATABASE_URI)
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(db_url)

    columns = await conn.fetch(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'milb_game_logs'
        ORDER BY ordinal_position
        """
    )

    print("MILB_GAME_LOGS Columns:")
    print("=" * 60)
    for col in columns:
        print(f"{col['column_name']:30} {col['data_type']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(get_columns())