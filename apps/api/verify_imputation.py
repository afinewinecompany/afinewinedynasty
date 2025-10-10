"""Verify imputed Statcast data."""
import asyncio
from sqlalchemy import text
import sys
sys.path.insert(0, '.')
from app.db.database import engine

async def main():
    async with engine.connect() as conn:
        result = await conn.execute(text('''
            SELECT mlb_player_id, avg_ev, max_ev, hard_hit_pct, barrel_pct
            FROM milb_statcast_metrics_imputed
            ORDER BY barrel_pct DESC
            LIMIT 10
        '''))
        print('Top 10 by Barrel%:')
        for row in result:
            print(f'  Player {row[0]}: EV={row[1]:.1f}, MaxEV={row[2]:.1f}, HH%={row[3]:.1f}, Barrel%={row[4]:.1f}')

asyncio.run(main())
