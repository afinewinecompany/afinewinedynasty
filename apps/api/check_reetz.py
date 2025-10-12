import asyncio
from sqlalchemy import text
from app.db.database import engine

async def check():
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                m.season,
                m.level,
                COUNT(*) as games,
                SUM(m.plate_appearances) as pa,
                AVG(m.ops) as ops,
                AVG(m.batting_avg) as ba,
                SUM(m.home_runs) as hr
            FROM milb_game_logs m
            INNER JOIN prospects p ON m.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
            WHERE p.name = 'Jakson Reetz'
            AND m.data_source = 'mlb_stats_api_gamelog'
            GROUP BY m.season, m.level
            ORDER BY m.season DESC, m.level
        """))

        print('\n=== JAKSON REETZ MiLB STATS ===')
        print(f"{'Season':<8} {'Level':<6} {'Games':<8} {'PAs':<8} {'OPS':<8} {'BA':<8} {'HR':<6}")
        print('-' * 60)
        for row in result:
            print(f'{row[0]:<8} {row[1]:<6} {row[2]:<8} {row[3]:<8.0f} {row[4]:<8.3f} {row[5]:<8.3f} {row[6]:<6.0f}')

        # Check MLB stats
        result2 = await conn.execute(text("""
            SELECT
                COUNT(*) as games,
                SUM(at_bats) as ab,
                AVG(ops) as ops
            FROM mlb_game_logs
            WHERE mlb_player_id = (SELECT mlb_player_id FROM prospects WHERE name = 'Jakson Reetz' LIMIT 1)
        """))

        print('\n=== JAKSON REETZ MLB STATS ===')
        for row in result2:
            print(f'Games: {row[0]}, AB: {row[1]}, OPS: {row[2] if row[2] else "N/A"}')

asyncio.run(check())
