"""
Populate MLB Player IDs for Prospects using MLB Stats API

This script searches for MLB player IDs using the official MLB Stats API
by matching prospect names and teams.

Usage:
    python scripts/populate_mlb_player_ids.py [--limit N] [--dry-run]

Options:
    --limit N    Only process N prospects (for testing)
    --dry-run    Don't actually update the database
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from difflib import SequenceMatcher
import re
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db.database import engine
import requests


# MLB Stats API endpoints
MLB_API_BASE = "https://statsapi.mlb.com/api/v1"


def normalize_name(name):
    """Normalize player name for matching."""
    if not name:
        return ""

    name = name.lower()
    # Remove suffixes
    name = re.sub(r'\s+(jr|sr|ii|iii|iv)\.?$', '', name)
    # Remove non-alphanumeric except spaces
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


def search_mlb_player(name, team_abbr=None, birth_date=None, age=None, position=None):
    """
    Search for a player in the MLB Stats API with multiple matching criteria.

    Args:
        name: Player's full name
        team_abbr: Team abbreviation (e.g., 'NYY', 'BOS')
        birth_date: Player's birth date (datetime.date or string)
        age: Player's age (int)
        position: Player's position (e.g., 'P', 'SS', '1B')

    Returns:
        dict or None: Player info including mlb_player_id if found
    """
    try:
        # Use the search endpoint
        url = f"{MLB_API_BASE}/people/search"
        params = {
            'names': name,
            'hydrate': 'currentTeam'
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return None

        data = response.json()

        if 'people' not in data or not data['people']:
            return None

        # Find best match using multiple criteria
        best_match = None
        best_score = 0.0

        for person in data['people']:
            player_name = person.get('fullName', '')
            player_id = person.get('id')

            if not player_name or not player_id:
                continue

            # Start with name similarity (0.0 - 1.0)
            score = name_similarity(name, player_name)

            # Require minimum name match
            if score < 0.75:
                continue

            # Bonus points for matching criteria
            bonus_points = 0.0
            match_details = []

            # Team match (+0.15)
            if team_abbr and 'currentTeam' in person:
                current_team = person['currentTeam'].get('abbreviation', '')
                if current_team and current_team.upper() == team_abbr.upper():
                    bonus_points += 0.15
                    match_details.append(f"team:{current_team}")

            # Birth date match (+0.20)
            if birth_date:
                player_birth_date = person.get('birthDate', '')
                if player_birth_date:
                    # Extract just the date part for comparison
                    player_date_str = player_birth_date.split('T')[0] if 'T' in player_birth_date else player_birth_date
                    birth_date_str = str(birth_date).split(' ')[0]  # Handle datetime objects

                    if player_date_str == birth_date_str:
                        bonus_points += 0.20
                        match_details.append(f"birth:{player_date_str}")

            # Age match (+0.10) - less reliable but helpful
            if age and 'currentAge' in person:
                player_age = person.get('currentAge')
                # Allow 1 year difference due to timing
                if player_age and abs(player_age - age) <= 1:
                    bonus_points += 0.10
                    match_details.append(f"age:{player_age}")

            # Position match (+0.10)
            if position and 'primaryPosition' in person:
                player_position = person['primaryPosition'].get('abbreviation', '')
                # Normalize positions (handle P vs SP/RP)
                norm_pos = position.upper()
                norm_player_pos = player_position.upper()

                if norm_pos in ['SP', 'RP'] and norm_player_pos == 'P':
                    bonus_points += 0.10
                    match_details.append(f"pos:P")
                elif norm_pos == norm_player_pos:
                    bonus_points += 0.10
                    match_details.append(f"pos:{player_position}")
                elif norm_pos == 'P' and norm_player_pos in ['SP', 'RP']:
                    bonus_points += 0.05
                    match_details.append(f"pos:{player_position}")

            final_score = score + bonus_points

            if final_score > best_score:
                best_score = final_score
                best_match = {
                    'mlb_player_id': player_id,
                    'name': player_name,
                    'score': final_score,
                    'base_score': score,
                    'bonus': bonus_points,
                    'team': person.get('currentTeam', {}).get('abbreviation', 'N/A'),
                    'birth_date': person.get('birthDate', 'N/A'),
                    'age': person.get('currentAge', 'N/A'),
                    'position': person.get('primaryPosition', {}).get('abbreviation', 'N/A'),
                    'match_details': ', '.join(match_details) if match_details else 'name only'
                }

        # Only return if similarity is high enough
        # Lower threshold if we have good supporting data
        min_score = 0.85 if not birth_date else 0.80

        if best_match and best_score >= min_score:
            return best_match

        return None

    except Exception as e:
        print(f"  [ERROR] Searching for {name}: {e}")
        return None


async def populate_mlb_ids(limit=None, dry_run=False):
    """Populate MLB player IDs for all prospects."""

    print("=" * 80)
    print("POPULATING MLB PLAYER IDs FROM MLB STATS API")
    print("=" * 80)

    if dry_run:
        print("[DRY RUN MODE - No database updates will be made]")

    print()

    async with engine.begin() as conn:
        # Get prospects without MLB player IDs (with all available matching fields)
        query = """
            SELECT id, name, organization, position, birth_date, age, mlb_player_id
            FROM prospects
            WHERE mlb_player_id IS NULL
            AND name IS NOT NULL
            ORDER BY id
        """

        if limit:
            query += f" LIMIT {limit}"

        result = await conn.execute(text(query))
        prospects = result.fetchall()

        print(f"Found {len(prospects)} prospects without MLB player IDs")

        if limit:
            print(f"(Limited to {limit} for testing)")

        print()

        matched = 0
        not_found = 0
        errors = 0

        for i, (prospect_id, name, org, position, birth_date, age, current_mlb_id) in enumerate(prospects, 1):
            # Rate limiting - be nice to the API
            if i > 1 and i % 10 == 0:
                print(f"\n  [Progress: {i}/{len(prospects)}]")
                time.sleep(1)  # Brief pause every 10 requests

            # Search for player with all available criteria
            match = search_mlb_player(
                name=name,
                team_abbr=org,
                birth_date=birth_date,
                age=age,
                position=position
            )

            if match:
                mlb_id = match['mlb_player_id']
                matched_name = match['name']
                score = match['score']
                match_details = match.get('match_details', 'name only')

                if not dry_run:
                    # Update database (convert mlb_id to string as column is VARCHAR)
                    await conn.execute(
                        text("""
                            UPDATE prospects
                            SET mlb_player_id = :mlb_id
                            WHERE id = :id
                        """),
                        {'mlb_id': str(mlb_id), 'id': prospect_id}
                    )

                matched += 1

                # Print first 20 matches and then every 50th
                if matched <= 20 or matched % 50 == 0:
                    status = "[DRY RUN] " if dry_run else ""
                    print(f"  {status}[{matched}] {name} ({org}) -> {matched_name} (ID: {mlb_id})")
                    print(f"           [score: {score:.2f}, matched: {match_details}]")

            else:
                not_found += 1
                # Print first few not found
                if not_found <= 10:
                    print(f"  [NOT FOUND] {name} ({org}, {position}, age:{age})")

        print()
        print("=" * 80)
        print("RESULTS")
        print("=" * 80)

        # Get final counts
        result = await conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(mlb_player_id) as with_mlb_id
            FROM prospects
        """))

        row = result.fetchone()
        total = row[0]
        with_mlb = row[1]

        print(f"Total prospects in database: {total}")
        print(f"With MLB player ID: {with_mlb} ({with_mlb/total*100:.1f}%)")
        print(f"Still unmatched: {total - with_mlb}")
        print()
        print(f"This run:")
        print(f"  - Matched: {matched}")
        print(f"  - Not found: {not_found}")
        print(f"  - Errors: {errors}")

        if dry_run:
            print("\n[DRY RUN] No changes were made to the database")

        print()
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Populate MLB player IDs for prospects")
    parser.add_argument('--limit', type=int, help='Only process N prospects')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t update database')

    args = parser.parse_args()

    asyncio.run(populate_mlb_ids(limit=args.limit, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
