"""Check current prospect data."""
import asyncio
from sqlalchemy import text
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.db.database import engine


async def main():
    async with engine.begin() as conn:
        # Count prospects
        result = await conn.execute(text('SELECT COUNT(*) FROM prospects'))
        print(f'Total prospects: {result.scalar()}')

        # Check FanGraphs IDs
        result = await conn.execute(text('''
            SELECT COUNT(*) FROM prospects WHERE fg_player_id IS NOT NULL
        '''))
        print(f'Prospects with FanGraphs ID: {result.scalar()}')

        # Sample prospects
        result = await conn.execute(text('''
            SELECT name, player_type, team_name, current_level, fg_player_id
            FROM prospects
            WHERE fg_player_id IS NOT NULL
            LIMIT 10
        '''))
        print('\nSample prospects with FG IDs:')
        for row in result:
            print(f'  {row[0]} ({row[1]}) - {row[2]} - FG:{row[4]}')

        # Check existing rankings
        try:
            result = await conn.execute(text('''
                SELECT COUNT(*) FROM prospect_rankings_v6
            '''))
            print(f'\nV6 Rankings: {result.scalar()} prospects')
        except:
            print('\nNo V6 rankings table found')


if __name__ == '__main__':
    asyncio.run(main())
