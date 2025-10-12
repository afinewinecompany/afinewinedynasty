"""Quick check of imputation table status."""
import asyncio
from sqlalchemy import text
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.db.database import engine

async def main():
    async with engine.begin() as conn:
        result = await conn.execute(text('SELECT COUNT(*) FROM milb_statcast_metrics_imputed'))
        count = result.scalar()
        print(f'Records in milb_statcast_metrics_imputed: {count}')

if __name__ == '__main__':
    asyncio.run(main())
