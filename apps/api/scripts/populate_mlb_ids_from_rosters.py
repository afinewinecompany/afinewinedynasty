"""
Populate MLB Player IDs using Team Rosters

This script fetches full rosters (including all minor leaguers) from each MLB
organization and matches prospects by name and organization.

This is much more reliable than the search API which doesn't index minor leaguers.

Usage:
    python scripts/populate_mlb_ids_from_rosters.py [--limit N] [--dry-run]
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from difflib import SequenceMatcher
import re
import requests
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db.database import engine


MLB_API_BASE = "https://statsapi.mlb.com/api/v1"

# MLB team abbreviations to team IDs
TEAM_IDS = {
    'ARI': 109, 'ATL': 144, 'BAL': 110, 'BOS': 111, 'CHC': 112, 'CHW': 145,
    'CIN': 113, 'CLE': 114, 'COL': 115, 'DET': 116, 'HOU': 117, 'KCR': 118,
    'LAA': 108, 'LAD': 119, 'MIA': 146, 'MIL': 158, 'MIN': 142, 'NYM': 121,
    'NYY': 147, 'ATH': 133, 'PHI': 143, 'PIT': 134, 'SDP': 135, 'SFG': 137,
    'SEA': 136, 'STL': 138, 'TBR': 139, 'TEX': 140, 'TOR': 141, 'WSN': 120
}


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
        partial_score = last_score * 0.7 + first_score * 0.3
        return max(full_score, partial_score)

    return full_score


def fetch_team_roster(team_id):
    """Fetch full roster for a team including all minor leaguers."""
    url = f"{MLB_API_BASE}/teams/{team_id}/roster/fullRoster"

    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if 'roster' in data:
                players = []
                for entry in data['roster']:
                    person = entry.get('person', {})
                    players.append({
                        'id': person.get('id'),
                        'name': person.get('fullName'),
                        'position': entry.get('position', {}).get('abbreviation', 'N/A')
                    })
                return players
        return []
    except Exception as e:
        print(f"  [ERROR] Fetching roster for team {team_id}: {e}")
        return []


async def populate_from_rosters(limit=None, dry_run=False):
    """Populate MLB player IDs by downloading full team rosters."""

    print("=" * 80)
    print("POPULATING MLB PLAYER IDs FROM TEAM ROSTERS")
    print("=" * 80)

    if dry_run:
        print("[DRY RUN MODE - No database updates will be made]")

    print()
    print("This method fetches all players from each MLB organization's full roster")
    print("(including all minor league affiliates)")
    print()

    # First, download all team rosters
    print("Step 1: Downloading all team rosters...")
    print()

    all_players = {}  # {team_abbr: [players]}

    for team_abbr, team_id in TEAM_IDS.items():
        print(f"  Fetching {team_abbr}...", end=' ', flush=True)
        players = fetch_team_roster(team_id)
        all_players[team_abbr] = players
        print(f"{len(players)} players")
        time.sleep(0.5)  # Be nice to the API

    total_players = sum(len(p) for p in all_players.values())
    print()
    print(f"Downloaded rosters for {len(TEAM_IDS)} teams: {total_players} total players")
    print()

    # Now match prospects
    print("Step 2: Matching prospects to roster players...")
    print()

    async with engine.begin() as conn:
        # Get prospects without MLB player IDs
        query = """
            SELECT id, name, organization, position, age, mlb_player_id
            FROM prospects
            WHERE mlb_player_id IS NULL
            AND name IS NOT NULL
            ORDER BY organization, name
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

        for prospect_id, name, org, position, age, current_mlb_id in prospects:
            if not org or org not in all_players:
                not_found += 1
                continue

            # Get roster for this team
            roster = all_players[org]

            # Find best match
            best_match = None
            best_score = 0.0

            for player in roster:
                score = name_similarity(name, player['name'])

                # Require strong name match
                if score < 0.90:
                    continue

                # Bonus for position match
                if position and player['position'] != 'N/A':
                    if position == player['position'] or \
                       (position in ['SP', 'RP'] and player['position'] == 'P'):
                        score += 0.05

                if score > best_score:
                    best_score = score
                    best_match = player

            # Accept match if score is high enough
            if best_match and best_score >= 0.90:
                mlb_id = str(best_match['id'])

                if not dry_run:
                    # Update database
                    await conn.execute(
                        text("""
                            UPDATE prospects
                            SET mlb_player_id = :mlb_id
                            WHERE id = :id
                        """),
                        {'mlb_id': mlb_id, 'id': prospect_id}
                    )

                matched += 1

                # Print progress
                if matched <= 30 or matched % 50 == 0:
                    status = "[DRY RUN] " if dry_run else ""
                    print(f"  {status}[{matched}] {name} ({org}) -> {best_match['name']} (ID: {mlb_id}) [score: {best_score:.2f}]")

            else:
                not_found += 1
                # Print first few not found
                if not_found <= 10:
                    print(f"  [NOT FOUND] {name} ({org})")

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

        if dry_run:
            print("\n[DRY RUN] No changes were made to the database")

        print()
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Populate MLB player IDs from team rosters")
    parser.add_argument('--limit', type=int, help='Only process N prospects')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t update database')

    args = parser.parse_args()

    asyncio.run(populate_from_rosters(limit=args.limit, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
