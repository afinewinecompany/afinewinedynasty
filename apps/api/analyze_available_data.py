#!/usr/bin/env python3
"""Analyze available data collections for ML training."""

import asyncio
from sqlalchemy import text
from app.db.database import AsyncSessionLocal
import pandas as pd


async def analyze_data_collections():
    """Comprehensive analysis of available data for ML."""
    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("AVAILABLE DATA COLLECTIONS FOR ML TRAINING")
        print("=" * 80)

        # 1. MiLB Game Logs Summary
        print("\n1. MiLB GAME LOGS DATA:")
        result = await db.execute(text("""
            SELECT
                COUNT(DISTINCT mlb_player_id) as total_players,
                COUNT(*) as total_games,
                MIN(season) as earliest_season,
                MAX(season) as latest_season,
                COUNT(DISTINCT season) as num_seasons,
                SUM(CASE WHEN hits IS NOT NULL THEN 1 ELSE 0 END) as hitting_games,
                SUM(CASE WHEN innings_pitched IS NOT NULL THEN 1 ELSE 0 END) as pitching_games,
                COUNT(DISTINCT level) as num_levels
            FROM milb_game_logs
            WHERE mlb_player_id IS NOT NULL
        """))
        row = result.fetchone()
        print(f"  Total Players: {row.total_players:,}")
        print(f"  Total Games: {row.total_games:,}")
        print(f"  Date Range: {row.earliest_season}-{row.latest_season} ({row.num_seasons} seasons)")
        print(f"  Hitting Games: {row.hitting_games:,}")
        print(f"  Pitching Games: {row.pitching_games:,}")
        print(f"  Levels Tracked: {row.num_levels}")

        # 2. MLB Game Logs Check
        print("\n2. MLB GAME LOGS DATA:")
        try:
            result = await db.execute(text("""
                SELECT
                    COUNT(DISTINCT mlb_player_id) as total_players,
                    COUNT(*) as total_games,
                    MIN(season) as earliest_season,
                    MAX(season) as latest_season
                FROM mlb_game_logs
                WHERE mlb_player_id IS NOT NULL
            """))
            row = result.fetchone()
            print(f"  Total MLB Players: {row.total_players:,}")
            print(f"  Total MLB Games: {row.total_games:,}")
            print(f"  Date Range: {row.earliest_season}-{row.latest_season}")
        except:
            print("  ⚠️  MLB game logs table not found or empty")

        # 3. Statcast Data Check
        print("\n3. STATCAST DATA:")
        try:
            result = await db.execute(text("""
                SELECT
                    COUNT(DISTINCT player_id) as total_players,
                    COUNT(*) as total_records,
                    MIN(game_year) as earliest_year,
                    MAX(game_year) as latest_year,
                    AVG(launch_speed) as avg_exit_velo,
                    AVG(launch_angle) as avg_launch_angle
                FROM statcast_data
            """))
            row = result.fetchone()
            if row and row.total_players:
                print(f"  Total Players: {row.total_players:,}")
                print(f"  Total Records: {row.total_records:,}")
                print(f"  Years: {row.earliest_year}-{row.latest_year}")
                print(f"  Avg Exit Velocity: {row.avg_exit_velo:.1f} mph")
                print(f"  Avg Launch Angle: {row.avg_launch_angle:.1f}°")
            else:
                print("  No Statcast data available")
        except:
            print("  Statcast table not found")

        # 4. Fangraphs Data Check
        print("\n4. FANGRAPHS DATA:")
        try:
            result = await db.execute(text("""
                SELECT
                    COUNT(DISTINCT player_id) as total_players,
                    COUNT(*) as total_records,
                    MIN(season) as earliest_season,
                    MAX(season) as latest_season,
                    AVG(wrc_plus) as avg_wrc_plus,
                    AVG(woba) as avg_woba
                FROM fangraphs_milb_stats
                WHERE wrc_plus IS NOT NULL
            """))
            row = result.fetchone()
            if row and row.total_players:
                print(f"  Total Players: {row.total_players:,}")
                print(f"  Total Records: {row.total_records:,}")
                print(f"  Seasons: {row.earliest_season}-{row.latest_season}")
                print(f"  Avg wRC+: {row.avg_wrc_plus:.0f}")
                print(f"  Avg wOBA: {row.avg_woba:.3f}")
            else:
                print("  No Fangraphs data with wRC+/wOBA")
        except:
            print("  Fangraphs table not found")

        # 5. Players with both MiLB and MLB data
        print("\n5. PLAYERS WITH MLB OUTCOMES (Y LABELS):")
        result = await db.execute(text("""
            WITH milb_players AS (
                SELECT DISTINCT
                    mlb_player_id,
                    MIN(season) as first_milb_season,
                    MAX(season) as last_milb_season,
                    COUNT(DISTINCT season) as milb_seasons
                FROM milb_game_logs
                WHERE mlb_player_id IS NOT NULL
                GROUP BY mlb_player_id
            ),
            mlb_players AS (
                SELECT DISTINCT
                    mlb_player_id,
                    MIN(season) as first_mlb_season,
                    MAX(season) as last_mlb_season,
                    COUNT(DISTINCT season) as mlb_seasons
                FROM mlb_game_logs
                WHERE mlb_player_id IS NOT NULL
                GROUP BY mlb_player_id
            )
            SELECT
                COUNT(*) as players_with_both,
                AVG(milb_seasons) as avg_milb_seasons,
                AVG(mlb_seasons) as avg_mlb_seasons
            FROM milb_players mi
            INNER JOIN mlb_players ml ON mi.mlb_player_id = ml.mlb_player_id
        """))
        row = result.fetchone()
        if row and row.players_with_both:
            print(f"  Players with MiLB → MLB data: {row.players_with_both:,}")
            print(f"  Avg MiLB Seasons: {row.avg_milb_seasons:.1f}")
            print(f"  Avg MLB Seasons: {row.avg_mlb_seasons:.1f}")
        else:
            print("  No players with both MiLB and MLB data")

        # 6. Age Distribution
        print("\n6. AGE DATA AVAILABILITY:")
        result = await db.execute(text("""
            WITH player_ages AS (
                SELECT
                    mlb_player_id,
                    season,
                    season - EXTRACT(YEAR FROM MIN(game_date)) + 20 as estimated_age
                FROM milb_game_logs
                WHERE mlb_player_id IS NOT NULL
                GROUP BY mlb_player_id, season
            )
            SELECT
                MIN(estimated_age) as min_age,
                MAX(estimated_age) as max_age,
                AVG(estimated_age) as avg_age,
                COUNT(*) as total_player_seasons
            FROM player_ages
        """))
        row = result.fetchone()
        print(f"  Estimated Age Range: {row.min_age:.0f}-{row.max_age:.0f}")
        print(f"  Average Age: {row.avg_age:.1f}")
        print(f"  Player-Season Records: {row.total_player_seasons:,}")

        # 7. Statistical Coverage
        print("\n7. STATISTICAL COMPLETENESS:")
        result = await db.execute(text("""
            SELECT
                -- Hitting stats
                COUNT(CASE WHEN batting_avg IS NOT NULL THEN 1 END) as has_avg,
                COUNT(CASE WHEN obp IS NOT NULL THEN 1 END) as has_obp,
                COUNT(CASE WHEN slg IS NOT NULL THEN 1 END) as has_slg,
                COUNT(CASE WHEN ops IS NOT NULL THEN 1 END) as has_ops,
                COUNT(CASE WHEN babip IS NOT NULL THEN 1 END) as has_babip,
                -- Pitching stats
                COUNT(CASE WHEN era IS NOT NULL THEN 1 END) as has_era,
                COUNT(CASE WHEN whip IS NOT NULL THEN 1 END) as has_whip,
                COUNT(CASE WHEN strikeouts_per_9inn IS NOT NULL THEN 1 END) as has_k9,
                COUNT(*) as total_games
            FROM milb_game_logs
            WHERE season IN (2024, 2025)
        """))
        row = result.fetchone()
        print(f"  Games with AVG: {row.has_avg:,} ({row.has_avg/row.total_games*100:.1f}%)")
        print(f"  Games with OBP: {row.has_obp:,} ({row.has_obp/row.total_games*100:.1f}%)")
        print(f"  Games with SLG: {row.has_slg:,} ({row.has_slg/row.total_games*100:.1f}%)")
        print(f"  Games with OPS: {row.has_ops:,} ({row.has_ops/row.total_games*100:.1f}%)")
        print(f"  Games with ERA: {row.has_era:,} ({row.has_era/row.total_games*100:.1f}%)")
        print(f"  Games with WHIP: {row.has_whip:,} ({row.has_whip/row.total_games*100:.1f}%)")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(analyze_data_collections())