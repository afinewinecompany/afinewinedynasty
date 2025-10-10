#!/usr/bin/env python3
"""Check data integrity and linkages between MiLB and MLB data."""

import asyncio
import sys
sys.path.insert(0, '.')

from app.db.database import AsyncSessionLocal
from sqlalchemy import text


async def check_data_integrity():
    """Perform comprehensive data integrity checks."""
    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("DATA INTEGRITY CHECK REPORT")
        print("=" * 80)

        # Check MiLB game logs
        print("\n1. MiLB GAME LOGS TABLE:")
        result = await db.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT prospect_id) as prospects,
                COUNT(DISTINCT mlb_player_id) as mlb_ids,
                COUNT(DISTINCT season) as seasons,
                MIN(season) as earliest_season,
                MAX(season) as latest_season,
                COUNT(CASE WHEN prospect_id IS NULL THEN 1 END) as null_prospects,
                COUNT(CASE WHEN mlb_player_id IS NULL THEN 1 END) as null_mlb_ids
            FROM milb_game_logs
        """))
        row = result.fetchone()
        if row and row.total > 0:
            print(f"  Total Records: {row.total:,}")
            print(f"  Unique Prospects: {row.prospects:,}")
            print(f"  Unique MLB IDs: {row.mlb_ids:,}")
            print(f"  Seasons: {row.earliest_season} - {row.latest_season} ({row.seasons} seasons)")
            print(f"  NULL prospect_id: {row.null_prospects:,}")
            print(f"  NULL mlb_player_id: {row.null_mlb_ids:,}")
        else:
            print("  ⚠️  No data in milb_game_logs table")

        # Check MLB game logs
        print("\n2. MLB GAME LOGS TABLE:")
        result = await db.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT prospect_id) as prospects,
                COUNT(DISTINCT mlb_player_id) as mlb_ids,
                COUNT(DISTINCT season) as seasons,
                MIN(season) as earliest_season,
                MAX(season) as latest_season
            FROM mlb_game_logs
        """))
        row = result.fetchone()
        if row and row.total > 0:
            print(f"  Total Records: {row.total:,}")
            print(f"  Unique Prospects: {row.prospects:,}")
            print(f"  Unique MLB IDs: {row.mlb_ids:,}")
            print(f"  Seasons: {row.earliest_season} - {row.latest_season} ({row.seasons} seasons)")
        else:
            print("  ⚠️  No data in mlb_game_logs table")

        # Check Prospects table
        print("\n3. PROSPECTS TABLE:")
        result = await db.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT mlb_id) as mlb_ids,
                COUNT(CASE WHEN mlb_id IS NULL THEN 1 END) as null_mlb_ids,
                COUNT(DISTINCT organization) as teams,
                COUNT(DISTINCT position) as positions,
                COUNT(DISTINCT level) as levels
            FROM prospects
        """))
        row = result.fetchone()
        print(f"  Total Prospects: {row.total:,}")
        print(f"  With MLB ID: {row.mlb_ids:,}")
        print(f"  Without MLB ID: {row.null_mlb_ids:,}")
        print(f"  Teams: {row.teams}")
        print(f"  Positions: {row.positions}")
        print(f"  Levels: {row.levels}")

        # Check linkage between tables
        print("\n4. DATA LINKAGE ANALYSIS:")

        # MiLB prospects with matching prospect record
        result = await db.execute(text("""
            SELECT
                COUNT(DISTINCT milb.prospect_id) as linked_prospects,
                COUNT(DISTINCT milb.mlb_player_id) as linked_mlb_ids
            FROM milb_game_logs milb
            INNER JOIN prospects p ON milb.prospect_id = p.id
        """))
        row = result.fetchone()
        print(f"  MiLB prospects with valid prospect record: {row.linked_prospects:,}")

        # Orphaned MiLB records
        result = await db.execute(text("""
            SELECT COUNT(DISTINCT milb.prospect_id) as orphaned
            FROM milb_game_logs milb
            LEFT JOIN prospects p ON milb.prospect_id = p.id
            WHERE p.id IS NULL AND milb.prospect_id IS NOT NULL
        """))
        row = result.fetchone()
        print(f"  ⚠️  Orphaned MiLB records (no prospect): {row.orphaned:,}")

        # Check MLB ID consistency
        result = await db.execute(text("""
            SELECT COUNT(*) as mismatched
            FROM milb_game_logs milb
            INNER JOIN prospects p ON milb.prospect_id = p.id
            WHERE p.mlb_id IS NOT NULL
            AND milb.mlb_player_id IS NOT NULL
            AND CAST(p.mlb_id AS INTEGER) != milb.mlb_player_id
        """))
        row = result.fetchone()
        print(f"  ⚠️  Mismatched MLB IDs between tables: {row.mismatched:,}")

        # Players who made it to MLB
        result = await db.execute(text("""
            SELECT COUNT(DISTINCT milb.prospect_id) as mlb_graduates
            FROM milb_game_logs milb
            WHERE EXISTS (
                SELECT 1 FROM mlb_game_logs mlb_g
                WHERE mlb_g.mlb_player_id = milb.mlb_player_id
            )
        """))
        row = result.fetchone()
        print(f"  Players with both MiLB and MLB data: {row.mlb_graduates:,}")

        # Check Fangraphs data
        print("\n5. FANGRAPHS DATA:")
        result = await db.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT player_id) as players,
                COUNT(DISTINCT season) as seasons,
                MIN(season) as earliest,
                MAX(season) as latest
            FROM fangraphs_milb_stats
        """))
        row = result.fetchone()
        if row and row.total > 0:
            print(f"  Total Records: {row.total:,}")
            print(f"  Unique Players: {row.players:,}")
            print(f"  Seasons: {row.earliest} - {row.latest}")
        else:
            print("  ⚠️  No Fangraphs data found")

        # Check Statcast data
        print("\n6. STATCAST DATA:")
        result = await db.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT player_id) as players,
                COUNT(DISTINCT game_year) as seasons
            FROM statcast_data
        """))
        row = result.fetchone()
        if row and row.total > 0:
            print(f"  Total Records: {row.total:,}")
            print(f"  Unique Players: {row.players:,}")
            print(f"  Seasons: {row.seasons}")
        else:
            print("  ⚠️  No Statcast data found")

        # Check ML Predictions
        print("\n7. ML PREDICTIONS:")
        result = await db.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT prospect_id) as prospects,
                COUNT(DISTINCT model_version) as models,
                COUNT(DISTINCT prediction_type) as types
            FROM ml_predictions
        """))
        row = result.fetchone()
        if row and row.total > 0:
            print(f"  Total Predictions: {row.total:,}")
            print(f"  Prospects with Predictions: {row.prospects:,}")
            print(f"  Model Versions: {row.models}")
            print(f"  Prediction Types: {row.types}")
        else:
            print("  ⚠️  No ML predictions found")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(check_data_integrity())