import asyncio
from sqlalchemy import text
from app.db.database import engine

async def debug():
    async with engine.begin() as conn:
        # Step 1: Check if he's in prospects table
        result = await conn.execute(text("""
            SELECT mlb_player_id, name, position, birth_date
            FROM prospects
            WHERE mlb_player_id = 702544
        """))
        row = result.fetchone()
        print('\n=== STEP 1: Prospects Table ===')
        if row:
            print(f'✓ Found: {row[1]}, Pos: {row[2]}, Birth: {row[3]}')
        else:
            print('✗ Not in prospects table')
            return

        # Step 2: Check ALL his game logs (any season)
        result = await conn.execute(text("""
            SELECT
                season,
                level,
                COUNT(*) as games,
                SUM(plate_appearances) as pa
            FROM milb_game_logs
            WHERE mlb_player_id = 702544
            GROUP BY season, level
            ORDER BY season DESC, level
        """))

        print('\n=== STEP 2: ALL MiLB Game Logs (Any Season) ===')
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f'  {row[0]} {row[1]}: {row[2]} games, {row[3]:.0f} PA')
        else:
            print('  ✗ NO GAME LOGS FOUND')

        # Step 3: Check 2024-2025 game logs specifically
        result = await conn.execute(text("""
            SELECT
                season,
                level,
                COUNT(*) as games,
                SUM(plate_appearances) as pa
            FROM milb_game_logs
            WHERE mlb_player_id = 702544
            AND season IN (2024, 2025)
            GROUP BY season, level
            ORDER BY season DESC, level
        """))

        print('\n=== STEP 3: 2024-2025 Game Logs ===')
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f'  {row[0]} {row[1]}: {row[2]} games, {row[3]:.0f} PA')
        else:
            print('  ✗ NO 2024-2025 GAME LOGS')

        # Step 4: Check the ranking script's JOIN query
        result = await conn.execute(text("""
            SELECT
                m.mlb_player_id,
                m.season,
                m.level,
                COUNT(*) as games,
                SUM(m.plate_appearances) as total_pa
            FROM milb_game_logs m
            INNER JOIN prospects p ON m.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
            WHERE p.mlb_player_id = 702544
            AND m.data_source = 'mlb_stats_api_gamelog'
            AND p.birth_date IS NOT NULL
            AND (m.games_pitched IS NULL OR m.games_pitched = 0)
            GROUP BY m.mlb_player_id, m.season, m.level
            ORDER BY m.season DESC, m.level
        """))

        print('\n=== STEP 4: Ranking Query JOIN Results ===')
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f'  {row[1]} {row[2]}: {row[3]} games, {row[4]:.0f} PA')
        else:
            print('  ✗ NO RESULTS FROM RANKING QUERY')

        # Step 5: Check if birth_date is the issue
        result = await conn.execute(text("""
            SELECT birth_date FROM prospects WHERE mlb_player_id = 702544
        """))
        row = result.fetchone()
        print(f'\n=== STEP 5: Birth Date Check ===')
        print(f'  Birth date: {row[0] if row and row[0] else "NULL - THIS IS THE PROBLEM!"}')

asyncio.run(debug())
