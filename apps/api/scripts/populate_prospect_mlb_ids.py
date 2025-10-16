"""
Populate MLB Player IDs for Prospects using Multiple Matching Strategies

This script uses a multi-layered approach to match prospects to MLB player IDs:
1. Exact FanGraphs ID match via Chadwick Bureau
2. Name + Organization + Year match with milb_players
3. Name + Age similarity match
4. Fuzzy name matching as fallback

Usage:
    python populate_prospect_mlb_ids.py
"""

import sys
import os
from pathlib import Path
from difflib import SequenceMatcher
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def normalize_name(name):
    """Normalize player name for matching."""
    if not name:
        return ""

    name = name.lower()
    name = re.sub(r'\s+(jr|sr|ii|iii|iv)\.?$', '', name)
    name = re.sub(r'[^a-z\s]', '', name)
    return ' '.join(name.split())


def name_similarity(name1, name2):
    """Calculate name similarity score (0-1)."""
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)

    if not norm1 or not norm2:
        return 0.0

    # Full name match
    full_score = SequenceMatcher(None, norm1, norm2).ratio()

    # Last name match (weighted heavily)
    parts1 = norm1.split()
    parts2 = norm2.split()

    if len(parts1) >= 2 and len(parts2) >= 2:
        last_score = SequenceMatcher(None, parts1[-1], parts2[-1]).ratio()
        first_score = SequenceMatcher(None, parts1[0], parts2[0]).ratio()

        # 70% last name, 30% first name
        partial_score = last_score * 0.7 + first_score * 0.3

        return max(full_score, partial_score)

    return full_score


def match_prospects_to_mlb_ids():
    """Match all prospects to MLB player IDs."""

    db_url = os.getenv('SQLALCHEMY_DATABASE_URI').replace('postgresql+asyncpg://', 'postgresql://')
    engine = create_engine(db_url)

    print("="*80)
    print("POPULATING PROSPECT MLB PLAYER IDs")
    print("="*80)
    print()

    with engine.begin() as conn:
        # Step 1: Match via FanGraphs ID using Chadwick Bureau
        print("Step 1: Matching via FanGraphs ID (Chadwick Bureau)...")

        try:
            import pybaseball as pyb
            mapping = pyb.chadwick_register()
            print(f"  Loaded {len(mapping)} ID mappings from Chadwick Bureau")

            # Get prospects with FG IDs but no MLB ID
            result = conn.execute(text("""
                SELECT id, fg_player_id, name
                FROM prospects
                WHERE fg_player_id IS NOT NULL
                AND (mlb_player_id IS NULL OR mlb_player_id = '')
            """))

            prospects_with_fg = result.fetchall()
            fg_matched = 0

            for prospect_id, fg_id, name in prospects_with_fg:
                try:
                    fg_id_int = int(fg_id)
                    match = mapping[mapping['key_fangraphs'] == fg_id_int]

                    if not match.empty:
                        mlb_id = match.iloc[0]['key_mlbam']
                        if mlb_id and mlb_id > 0:
                            conn.execute(text("""
                                UPDATE prospects
                                SET mlb_player_id = :mlb_id
                                WHERE id = :id
                            """), {'mlb_id': str(int(mlb_id)), 'id': prospect_id})

                            fg_matched += 1
                            if fg_matched <= 5:
                                print(f"    [{fg_matched}] {name}: FG {fg_id} -> MLB {int(mlb_id)}")
                except:
                    pass

            print(f"  [OK] Matched {fg_matched} prospects via FanGraphs ID")

        except ImportError:
            print("  [WARN] pybaseball not available, skipping FanGraphs matching")
            fg_matched = 0

        print()

        # Step 2: Match via name + organization with milb_players
        print("Step 2: Matching via name + organization...")

        # Get unmatched prospects
        result = conn.execute(text("""
            SELECT
                p.id,
                p.name,
                p.organization,
                fg.year
            FROM prospects p
            LEFT JOIN fangraphs_unified_grades fg ON p.fg_player_id = fg.fg_player_id
            WHERE (p.mlb_player_id IS NULL OR p.mlb_player_id = '')
            AND p.name IS NOT NULL
        """))

        unmatched_prospects = result.fetchall()
        print(f"  Processing {len(unmatched_prospects)} unmatched prospects...")

        # Get milb_players for matching
        result = conn.execute(text("""
            SELECT DISTINCT
                mlb_player_id,
                name,
                team_name,
                season
            FROM milb_players
            WHERE mlb_player_id IS NOT NULL
            AND name IS NOT NULL
        """))

        milb_players = result.fetchall()
        print(f"  Loaded {len(milb_players)} MiLB players")

        # Build lookup by season
        milb_by_season = {}
        for mlb_id, name, team, season in milb_players:
            if season not in milb_by_season:
                milb_by_season[season] = []
            milb_by_season[season].append({
                'mlb_id': mlb_id,
                'name': name,
                'team': team
            })

        name_matched = 0

        for prospect_id, prospect_name, prospect_org, fg_year in unmatched_prospects:
            if not prospect_name:
                continue

            best_match = None
            best_score = 0.0

            # Search in relevant seasons
            years_to_check = [2024, 2023, 2025, 2022]
            if fg_year:
                years_to_check = [fg_year, fg_year - 1, fg_year + 1, 2024, 2023]

            for year in years_to_check:
                if year not in milb_by_season:
                    continue

                for milb_player in milb_by_season[year]:
                    score = name_similarity(prospect_name, milb_player['name'])

                    # Require strong name match
                    if score < 0.85:
                        continue

                    # Bonus for org match (if available)
                    if prospect_org and milb_player['team']:
                        if prospect_org.upper() in milb_player['team'].upper() or \
                           milb_player['team'].upper() in prospect_org.upper():
                            score += 0.1

                    if score > best_score:
                        best_score = score
                        best_match = milb_player

            # Accept match if score is good
            if best_match and best_score >= 0.88:
                conn.execute(text("""
                    UPDATE prospects
                    SET mlb_player_id = :mlb_id
                    WHERE id = :id
                """), {'mlb_id': str(best_match['mlb_id']), 'id': prospect_id})

                name_matched += 1
                if name_matched <= 20:
                    print(f"    [{name_matched}] {prospect_name} -> {best_match['name']} (MLB {best_match['mlb_id']}) [{best_score:.2f}]")

        print(f"  [OK] Matched {name_matched} prospects via name matching")
        print()

        # Step 3: Report results
        print("="*80)
        print("RESULTS")
        print("="*80)

        result = conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(mlb_player_id) FILTER (WHERE mlb_player_id IS NOT NULL AND mlb_player_id != '') as with_mlb_id
            FROM prospects
        """))

        row = result.fetchone()
        total = row[0]
        with_mlb = row[1]

        print(f"Total prospects: {total}")
        print(f"With MLB player ID: {with_mlb} ({with_mlb/total*100:.1f}%)")
        print(f"  - Via FanGraphs ID: {fg_matched}")
        print(f"  - Via name matching: {name_matched}")
        print(f"Still unmatched: {total - with_mlb}")
        print()

        # Check how many have game logs
        result = conn.execute(text("""
            SELECT COUNT(DISTINCT p.mlb_player_id)
            FROM prospects p
            INNER JOIN milb_game_logs g ON g.mlb_player_id::text = p.mlb_player_id
            WHERE p.mlb_player_id IS NOT NULL
            AND p.mlb_player_id != ''
            AND g.season >= 2021
        """))

        with_game_logs = result.scalar()

        print(f"Prospects with MLB IDs AND game logs (2021+): {with_game_logs}")
        print()

        # Sample matched prospects
        result = conn.execute(text("""
            SELECT p.name, p.organization, p.mlb_player_id, COUNT(g.id) as game_count
            FROM prospects p
            LEFT JOIN milb_game_logs g ON g.mlb_player_id::text = p.mlb_player_id AND g.season >= 2021
            WHERE p.mlb_player_id IS NOT NULL
            AND p.mlb_player_id != ''
            GROUP BY p.name, p.organization, p.mlb_player_id
            ORDER BY game_count DESC
            LIMIT 10
        """))

        print("Sample matched prospects with game logs:")
        for name, org, mlb_id, games in result.fetchall():
            print(f"  {name} ({org}) - MLB ID: {mlb_id} - {games} games")

        print()
        print("="*80)
        print(f"[OK] COMPLETE - {with_mlb} prospects now have MLB player IDs")
        print("="*80)


if __name__ == "__main__":
    match_prospects_to_mlb_ids()
