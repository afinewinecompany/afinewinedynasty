#!/usr/bin/env python3
"""
Collect Full 2024 Prospect Data
================================
Uses raw SQL to avoid ORM relationship issues.

Usage:
    python collect_2024_data.py
"""

import sys
import os
import asyncio
import aiohttp
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import get_db_sync
from sqlalchemy import text


async def fetch_fangraphs_prospects(year: int):
    """Fetch prospect list from Fangraphs."""
    url = "https://www.fangraphs.com/api/prospects/board/prospects-list-combined"

    params = {
        'pos': 'all',
        'lg': '2,4,5,6,7,8,9,10,11,14,12,13,15,16,17,18,30,32,33',
        'stats': 'bat',
        'qual': '0',
        'type': '0',
        'team': '',
        'season': str(year),
        'seasonend': str(year),
        'draft': f'{year+1}prospect',
        'valueheader': 'prospect-new',
        'quickleaderboard': f'{year}all'
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=30) as response:
            if response.status == 200:
                data = await response.json()
                prospects = data.get('dataScout', [])
                return prospects
            return []


def insert_prospect(db, fg_data: dict, year: int):
    """Insert prospect using raw SQL."""
    name = fg_data.get('playerName')
    position = fg_data.get('POS', 'OF')

    # Check if exists
    check_sql = text("SELECT id FROM prospects WHERE name = :name")
    result = db.execute(check_sql, {'name': name})
    existing = result.fetchone()

    if existing:
        return existing[0], False  # Return ID and False (not created)

    # Insert
    insert_sql = text("""
        INSERT INTO prospects (
            name, position, bats, throws,
            fg_player_id, current_organization, current_level,
            created_at, updated_at, data_sources
        ) VALUES (
            :name, :position, :bats, :throws,
            :fg_player_id, :organization, :level,
            NOW(), NOW(), '{}'::json
        ) RETURNING id
    """)

    result = db.execute(insert_sql, {
        'name': name,
        'position': position,
        'bats': fg_data.get('Bats'),
        'throws': fg_data.get('Throws'),
        'fg_player_id': fg_data.get('PlayerId'),
        'organization': fg_data.get('OrgName'),
        'level': fg_data.get('Level'),
    })

    prospect_id = result.fetchone()[0]
    db.commit()

    return prospect_id, True  # Return ID and True (created)


def insert_scouting_grade(db, prospect_id: int, fg_data: dict, year: int):
    """Insert scouting grade using raw SQL."""

    # Check if already exists
    check_sql = text("""
        SELECT id FROM scouting_grades
        WHERE prospect_id = :prospect_id
        AND source = 'fangraphs'
        AND ranking_year = :year
    """)
    result = db.execute(check_sql, {'prospect_id': prospect_id, 'year': year})
    if result.fetchone():
        return False  # Already exists

    insert_sql = text("""
        INSERT INTO scouting_grades (
            prospect_id, source, ranking_year, rank_overall,
            future_value, risk_level, eta_year,
            hit_present, power_present, raw_power_present, speed_present, field_present, arm_present,
            hit_future, power_future, raw_power_future, speed_future, field_future, arm_future,
            fastball_grade, slider_grade, curveball_grade, changeup_grade, command_grade,
            dynasty_rank, redraft_rank, scouting_report, date_recorded,
            created_at, updated_at
        ) VALUES (
            :prospect_id, 'fangraphs', :ranking_year, :rank_overall,
            :future_value, :risk_level, :eta_year,
            :hit_present, :power_present, :raw_power_present, :speed_present, :field_present, :arm_present,
            :hit_future, :power_future, :raw_power_future, :speed_future, :field_future, :arm_future,
            :fastball_grade, :slider_grade, :curveball_grade, :changeup_grade, :command_grade,
            :dynasty_rank, :redraft_rank, :scouting_report, CURRENT_DATE,
            NOW(), NOW()
        )
    """)

    # Parse ETA
    eta_str = fg_data.get('ETA_Current', '')
    eta_year = int(eta_str) if eta_str and str(eta_str).isdigit() else None

    db.execute(insert_sql, {
        'prospect_id': prospect_id,
        'ranking_year': year,
        'rank_overall': fg_data.get('BoardRank'),
        'future_value': fg_data.get('FV_Current'),
        'risk_level': fg_data.get('Variance'),
        'eta_year': eta_year,

        # Present grades
        'hit_present': fg_data.get('pHit'),
        'power_present': fg_data.get('pGame'),
        'raw_power_present': fg_data.get('pRaw'),
        'speed_present': fg_data.get('pSpd'),
        'field_present': fg_data.get('pFld'),
        'arm_present': fg_data.get('pArm'),

        # Future grades
        'hit_future': fg_data.get('fHit'),
        'power_future': fg_data.get('fGame'),
        'raw_power_future': fg_data.get('fRaw'),
        'speed_future': fg_data.get('fSpd'),
        'field_future': fg_data.get('fFld'),
        'arm_future': fg_data.get('fArm'),

        # Pitcher grades
        'fastball_grade': fg_data.get('pFB'),
        'slider_grade': fg_data.get('pSL'),
        'curveball_grade': fg_data.get('pCB'),
        'changeup_grade': fg_data.get('pCH'),
        'command_grade': fg_data.get('pCMD'),

        # Fantasy
        'dynasty_rank': fg_data.get('Fantasy_Dynasty'),
        'redraft_rank': fg_data.get('Fantasy_Redraft'),

        # Narrative
        'scouting_report': fg_data.get('Summary'),
    })

    db.commit()
    return True  # Created


async def main():
    """Main entry point."""
    start_time = datetime.now()

    print("=" * 80)
    print("COLLECTING FULL 2024 PROSPECT DATA")
    print("=" * 80)

    print("\nFetching prospect list from Fangraphs...")
    prospects = await fetch_fangraphs_prospects(2024)
    print(f"Found {len(prospects)} prospects\n")

    db = get_db_sync()

    stats = {
        'prospects_created': 0,
        'prospects_existing': 0,
        'scouting_grades_created': 0,
        'scouting_grades_existing': 0,
        'errors': 0
    }

    try:
        for i, fg_data in enumerate(prospects, 1):
            name = fg_data.get('playerName', 'Unknown')
            fv = fg_data.get('FV_Current', 'N/A')

            if i % 25 == 0:
                print(f"[{i}/{len(prospects)}] Processing: {name} (FV: {fv})")

            try:
                # Insert prospect
                prospect_id, created = insert_prospect(db, fg_data, 2024)
                if created:
                    stats['prospects_created'] += 1
                else:
                    stats['prospects_existing'] += 1

                # Insert scouting grade
                grade_created = insert_scouting_grade(db, prospect_id, fg_data, 2024)
                if grade_created:
                    stats['scouting_grades_created'] += 1
                else:
                    stats['scouting_grades_existing'] += 1

            except Exception as e:
                print(f"  Error with {name}: {e}")
                stats['errors'] += 1
                db.rollback()
                continue

            # Rate limiting
            await asyncio.sleep(1)

        duration = (datetime.now() - start_time).total_seconds() / 60

        print("\n" + "=" * 80)
        print("COLLECTION SUMMARY")
        print("=" * 80)
        print(f"Duration: {duration:.1f} minutes")
        print(f"Total prospects found: {len(prospects)}")
        print(f"Prospects created: {stats['prospects_created']}")
        print(f"Prospects existing: {stats['prospects_existing']}")
        print(f"Scouting grades created: {stats['scouting_grades_created']}")
        print(f"Scouting grades existing: {stats['scouting_grades_existing']}")
        print(f"Errors: {stats['errors']}")
        print("=" * 80)

        print("\n✅ SUCCESS! 2024 data collection complete!")

    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(main())
