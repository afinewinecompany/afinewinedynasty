"""Debug why we only found 20/37 training samples."""

import asyncio
import asyncpg

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


async def debug():
    conn = await asyncpg.connect(DATABASE_URL)

    # Find all prospects who SHOULD be in training data
    query = """
        WITH candidates AS (
            SELECT DISTINCT
                p.id,
                p.mlb_player_id::integer as mlb_player_id,
                p.name,
                p.position,
                COUNT(DISTINCT milb.id) as milb_game_count,
                COUNT(DISTINCT mlb.id) as mlb_game_count,
                MIN(mlb.season) as mlb_debut
            FROM prospects p
            INNER JOIN milb_game_logs milb
                ON p.mlb_player_id::integer = milb.mlb_player_id
            INNER JOIN mlb_game_logs mlb
                ON p.mlb_player_id::integer = mlb.mlb_player_id
            WHERE p.mlb_player_id IS NOT NULL
                AND p.mlb_player_id ~ '^[0-9]+$'
                AND milb.season BETWEEN 2018 AND 2023
                AND milb.plate_appearances > 0
                AND mlb.season >= 2021
                AND p.position NOT IN ('SP', 'RP', 'LHP', 'RHP')
            GROUP BY p.id, p.mlb_player_id, p.name, p.position
            HAVING COUNT(DISTINCT mlb.id) >= 20
        )
        SELECT * FROM candidates
        ORDER BY mlb_debut, mlb_game_count DESC
    """

    rows = await conn.fetch(query)

    print(f"Total prospects matching criteria: {len(rows)}")
    print("\nFirst 10:")
    for r in rows[:10]:
        print(f"  {r['name']:30s} ({r['position']:3s}) - MLB: {r['mlb_game_count']:4d} games, Debut: {r['mlb_debut']}")

    await conn.close()

asyncio.run(debug())
