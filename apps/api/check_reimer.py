import asyncio
from sqlalchemy import text
from app.db.database import engine

async def check():
    async with engine.begin() as conn:
        # Find player
        result = await conn.execute(text("""
            SELECT mlb_player_id, name, position, birth_date
            FROM prospects
            WHERE name ILIKE '%reimer%' OR name ILIKE '%reimber%'
        """))

        print('\n=== JACOB REIMER/REIMBER - PLAYER INFO ===')
        players = result.fetchall()
        for p in players:
            print(f'ID: {p[0]}, Name: {p[1]}, Pos: {p[2]}, Birth: {p[3]}')

        if not players:
            print('Not found')
            return

        player_id = players[0][0]

        # Get 2024-2025 stats
        result = await conn.execute(text("""
            SELECT
                season,
                level,
                COUNT(*) as games,
                SUM(plate_appearances) as pa,
                SUM(at_bats) as ab,
                SUM(hits) as h,
                SUM(home_runs) as hr,
                SUM(walks) as bb,
                SUM(strikeouts) as so,
                AVG(batting_avg) as ba,
                AVG(on_base_pct) as obp,
                AVG(slugging_pct) as slg,
                AVG(ops) as ops
            FROM milb_game_logs
            WHERE mlb_player_id = :player_id
            AND season >= 2024
            GROUP BY season, level
            ORDER BY season DESC, level
        """), {'player_id': player_id})

        print('\n=== 2024-2025 MiLB STATS ===')
        print(f"{'Season':<8} {'Level':<6} {'G':<5} {'PA':<6} {'AB':<6} {'H':<5} {'HR':<5} {'BB':<5} {'SO':<5} {'BA':<7} {'OBP':<7} {'SLG':<7} {'OPS':<7}")
        print('-' * 100)
        for row in result:
            print(f'{row[0]:<8} {row[1]:<6} {row[2]:<5} {row[3]:<6.0f} {row[4]:<6.0f} {row[5]:<5.0f} {row[6]:<5.0f} {row[7]:<5.0f} {row[8]:<5.0f} {row[9]:<7.3f} {row[10]:<7.3f} {row[11]:<7.3f} {row[12]:<7.3f}')

        # Get ALL stats
        result = await conn.execute(text("""
            SELECT
                season,
                level,
                SUM(plate_appearances) as pa,
                AVG(ops) as ops
            FROM milb_game_logs
            WHERE mlb_player_id = :player_id
            GROUP BY season, level
            ORDER BY season, level
        """), {'player_id': player_id})

        print('\n=== ALL CAREER STATS ===')
        for row in result:
            print(f'{row[0]} {row[1]}: {row[2]:.0f} PA, {row[3]:.3f} OPS')

asyncio.run(check())
