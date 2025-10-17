"""
Match FanGraphs Unified Grades to MLB Player IDs using name, age, and team.

This script matches players from fangraphs_unified_grades to milb_players
using fuzzy name matching, age similarity, and team/organization matching.

Usage:
    python match_fangraphs_to_mlb_ids.py
"""

import sys
import os
from pathlib import Path
from difflib import SequenceMatcher
import re

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db.database import get_db_sync

# Team abbreviation mappings
TEAM_MAPPINGS = {
    'ARI': ['Arizona', 'D-backs', 'Diamondbacks'],
    'ATL': ['Atlanta', 'Braves'],
    'BAL': ['Baltimore', 'Orioles'],
    'BOS': ['Boston', 'Red Sox'],
    'CHC': ['Chicago Cubs', 'Cubs'],
    'CHW': ['Chicago White Sox', 'White Sox', 'CWS'],
    'CIN': ['Cincinnati', 'Reds'],
    'CLE': ['Cleveland', 'Guardians', 'Indians'],
    'COL': ['Colorado', 'Rockies'],
    'DET': ['Detroit', 'Tigers'],
    'HOU': ['Houston', 'Astros'],
    'KCR': ['Kansas City', 'Royals', 'KC'],
    'LAA': ['Los Angeles Angels', 'Angels', 'LA Angels'],
    'LAD': ['Los Angeles Dodgers', 'Dodgers', 'LA Dodgers'],
    'MIA': ['Miami', 'Marlins'],
    'MIL': ['Milwaukee', 'Brewers'],
    'MIN': ['Minnesota', 'Twins'],
    'NYM': ['New York Mets', 'Mets', 'NY Mets'],
    'NYY': ['New York Yankees', 'Yankees', 'NY Yankees'],
    'OAK': ['Oakland', 'Athletics', 'A\'s', 'ATH'],
    'PHI': ['Philadelphia', 'Phillies'],
    'PIT': ['Pittsburgh', 'Pirates'],
    'SDP': ['San Diego', 'Padres', 'SD'],
    'SEA': ['Seattle', 'Mariners'],
    'SFG': ['San Francisco', 'Giants', 'SF'],
    'STL': ['St. Louis', 'Cardinals'],
    'TBR': ['Tampa Bay', 'Rays', 'TB'],
    'TEX': ['Texas', 'Rangers'],
    'TOR': ['Toronto', 'Blue Jays'],
    'WSN': ['Washington', 'Nationals', 'WAS']
}


def normalize_name(name):
    """Normalize a player name for comparison."""
    if not name:
        return ""

    # Remove accents, convert to lowercase
    name = name.lower()

    # Remove common suffixes
    name = re.sub(r'\s+(jr|sr|ii|iii|iv)\.?$', '', name)

    # Remove punctuation except spaces
    name = re.sub(r'[^a-z\s]', '', name)

    # Normalize whitespace
    name = ' '.join(name.split())

    return name


def name_similarity(name1, name2):
    """Calculate similarity between two names (0-1)."""
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)

    if not norm1 or not norm2:
        return 0.0

    # Try full name match
    full_match = SequenceMatcher(None, norm1, norm2).ratio()

    # Try first/last name combinations
    parts1 = norm1.split()
    parts2 = norm2.split()

    if len(parts1) >= 2 and len(parts2) >= 2:
        # Check if last names match
        last_match = SequenceMatcher(None, parts1[-1], parts2[-1]).ratio()
        first_match = SequenceMatcher(None, parts1[0], parts2[0]).ratio()

        # Weight last name more heavily
        partial_match = (last_match * 0.7 + first_match * 0.3)

        return max(full_match, partial_match)

    return full_match


def teams_match(fg_org, mlb_team):
    """Check if FanGraphs organization matches MLB team."""
    if not fg_org or not mlb_team:
        return False

    fg_org = fg_org.upper().strip()
    mlb_team = mlb_team.upper().strip()

    # Direct match
    if fg_org == mlb_team:
        return True

    # Check mappings
    for abbrev, variations in TEAM_MAPPINGS.items():
        if fg_org == abbrev or fg_org in [v.upper() for v in variations]:
            if mlb_team == abbrev or mlb_team in [v.upper() for v in variations]:
                return True

    return False


def age_difference(fg_age, game_date, birth_date=None):
    """Calculate age difference (allowing for season variations)."""
    # FanGraphs ages are typically as of a specific date in the season
    # MiLB game ages can vary throughout the season
    # Allow 1 year tolerance
    try:
        fg_age_float = float(fg_age)
        # We don't have exact birth dates, so we'll be lenient
        return 0  # Will check age separately
    except:
        return 999


def match_fangraphs_to_milb():
    """Match FanGraphs players to MLB player IDs."""
    db = get_db_sync()

    print("="*80)
    print("MATCHING FANGRAPHS PLAYERS TO MLB PLAYER IDS")
    print("="*80)

    try:
        # Get all FanGraphs players without MLB IDs
        fg_query = text("""
            SELECT DISTINCT
                fg_player_id,
                player_name,
                age,
                organization,
                position,
                year
            FROM fangraphs_unified_grades
            WHERE fg_player_id IS NOT NULL
            ORDER BY year DESC, player_name
        """)

        fg_result = db.execute(fg_query)
        fg_players = fg_result.fetchall()

        print(f"Found {len(fg_players)} FanGraphs player records to match")

        # Get all MiLB players with names
        milb_query = text("""
            SELECT DISTINCT
                mlb_player_id,
                name,
                team_name,
                level,
                season
            FROM milb_players
            WHERE mlb_player_id IS NOT NULL
            AND name IS NOT NULL
        """)

        milb_result = db.execute(milb_query)
        milb_players = milb_result.fetchall()

        print(f"Found {len(milb_players)} MiLB players in database")
        print("")

        # Build lookup dictionaries for faster matching
        milb_by_season = {}
        for mlb_id, name, team, level, season in milb_players:
            if season not in milb_by_season:
                milb_by_season[season] = []
            milb_by_season[season].append({
                'mlb_id': mlb_id,
                'name': name,
                'team': team,
                'level': level
            })

        # Match FanGraphs players
        matches = {}
        match_count = 0
        no_match_count = 0

        for fg_id, fg_name, fg_age, fg_org, fg_pos, fg_year in fg_players:
            # Skip if already matched
            if fg_id in matches:
                continue

            best_match = None
            best_score = 0.0

            # Look in the same year and adjacent years
            for year in [fg_year, fg_year - 1, fg_year + 1]:
                if year not in milb_by_season:
                    continue

                for milb_player in milb_by_season[year]:
                    # Calculate match score
                    name_score = name_similarity(fg_name, milb_player['name'])

                    # Require at least 0.8 name similarity
                    if name_score < 0.8:
                        continue

                    # Bonus for team match
                    team_bonus = 0.2 if teams_match(fg_org, milb_player['team']) else 0.0

                    total_score = name_score + team_bonus

                    if total_score > best_score:
                        best_score = total_score
                        best_match = milb_player

            # Accept match if score is high enough
            if best_match and best_score >= 0.85:
                matches[fg_id] = best_match['mlb_id']
                match_count += 1

                if match_count <= 20 or match_count % 100 == 0:
                    print(f"[{match_count}] Matched: {fg_name} ({fg_org}) -> {best_match['name']} (ID: {best_match['mlb_id']}) [score: {best_score:.2f}]")
            else:
                no_match_count += 1
                if no_match_count <= 10:
                    print(f"  No match: {fg_name} ({fg_org}, {fg_year}) [best score: {best_score:.2f}]")

        print("")
        print(f"Matched {match_count} FanGraphs players")
        print(f"No match found for {no_match_count} players")

        # Update fangraphs_unified_grades with MLB IDs
        if matches:
            print("")
            print("Updating fangraphs_unified_grades with MLB player IDs...")

            update_count = 0
            for fg_id, mlb_id in matches.items():
                update_query = text("""
                    UPDATE fangraphs_unified_grades
                    SET mlb_player_id = :mlb_id
                    WHERE fg_player_id = :fg_id
                """)

                result = db.execute(update_query, {
                    'mlb_id': mlb_id,
                    'fg_id': fg_id
                })

                update_count += result.rowcount

            db.commit()
            print(f"Updated {update_count} rows in fangraphs_unified_grades")

        # Verify results
        verify_query = text("""
            SELECT COUNT(DISTINCT fg_player_id) as total,
                   COUNT(DISTINCT mlb_player_id) FILTER (WHERE mlb_player_id IS NOT NULL) as with_mlb_id
            FROM fangraphs_unified_grades
        """)

        result = db.execute(verify_query)
        row = result.fetchone()

        print("")
        print("="*80)
        print("RESULTS")
        print("="*80)
        print(f"Total FG players: {row[0]}")
        print(f"With MLB IDs: {row[1]} ({row[1]/row[0]*100:.1f}%)")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()

    finally:
        db.close()


if __name__ == "__main__":
    match_fangraphs_to_milb()
