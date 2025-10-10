"""
Improved FanGraphs linking script.

Improvements:
1. Consolidate duplicate prospect entries (some have mlb_id, some have fg_id)
2. Use birth year to disambiguate players with same names
3. Match on both full names and last names
4. Prioritize newest FanGraphs grades
5. Filter out players with 130+ MLB at-bats
"""

import pandas as pd
import asyncio
from sqlalchemy import text
import sys
import os
from fuzzywuzzy import fuzz
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine


async def load_fangraphs_prospects():
    """Load FanGraphs prospects with latest grades prioritized."""
    async with engine.begin() as conn:
        result = await conn.execute(text('''
            WITH latest_grades AS (
                SELECT
                    fg_player_id,
                    player_name,
                    report_year,
                    age,
                    fv,
                    top_100_rank,
                    position,
                    organization,
                    ROW_NUMBER() OVER (PARTITION BY fg_player_id ORDER BY report_year DESC) as rn
                FROM fangraphs_prospect_grades
            )
            SELECT
                fg_player_id,
                player_name,
                report_year as latest_year,
                age,
                fv,
                top_100_rank,
                position,
                organization,
                EXTRACT(YEAR FROM CURRENT_DATE) - age as approx_birth_year
            FROM latest_grades
            WHERE rn = 1
            ORDER BY fv DESC NULLS LAST, player_name
        '''))

        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        print(f'Loaded {len(df)} FanGraphs prospects (latest grades only)')
        return df


async def load_our_prospects():
    """
    Load prospects from our database, consolidating duplicates.
    Some prospects have multiple rows (one with mlb_id, one with fg_id).
    """
    async with engine.begin() as conn:
        result = await conn.execute(text('''
            SELECT
                name,
                mlb_player_id,
                fg_player_id,
                birth_date,
                position,
                current_team,
                EXTRACT(YEAR FROM birth_date) as birth_year
            FROM prospects
            WHERE mlb_player_id IS NOT NULL
            ORDER BY name, mlb_player_id
        '''))

        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        print(f'Loaded {len(df)} prospects from our database (with MLB IDs)')
        print(f'  Already linked to FG: {df["fg_player_id"].notna().sum()}')
        return df


async def get_mlb_at_bats():
    """Get MLB at-bats for filtering (exclude players with 130+ AB)."""
    async with engine.begin() as conn:
        result = await conn.execute(text('''
            SELECT
                mlb_player_id,
                SUM(at_bats) as total_ab
            FROM mlb_game_logs
            GROUP BY mlb_player_id
            HAVING SUM(at_bats) >= 130
        '''))

        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        print(f'Found {len(df)} players with 130+ MLB at-bats (will exclude)')
        return set(df['mlb_player_id'].astype(str))


def normalize_name(name):
    """Normalize player name for matching."""
    if pd.isna(name):
        return ''

    name = str(name).lower().strip()

    # Remove accents
    replacements = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'ä': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o', 'ö': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ñ': 'n', 'ç': 'c',
        'jr.': '', 'jr': '', 'sr.': '', 'sr': '',
        '.': '', ',': '', "'": '', '-': ' ', '  ': ' '
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    return ' '.join(name.split())


def get_last_name(name):
    """Extract last name."""
    parts = name.split()
    return parts[-1] if parts else ''


def normalize_position(pos):
    """Normalize position for matching."""
    if pd.isna(pos):
        return None
    pos = str(pos).upper().strip()
    # Map variations
    mapping = {
        'SS': 'SS', 'SHORTSTOP': 'SS',
        '2B': '2B', 'SECOND BASE': '2B',
        '3B': '3B', 'THIRD BASE': '3B',
        '1B': '1B', 'FIRST BASE': '1B',
        'OF': 'OF', 'OUTFIELD': 'OF', 'LF': 'OF', 'CF': 'OF', 'RF': 'OF',
        'C': 'C', 'CATCHER': 'C',
        'P': 'P', 'PITCHER': 'P', 'RHP': 'P', 'LHP': 'P',
        'DH': 'DH', 'UTIL': 'UTIL', 'IF': 'IF'
    }
    return mapping.get(pos, pos)


def normalize_org(org):
    """Normalize organization/team name."""
    if pd.isna(org):
        return None
    org = str(org).upper().strip()
    # Common abbreviations
    mapping = {
        'YANKEES': 'NYY', 'NEW YORK YANKEES': 'NYY',
        'RED SOX': 'BOS', 'BOSTON RED SOX': 'BOS',
        'DODGERS': 'LAD', 'LOS ANGELES DODGERS': 'LAD',
        # Add more as needed
    }
    return mapping.get(org, org)


def match_prospects(fg_df, our_df, exclude_mlb_ids):
    """
    Match FanGraphs prospects to our prospects.

    Matching strategy:
    1. Exact name match (normalized)
    2. Exact name match + birth year within 1 year
    3. Exact name + position match
    4. Exact name + organization match
    5. Fuzzy match on full name (90%+)
    6. Last name + birth year + position
    7. Last name + birth year + organization
    """
    matches = []

    # Normalize names
    fg_df['name_norm'] = fg_df['player_name'].apply(normalize_name)
    fg_df['last_name'] = fg_df['name_norm'].apply(get_last_name)
    fg_df['pos_norm'] = fg_df['position'].apply(normalize_position)
    fg_df['org_norm'] = fg_df['organization'].apply(normalize_org)

    our_df['name_norm'] = our_df['name'].apply(normalize_name)
    our_df['last_name'] = our_df['name_norm'].apply(get_last_name)
    our_df['pos_norm'] = our_df['position'].apply(normalize_position)
    our_df['org_norm'] = our_df['current_team'].apply(normalize_org)

    print('\nMatching prospects...')

    # Create index for faster lookup
    our_by_name = {}
    for idx, row in our_df.iterrows():
        name = row['name_norm']
        if name not in our_by_name:
            our_by_name[name] = []
        our_by_name[name].append(row)

    our_by_last = {}
    for idx, row in our_df.iterrows():
        last = row['last_name']
        if last not in our_by_last:
            our_by_last[last] = []
        our_by_last[last].append(row)

    for idx, fg_row in fg_df.iterrows():
        if idx % 100 == 0:
            print(f'  Progress: {idx}/{len(fg_df)}')

        fg_name = fg_row['name_norm']
        fg_last = fg_row['last_name']
        fg_pos = fg_row['pos_norm']
        fg_org = fg_row['org_norm']
        fg_birth_year = int(fg_row['approx_birth_year']) if pd.notna(fg_row['approx_birth_year']) else None

        if not fg_name:
            continue

        best_match = None
        match_type = None

        # Strategy 1: Exact name match
        if fg_name in our_by_name:
            candidates = our_by_name[fg_name]

            # If single match, use it
            if len(candidates) == 1:
                best_match = candidates[0]
                match_type = 'exact_name'

            # Multiple candidates - disambiguate
            else:
                # Try birth year first
                if fg_birth_year:
                    for candidate in candidates:
                        if pd.notna(candidate['birth_year']):
                            year_diff = abs(fg_birth_year - int(candidate['birth_year']))
                            if year_diff <= 1:
                                best_match = candidate
                                match_type = 'exact_name_birth_year'
                                break

                # Try position
                if best_match is None and fg_pos:
                    for candidate in candidates:
                        if candidate['pos_norm'] == fg_pos:
                            best_match = candidate
                            match_type = 'exact_name_position'
                            break

                # Try organization
                if best_match is None and fg_org:
                    for candidate in candidates:
                        if candidate['org_norm'] == fg_org:
                            best_match = candidate
                            match_type = 'exact_name_org'
                            break

                # Take first if no disambiguator worked
                if best_match is None:
                    best_match = candidates[0]
                    match_type = 'exact_name_first'

        # Strategy 2: Fuzzy name match (90%+)
        if best_match is None:
            best_score = 0
            for our_row in our_df.itertuples():
                score = fuzz.ratio(fg_name, our_row.name_norm)
                if score >= 90 and score > best_score:
                    best_score = score
                    best_match = our_df.iloc[our_row.Index]
                    match_type = f'fuzzy_{score}'

        # Strategy 3: Last name + birth year + position/org
        if best_match is None and fg_birth_year and fg_last in our_by_last:
            candidates = our_by_last[fg_last]

            # Try birth year + position
            if fg_pos:
                for candidate in candidates:
                    if pd.notna(candidate['birth_year']) and candidate['pos_norm'] == fg_pos:
                        year_diff = abs(fg_birth_year - int(candidate['birth_year']))
                        if year_diff <= 1:
                            best_match = candidate
                            match_type = 'last_birth_pos'
                            break

            # Try birth year + org
            if best_match is None and fg_org:
                for candidate in candidates:
                    if pd.notna(candidate['birth_year']) and candidate['org_norm'] == fg_org:
                        year_diff = abs(fg_birth_year - int(candidate['birth_year']))
                        if year_diff <= 1:
                            best_match = candidate
                            match_type = 'last_birth_org'
                            break

            # Try birth year alone
            if best_match is None:
                for candidate in candidates:
                    if pd.notna(candidate['birth_year']):
                        year_diff = abs(fg_birth_year - int(candidate['birth_year']))
                        if year_diff <= 1:
                            best_match = candidate
                            match_type = 'last_birth_year'
                            break

        if best_match is not None:
            # Skip if player has 130+ MLB at-bats
            mlb_id = str(best_match['mlb_player_id'])
            if mlb_id in exclude_mlb_ids:
                continue

            matches.append({
                'fg_player_id': fg_row['fg_player_id'],
                'fg_name': fg_row['player_name'],
                'mlb_player_id': mlb_id,
                'our_name': best_match['name'],
                'match_type': match_type,
                'fv': fg_row['fv'],
                'latest_year': fg_row['latest_year'],
                'top_100_rank': fg_row['top_100_rank']
            })

    matches_df = pd.DataFrame(matches)
    print(f'\nMatched {len(matches_df)} prospects')

    # Match type distribution
    print('\nMatch Types:')
    for match_type, count in matches_df['match_type'].value_counts().items():
        print(f'  {match_type}: {count}')

    return matches_df


async def update_prospect_links(matches_df):
    """
    Update prospects table with FanGraphs IDs.
    Update ALL prospect rows with the same mlb_player_id.
    """
    print('\nUpdating prospects table...')

    async with engine.begin() as conn:
        updated = 0

        for _, row in matches_df.iterrows():
            # Update all prospects with this MLB player ID
            result = await conn.execute(text('''
                UPDATE prospects
                SET fg_player_id = :fg_player_id,
                    updated_at = NOW()
                WHERE mlb_player_id = :mlb_player_id
            '''), {
                'fg_player_id': row['fg_player_id'],
                'mlb_player_id': row['mlb_player_id']
            })
            updated += result.rowcount

        print(f'Updated {updated} prospect rows')

        # Verify
        result = await conn.execute(text('''
            SELECT COUNT(DISTINCT mlb_player_id)
            FROM prospects
            WHERE fg_player_id IS NOT NULL
              AND mlb_player_id IS NOT NULL
        '''))
        total = result.scalar()
        print(f'Total unique prospects with FanGraphs ID: {total}')


async def show_sample_matches(matches_df):
    """Show sample of matched prospects."""
    print('\n' + '=' * 80)
    print('SAMPLE MATCHES (Top 30 by FV)')
    print('=' * 80)

    sample = matches_df.sort_values('fv', ascending=False).head(30)

    print(f'{"FanGraphs Name":<25} {"Our Name":<25} {"FV":<4} {"Year":<6} {"Match Type":<20}')
    print('-' * 80)

    for _, row in sample.iterrows():
        fg_name = row['fg_name'][:24]
        our_name = row['our_name'][:24]
        fv = int(row['fv']) if pd.notna(row['fv']) else '-'
        year = int(row['latest_year'])
        match_type = row['match_type'][:19]

        print(f'{fg_name:<25} {our_name:<25} {str(fv):<4} {year:<6} {match_type:<20}')


async def main():
    print('=' * 80)
    print('IMPROVED FANGRAPHS LINKING')
    print('=' * 80)

    # Load data
    fg_df = await load_fangraphs_prospects()
    our_df = await load_our_prospects()
    exclude_ids = await get_mlb_at_bats()

    # Match
    matches_df = match_prospects(fg_df, our_df, exclude_ids)

    if len(matches_df) == 0:
        print('\nNo matches found!')
        return

    # Show samples
    await show_sample_matches(matches_df)

    # Update database
    await update_prospect_links(matches_df)

    print('\n' + '=' * 80)
    print('LINKING COMPLETE')
    print('=' * 80)


if __name__ == '__main__':
    asyncio.run(main())
