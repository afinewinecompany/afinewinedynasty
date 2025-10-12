"""
Link FanGraphs prospect grades to our prospects table.

This script:
1. Matches FanGraphs player names to prospects in our database
2. Updates prospects.fg_player_id for successful matches
3. Enables joining FanGraphs grades to MiLB/MLB performance data
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
    """Load all unique FanGraphs prospects."""
    async with engine.begin() as conn:
        result = await conn.execute(text('''
            SELECT DISTINCT
                fg_player_id,
                player_name,
                MIN(report_year) as first_report_year,
                MAX(report_year) as last_report_year,
                AVG(age) as avg_age,
                MAX(fv) as best_fv,
                MIN(top_100_rank) as best_rank
            FROM fangraphs_prospect_grades
            GROUP BY fg_player_id, player_name
            ORDER BY best_fv DESC NULLS LAST, player_name
        '''))

        fg_prospects = pd.DataFrame(result.fetchall(), columns=result.keys())
        print(f'Loaded {len(fg_prospects)} unique FanGraphs prospects')
        return fg_prospects


async def load_our_prospects():
    """Load prospects from our database."""
    async with engine.begin() as conn:
        result = await conn.execute(text('''
            SELECT
                id as prospect_id,
                name,
                mlb_player_id,
                fg_player_id as existing_fg_id,
                birth_date
            FROM prospects
            ORDER BY name
        '''))

        our_prospects = pd.DataFrame(result.fetchall(), columns=result.keys())
        print(f'Loaded {len(our_prospects)} prospects from our database')
        print(f'  Already linked: {our_prospects["existing_fg_id"].notna().sum()}')
        return our_prospects


def normalize_name(name):
    """Normalize player name for matching."""
    if pd.isna(name):
        return ''

    # Convert to lowercase, remove accents/special chars
    name = str(name).lower()

    # Common replacements
    replacements = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ñ': 'n', 'ç': 'c',
        'jr.': '', 'sr.': '', 'jr': '', 'sr': '',
        '.': '', ',': '', "'": '', '-': ' '
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    # Remove extra whitespace
    name = ' '.join(name.split())

    return name


def match_prospects(fg_df, our_df):
    """Match FanGraphs prospects to our prospects using fuzzy name matching."""
    matches = []

    # Normalize names
    fg_df['name_norm'] = fg_df['player_name'].apply(normalize_name)
    our_df['name_norm'] = our_df['name'].apply(normalize_name)

    print('\nMatching prospects...')

    for idx, fg_row in fg_df.iterrows():
        if idx % 100 == 0:
            print(f'  Progress: {idx}/{len(fg_df)}')

        fg_name = fg_row['name_norm']
        fg_id = fg_row['fg_player_id']

        if not fg_name:
            continue

        # Find best match in our prospects
        best_score = 0
        best_match = None

        for _, our_row in our_df.iterrows():
            our_name = our_row['name_norm']

            if not our_name:
                continue

            # Try exact match first
            if fg_name == our_name:
                best_score = 100
                best_match = our_row
                break

            # Fuzzy match
            score = fuzz.ratio(fg_name, our_name)

            if score > best_score:
                best_score = score
                best_match = our_row

        # Only accept strong matches
        if best_score >= 85:  # 85% similarity threshold
            matches.append({
                'fg_player_id': fg_id,
                'fg_name': fg_row['player_name'],
                'prospect_id': best_match['prospect_id'],
                'our_name': best_match['name'],
                'mlb_player_id': best_match['mlb_player_id'],
                'match_score': best_score,
                'first_report_year': fg_row['first_report_year'],
                'best_fv': fg_row['best_fv'],
                'best_rank': fg_row['best_rank']
            })

    matches_df = pd.DataFrame(matches)
    print(f'\nMatched {len(matches_df)} prospects (score >= 85%)')

    # Show match quality distribution
    print('\nMatch Quality:')
    print(f'  Perfect (100%): {(matches_df["match_score"] == 100).sum()}')
    print(f'  Excellent (95-99%): {((matches_df["match_score"] >= 95) & (matches_df["match_score"] < 100)).sum()}')
    print(f'  Good (90-94%): {((matches_df["match_score"] >= 90) & (matches_df["match_score"] < 95)).sum()}')
    print(f'  Fair (85-89%): {((matches_df["match_score"] >= 85) & (matches_df["match_score"] < 90)).sum()}')

    return matches_df


async def update_prospect_links(matches_df):
    """Update prospects table with FanGraphs IDs."""
    print('\nUpdating prospects table...')

    async with engine.begin() as conn:
        updated = 0

        for _, row in matches_df.iterrows():
            await conn.execute(text('''
                UPDATE prospects
                SET fg_player_id = :fg_player_id,
                    updated_at = NOW()
                WHERE id = :prospect_id
            '''), {
                'fg_player_id': row['fg_player_id'],
                'prospect_id': row['prospect_id']
            })
            updated += 1

        print(f'Updated {updated} prospects with FanGraphs IDs')

        # Verify
        result = await conn.execute(text('''
            SELECT COUNT(*) FROM prospects WHERE fg_player_id IS NOT NULL
        '''))
        total_linked = result.scalar()
        print(f'Total prospects with FanGraphs ID: {total_linked}')


async def show_sample_matches(matches_df):
    """Show sample of matched prospects."""
    print('\n' + '=' * 80)
    print('SAMPLE MATCHES (Top 20 by FV)')
    print('=' * 80)

    sample = matches_df.sort_values('best_fv', ascending=False).head(20)

    print(f'{"Rank":<6} {"FanGraphs Name":<25} {"Our Name":<25} {"FV":<5} {"Score":<6}')
    print('-' * 80)

    for _, row in sample.iterrows():
        rank = int(row['best_rank']) if pd.notna(row['best_rank']) else '-'
        fv = int(row['best_fv']) if pd.notna(row['best_fv']) else '-'
        score = int(row['match_score'])

        print(f'{str(rank):<6} {row["fg_name"]:<25} {row["our_name"]:<25} {str(fv):<5} {score}%')


async def verify_mlb_linkage():
    """Verify we can now link FanGraphs grades to MLB performance."""
    print('\n' + '=' * 80)
    print('VERIFYING MLB DATA LINKAGE')
    print('=' * 80)

    async with engine.begin() as conn:
        # Check if we have MiLB game logs
        result = await conn.execute(text('''
            SELECT COUNT(DISTINCT p.id) as prospect_count,
                   COUNT(DISTINCT gl.game_pk) as game_count,
                   MIN(gl.season) as earliest_season,
                   MAX(gl.season) as latest_season
            FROM prospects p
            INNER JOIN milb_game_logs gl ON gl.mlb_player_id = p.mlb_player_id
            WHERE p.fg_player_id IS NOT NULL
              AND gl.season >= 2022
        '''))

        row = result.fetchone()
        print(f'\nMiLB Game Logs (2022+):')
        print(f'  Prospects with FG ID + MiLB data: {row[0]}')
        print(f'  Total games: {row[1]:,}')
        print(f'  Season range: {row[2]}-{row[3]}')

        # Show prospects with both FG grades and recent performance
        result = await conn.execute(text('''
            SELECT
                p.name,
                p.fg_player_id,
                fg.report_year,
                fg.fv,
                fg.hit_future,
                fg.game_pwr_future,
                COUNT(DISTINCT gl.game_pk) as games,
                SUM(gl.pa) as total_pa
            FROM prospects p
            INNER JOIN fangraphs_prospect_grades fg ON fg.fg_player_id = p.fg_player_id
            INNER JOIN milb_game_logs gl ON gl.mlb_player_id = p.mlb_player_id
            WHERE fg.report_year = 2024
              AND gl.season = 2024
              AND fg.hit_future IS NOT NULL
            GROUP BY p.name, p.fg_player_id, fg.report_year, fg.fv, fg.hit_future, fg.game_pwr_future
            ORDER BY fg.fv DESC NULLS LAST
            LIMIT 10
        '''))

        print('\nSample: 2024 FG Grades + 2024 MiLB Performance')
        print(f'{"Player":<25} {"FV":<5} {"Hit":<5} {"Pwr":<5} {"Games":<7} {"PA":<7}')
        print('-' * 65)

        for row in result:
            fv = int(row[3]) if row[3] else '-'
            hit = int(row[4]) if row[4] else '-'
            pwr = int(row[5]) if row[5] else '-'
            games = int(row[6])
            pa = int(row[7])

            print(f'{row[0]:<25} {str(fv):<5} {str(hit):<5} {str(pwr):<5} {games:<7} {pa:<7}')


async def main():
    print('=' * 80)
    print('LINK FANGRAPHS IDS TO PROSPECTS')
    print('=' * 80)

    # Load data
    fg_prospects = await load_fangraphs_prospects()
    our_prospects = await load_our_prospects()

    # Match prospects
    matches_df = match_prospects(fg_prospects, our_prospects)

    # Show samples
    await show_sample_matches(matches_df)

    # Update database
    await update_prospect_links(matches_df)

    # Verify MLB linkage
    await verify_mlb_linkage()

    print('\n' + '=' * 80)
    print('LINKAGE COMPLETE')
    print('=' * 80)
    print('\nYou can now:')
    print('  1. Train ML models: FanGraphs grades -> MLB/MiLB performance')
    print('  2. Analyze which scouting grades are most predictive')
    print('  3. Integrate FG-based predictions into V7 rankings')


if __name__ == '__main__':
    asyncio.run(main())
