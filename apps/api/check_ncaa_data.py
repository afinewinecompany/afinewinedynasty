import asyncio
from sqlalchemy import text
from app.db.database import engine

async def check_levels():
    """Check what levels exist in the database."""
    async with engine.begin() as conn:
        # Check all levels in database
        result = await conn.execute(text("""
            SELECT
                level,
                COUNT(*) as game_count,
                COUNT(DISTINCT mlb_player_id) as player_count,
                MIN(season) as first_season,
                MAX(season) as last_season
            FROM milb_game_logs
            GROUP BY level
            ORDER BY level
        """))

        print('\n=== LEVELS IN DATABASE ===')
        print(f"{'Level':<15} {'Games':>10} {'Players':>10} {'Seasons':>15}")
        print('-' * 55)
        for row in result:
            print(f'{row[0]:<15} {row[1]:>10,} {row[2]:>10,} {row[3]}-{row[4]}')

        # Check for any suspicious team names (college/NCAA indicators)
        result = await conn.execute(text("""
            SELECT DISTINCT opponent_name
            FROM milb_game_logs
            WHERE opponent_name ILIKE '%university%'
               OR opponent_name ILIKE '%college%'
               OR opponent_name ILIKE '%state%'
               OR level NOT IN ('AAA', 'AA', 'A+', 'A', 'Rookie', 'Rookie+', 'ROK', 'ACL', 'DSL', 'FCL')
            ORDER BY opponent_name
            LIMIT 50
        """))

        ncaa_teams = [row[0] for row in result]

        if ncaa_teams:
            print('\n⚠️  POTENTIAL NCAA/COLLEGE TEAMS FOUND:')
            for team in ncaa_teams:
                print(f'  - {team}')
        else:
            print('\n✅ No NCAA/college teams detected')

        # Check for valid MiLB levels only
        result = await conn.execute(text("""
            SELECT COUNT(*) as count
            FROM milb_game_logs
            WHERE level NOT IN ('AAA', 'AA', 'A+', 'A', 'Rookie', 'Rookie+', 'ROK', 'ACL', 'DSL', 'FCL')
        """))

        invalid_count = result.scalar()

        if invalid_count > 0:
            print(f'\n⚠️  Found {invalid_count:,} games with invalid levels')
        else:
            print('\n✅ All games have valid MiLB levels')

asyncio.run(check_levels())
