#!/usr/bin/env python3
"""Check the status of 2024 and 2025 MiLB data collection."""

import asyncio
from sqlalchemy import text
from app.db.database import AsyncSessionLocal


async def check_collection_status():
    """Check 2024 and 2025 collection progress."""
    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("2024/2025 MiLB DATA COLLECTION STATUS")
        print("=" * 80)

        # Overall stats by season
        print("\n1. OVERALL GAME COUNTS BY SEASON:")
        result = await db.execute(text("""
            SELECT
                season,
                COUNT(DISTINCT mlb_player_id) as unique_players,
                COUNT(DISTINCT prospect_id) as linked_prospects,
                COUNT(*) as total_games,
                COUNT(CASE WHEN hits IS NOT NULL THEN 1 END) as hitting_games,
                COUNT(CASE WHEN innings_pitched IS NOT NULL THEN 1 END) as pitching_games
            FROM milb_game_logs
            WHERE season IN (2024, 2025)
            GROUP BY season
            ORDER BY season DESC
        """))

        for row in result:
            print(f"\n  Season {row.season}:")
            print(f"    Total Games: {row.total_games:,}")
            print(f"    Unique Players: {row.unique_players:,}")
            print(f"    Linked to Prospects: {row.linked_prospects:,} ({row.linked_prospects/row.unique_players*100:.1f}%)")
            print(f"    Hitting Games: {row.hitting_games:,}")
            print(f"    Pitching Games: {row.pitching_games:,}")

        # By level breakdown
        print("\n2. 2024 DATA BY LEVEL:")
        result = await db.execute(text("""
            SELECT
                COALESCE(level, 'Unknown') as level,
                COUNT(DISTINCT mlb_player_id) as players,
                COUNT(*) as games,
                COUNT(CASE WHEN hits IS NOT NULL THEN 1 END) as hitting_games,
                COUNT(CASE WHEN innings_pitched IS NOT NULL THEN 1 END) as pitching_games
            FROM milb_game_logs
            WHERE season = 2024
            GROUP BY level
            ORDER BY
                CASE level
                    WHEN 'AAA' THEN 1
                    WHEN 'AA' THEN 2
                    WHEN 'A+' THEN 3
                    WHEN 'A' THEN 4
                    WHEN 'Rookie' THEN 5
                    WHEN 'Rookie+' THEN 6
                    WHEN 'Winter' THEN 7
                    ELSE 8
                END
        """))

        print(f"  {'Level':10} | {'Players':>8} | {'Total':>10} | {'Hitting':>10} | {'Pitching':>10}")
        print("  " + "-" * 60)
        for row in result:
            print(f"  {row.level:10} | {row.players:>8,} | {row.games:>10,} | {row.hitting_games:>10,} | {row.pitching_games:>10,}")

        print("\n3. 2025 DATA BY LEVEL:")
        result = await db.execute(text("""
            SELECT
                COALESCE(level, 'Unknown') as level,
                COUNT(DISTINCT mlb_player_id) as players,
                COUNT(*) as games,
                COUNT(CASE WHEN hits IS NOT NULL THEN 1 END) as hitting_games,
                COUNT(CASE WHEN innings_pitched IS NOT NULL THEN 1 END) as pitching_games
            FROM milb_game_logs
            WHERE season = 2025
            GROUP BY level
            ORDER BY
                CASE level
                    WHEN 'AAA' THEN 1
                    WHEN 'AA' THEN 2
                    WHEN 'A+' THEN 3
                    WHEN 'A' THEN 4
                    WHEN 'Rookie' THEN 5
                    WHEN 'Rookie+' THEN 6
                    WHEN 'Winter' THEN 7
                    ELSE 8
                END
        """))

        print(f"  {'Level':10} | {'Players':>8} | {'Total':>10} | {'Hitting':>10} | {'Pitching':>10}")
        print("  " + "-" * 60)
        for row in result:
            print(f"  {row.level:10} | {row.players:>8,} | {row.games:>10,} | {row.hitting_games:>10,} | {row.pitching_games:>10,}")

        # Check for gaps
        print("\n4. DATA COMPLETENESS CHECK:")

        # Players from resume files not in DB
        resume_2024_players = [679938, 606213, 606216, 622603, 671760]  # First 5 from resume
        resume_2025_players = [688162, 688214, 688230, 622694, 622766]  # First 5 from resume

        result = await db.execute(text("""
            SELECT
                mlb_player_id,
                COUNT(*) as games,
                MIN(game_date) as first_game,
                MAX(game_date) as last_game
            FROM milb_game_logs
            WHERE mlb_player_id = ANY(:player_ids)
            AND season = 2024
            GROUP BY mlb_player_id
        """), {"player_ids": resume_2024_players})

        found_2024 = {row.mlb_player_id for row in result}
        missing_2024 = set(resume_2024_players) - found_2024

        if missing_2024:
            print(f"  WARNING: {len(missing_2024)} players from 2024 resume not in DB: {missing_2024}")
        else:
            print(f"  OK: All sampled 2024 resume players found in DB")

        result = await db.execute(text("""
            SELECT
                mlb_player_id,
                COUNT(*) as games
            FROM milb_game_logs
            WHERE mlb_player_id = ANY(:player_ids)
            AND season = 2025
            GROUP BY mlb_player_id
        """), {"player_ids": resume_2025_players})

        found_2025 = {row.mlb_player_id for row in result}
        missing_2025 = set(resume_2025_players) - found_2025

        if missing_2025:
            print(f"  WARNING: {len(missing_2025)} players from 2025 resume not in DB: {missing_2025}")
        else:
            print(f"  OK: All sampled 2025 resume players found in DB")

        # Check for recent updates
        print("\n5. RECENT DATA UPDATES:")
        result = await db.execute(text("""
            SELECT
                DATE(created_at) as update_date,
                COUNT(DISTINCT mlb_player_id) as players_added,
                COUNT(*) as games_added,
                MIN(season) as min_season,
                MAX(season) as max_season
            FROM milb_game_logs
            WHERE created_at >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY update_date DESC
        """))

        recent_updates = result.fetchall()
        if recent_updates:
            print(f"  {'Date':12} | {'Players':>8} | {'Games':>10} | {'Seasons':>12}")
            print("  " + "-" * 50)
            for row in recent_updates:
                seasons = f"{row.min_season}-{row.max_season}" if row.min_season != row.max_season else str(row.min_season)
                print(f"  {str(row.update_date):12} | {row.players_added:>8} | {row.games_added:>10,} | {seasons:>12}")
        else:
            print("  No updates in the last 7 days")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(check_collection_status())