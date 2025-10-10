"""Count distinct pitchers in the dataset."""
import asyncio
from sqlalchemy import text
from app.db.database import engine

async def count_pitchers():
    async with engine.begin() as conn:
        # Count distinct pitchers (players with pitching games)
        result = await conn.execute(text('''
            SELECT COUNT(DISTINCT mlb_player_id)
            FROM milb_game_logs
            WHERE games_pitched > 0
        '''))
        pitcher_count = result.scalar()

        # Also get breakdown by position type
        result2 = await conn.execute(text('''
            SELECT
                CASE
                    WHEN MAX(games_pitched) > 0 AND MAX(games_played) > MAX(games_pitched) THEN 'Two-Way Player'
                    WHEN MAX(games_pitched) > 0 THEN 'Pitcher Only'
                    ELSE 'Position Player'
                END as player_type,
                COUNT(DISTINCT mlb_player_id) as count
            FROM milb_game_logs
            GROUP BY mlb_player_id
        '''))
        rows = result2.fetchall()

        # Aggregate the counts
        breakdown = {}
        for row in rows:
            player_type = row[0]
            breakdown[player_type] = breakdown.get(player_type, 0) + 1

        print(f'Total pitchers (players with games_pitched > 0): {pitcher_count:,}')
        print(f'\nBreakdown by player type:')
        for player_type, count in sorted(breakdown.items()):
            print(f'  {player_type}: {count:,}')

if __name__ == "__main__":
    asyncio.run(count_pitchers())
