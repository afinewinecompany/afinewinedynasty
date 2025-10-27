"""
ROBUST INVESTIGATION FRAMEWORK FOR BRYCE ELDRIDGE AA/AAA DATA
Uses multiple fallback methods to find games across all possible data sources
"""

import asyncio
import aiohttp
import psycopg2
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

# Complete sport ID mapping
SPORT_ID_MAP = {
    1: 'MLB',
    11: 'AAA',
    12: 'AA',
    13: 'A+',
    14: 'A',
    15: 'Rk',
    16: 'FRk',
    5442: 'CPX',
    # Additional historical sport IDs
    21: 'Independent',
    23: 'College',
    31: 'International',
    586: 'FCL',  # Florida Complex League
}

# All possible game type codes
GAME_TYPE_CODES = ['R', 'S', 'E', 'F', 'D', 'L', 'W', 'C', 'A', 'I', 'P']

class BryceEldridgeInvestigator:
    """Comprehensive investigation framework using multiple fallback methods"""

    def __init__(self, mlb_player_id=805811):
        self.mlb_player_id = mlb_player_id
        self.seasons = [2022, 2023, 2024, 2025]
        self.findings = {
            'database': {},
            'api': {},
            'discrepancies': [],
            'recommendations': []
        }

    def connect_db(self):
        """Create database connection"""
        return psycopg2.connect(DB_URL)

    # =========================================================================
    # DATABASE INVESTIGATION METHODS
    # =========================================================================

    def investigate_database_comprehensive(self):
        """Run all database diagnostic queries"""
        logger.info("="*80)
        logger.info("DATABASE INVESTIGATION - COMPREHENSIVE DIAGNOSTICS")
        logger.info("="*80)

        conn = self.connect_db()
        cursor = conn.cursor()

        # Query 1: All games in database for this player
        logger.info("\n[1/7] Checking all game logs for player...")
        cursor.execute("""
            SELECT season, level, COUNT(DISTINCT game_pk) as games,
                   SUM(plate_appearances) as total_pa,
                   MIN(game_date) as first_date, MAX(game_date) as last_date
            FROM milb_game_logs
            WHERE mlb_player_id = %s
            GROUP BY season, level
            ORDER BY season DESC, level
        """, (self.mlb_player_id,))

        game_log_results = cursor.fetchall()
        if game_log_results:
            logger.info(f"  Found {len(game_log_results)} season/level combinations:")
            for row in game_log_results:
                season, level, games, pa, first, last = row
                expected_pitches = int(pa * 4.5) if pa else 0
                logger.info(f"    {season} {level}: {games} games, {pa} PAs, ~{expected_pitches} pitches")
                logger.info(f"      Date range: {first} to {last}")

                self.findings['database'][f"{season}_{level}"] = {
                    'games': games,
                    'pa': pa,
                    'expected_pitches': expected_pitches,
                    'first_date': str(first),
                    'last_date': str(last)
                }
        else:
            logger.warning("  NO GAME LOGS FOUND IN DATABASE")

        # Query 2: AA/AAA games with flexible matching
        logger.info("\n[2/7] Searching for AA/AAA games with pattern matching...")
        cursor.execute("""
            SELECT game_pk, game_date, level, team, opponent, plate_appearances
            FROM milb_game_logs
            WHERE mlb_player_id = %s
              AND (
                level = 'AA' OR level = 'AAA' OR
                level ILIKE '%%AA%%' OR
                level ILIKE '%%double%%' OR
                level ILIKE '%%triple%%'
              )
            ORDER BY game_date
        """, (self.mlb_player_id,))

        aa_aaa_games = cursor.fetchall()
        if aa_aaa_games:
            logger.info(f"  Found {len(aa_aaa_games)} AA/AAA games:")
            for game in aa_aaa_games:
                logger.info(f"    {game[1]} | {game[2]} | {game[3]} vs {game[4]} | {game[5]} PAs")
        else:
            logger.info("  NO AA/AAA games found")

        # Query 3: Check pitch data
        logger.info("\n[3/7] Checking pitch data table...")
        cursor.execute("""
            SELECT season, level, COUNT(DISTINCT game_pk) as games,
                   COUNT(*) as total_pitches,
                   MIN(game_date) as first_date, MAX(game_date) as last_date
            FROM milb_batter_pitches
            WHERE mlb_batter_id = %s
            GROUP BY season, level
            ORDER BY season DESC, level
        """, (self.mlb_player_id,))

        pitch_results = cursor.fetchall()
        if pitch_results:
            logger.info(f"  Found {len(pitch_results)} season/level combinations:")
            for row in pitch_results:
                season, level, games, pitches, first, last = row
                logger.info(f"    {season} {level}: {games} games, {pitches} pitches")
                logger.info(f"      Date range: {first} to {last}")
        else:
            logger.info("  NO PITCH DATA FOUND")

        # Query 4: Cross-reference pitch data vs game logs
        logger.info("\n[4/7] Cross-referencing pitch data with game logs...")
        cursor.execute("""
            SELECT
                bp.game_pk,
                bp.game_date,
                bp.level as pitch_level,
                gl.level as gamelog_level,
                COUNT(*) as pitch_count,
                gl.plate_appearances
            FROM milb_batter_pitches bp
            LEFT JOIN milb_game_logs gl
                ON bp.game_pk = gl.game_pk
                AND bp.mlb_batter_id = gl.mlb_player_id
            WHERE bp.mlb_batter_id = %s
            GROUP BY bp.game_pk, bp.game_date, bp.level, gl.level, gl.plate_appearances
            ORDER BY bp.game_date
        """, (self.mlb_player_id,))

        cross_ref = cursor.fetchall()
        if cross_ref:
            logger.info(f"  Found {len(cross_ref)} games with pitch data:")
            mismatches = 0
            for row in cross_ref:
                game_pk, date, pitch_lvl, log_lvl, pitches, pa = row
                if pitch_lvl != log_lvl:
                    mismatches += 1
                    logger.warning(f"    [MISMATCH] {date} | game_pk={game_pk}")
                    logger.warning(f"      Pitch level: {pitch_lvl}, Game log level: {log_lvl}")
                    logger.warning(f"      {pitches} pitches, {pa} PAs")

                    self.findings['discrepancies'].append({
                        'game_pk': game_pk,
                        'date': str(date),
                        'pitch_level': pitch_lvl,
                        'gamelog_level': log_lvl,
                        'pitches': pitches
                    })
                else:
                    logger.info(f"    [OK] {date} | {pitch_lvl} | {pitches} pitches, {pa} PAs")

            if mismatches > 0:
                logger.warning(f"\n  WARNING: Found {mismatches} level mismatches!")

        # Query 5: Check for orphaned pitch data
        logger.info("\n[5/7] Checking for orphaned pitch data (no corresponding game log)...")
        cursor.execute("""
            SELECT bp.game_pk, bp.game_date, bp.level, COUNT(*) as pitches
            FROM milb_batter_pitches bp
            LEFT JOIN milb_game_logs gl
                ON bp.game_pk = gl.game_pk
                AND bp.mlb_batter_id = gl.mlb_player_id
            WHERE bp.mlb_batter_id = %s
              AND gl.game_pk IS NULL
            GROUP BY bp.game_pk, bp.game_date, bp.level
            ORDER BY bp.game_date
        """, (self.mlb_player_id,))

        orphaned = cursor.fetchall()
        if orphaned:
            logger.warning(f"  Found {len(orphaned)} orphaned games (pitch data without game log):")
            for row in orphaned:
                logger.warning(f"    {row[1]} | game_pk={row[0]} | {row[2]} | {row[3]} pitches")
        else:
            logger.info("  No orphaned pitch data")

        # Query 6: Verify level values exist in database
        logger.info("\n[6/7] Verifying AA/AAA level values exist in database...")
        cursor.execute("""
            SELECT level, COUNT(*) as games
            FROM milb_game_logs
            WHERE season IN (2023, 2024, 2025)
              AND level IN ('AA', 'AAA')
            GROUP BY level
        """)

        level_counts = cursor.fetchall()
        for level, count in level_counts:
            logger.info(f"  {level}: {count:,} games in database")

        # Query 7: Check prospects table mapping
        logger.info("\n[7/7] Verifying player ID mapping in prospects table...")
        cursor.execute("""
            SELECT name, mlb_player_id, fg_player_id, position, current_level
            FROM prospects
            WHERE mlb_player_id = %s
        """, (str(self.mlb_player_id),))

        prospect_info = cursor.fetchone()
        if prospect_info:
            logger.info(f"  Found: {prospect_info[0]}")
            logger.info(f"    MLB ID: {prospect_info[1]}, FG ID: {prospect_info[2]}")
            logger.info(f"    Position: {prospect_info[3]}, Level: {prospect_info[4]}")

        conn.close()

    # =========================================================================
    # MLB API INVESTIGATION METHODS
    # =========================================================================

    async def investigate_api_all_seasons(self, session):
        """Check MLB API for all seasons"""
        logger.info("\n" + "="*80)
        logger.info("MLB API INVESTIGATION - ALL SEASONS")
        logger.info("="*80)

        for season in self.seasons:
            logger.info(f"\n[SEASON {season}]")

            # Try each game type
            found_data = False

            for game_type in GAME_TYPE_CODES:
                url = f"https://statsapi.mlb.com/api/v1/people/{self.mlb_player_id}/stats"
                params = {
                    'stats': 'gameLog',
                    'group': 'hitting',
                    'gameType': game_type,
                    'season': season
                }

                try:
                    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status != 200:
                            continue

                        data = await resp.json()

                        if not data.get('stats') or not data['stats'][0].get('splits'):
                            continue

                        splits = data['stats'][0]['splits']

                        # Group by level
                        by_level = {}
                        for split in splits:
                            sport_id = split.get('game', {}).get('sport', {}).get('id')
                            level = SPORT_ID_MAP.get(sport_id, f"Sport_{sport_id}")

                            if level not in by_level:
                                by_level[level] = []
                            by_level[level].append(split)

                        if by_level:
                            found_data = True
                            logger.info(f"  Game Type '{game_type}':")

                            for level, level_splits in sorted(by_level.items()):
                                total_pa = sum(s.get('stat', {}).get('plateAppearances', 0) for s in level_splits)
                                expected_pitches = int(total_pa * 4.5)

                                logger.info(f"    {level}: {len(level_splits)} games, {total_pa} PAs, ~{expected_pitches} pitches")

                                # Store in findings
                                key = f"{season}_{level}_{game_type}"
                                self.findings['api'][key] = {
                                    'games': len(level_splits),
                                    'pa': total_pa,
                                    'expected_pitches': expected_pitches,
                                    'game_type': game_type
                                }

                                # Show sample game_pks
                                sample_pks = [s.get('game', {}).get('gamePk') for s in level_splits[:3]]
                                logger.info(f"      Sample game_pks: {', '.join(map(str, sample_pks))}")

                    await asyncio.sleep(0.2)  # Rate limiting

                except Exception as e:
                    logger.debug(f"Error checking {season}/{game_type}: {e}")

            if not found_data:
                logger.info(f"  No data found in API for {season}")

    async def investigate_api_career_stats(self, session):
        """Check career stats endpoint"""
        logger.info("\n" + "="*80)
        logger.info("MLB API - CAREER STATS")
        logger.info("="*80)

        url = f"https://statsapi.mlb.com/api/v1/people/{self.mlb_player_id}/stats"
        params = {
            'stats': 'yearByYearAdvanced',
            'group': 'hitting'
        }

        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.error(f"  API returned status {resp.status}")
                    return

                data = await resp.json()

                if not data.get('stats') or not data['stats'][0].get('splits'):
                    logger.info("  No career stats found")
                    return

                splits = data['stats'][0]['splits']
                logger.info(f"  Found {len(splits)} career stat entries:")

                total_pa_career = 0

                for split in splits:
                    season = split.get('season')
                    team = split.get('team', {}).get('name', 'Unknown')
                    sport = split.get('sport', {})
                    sport_id = sport.get('id')
                    level = SPORT_ID_MAP.get(sport_id, sport.get('name', 'Unknown'))

                    stat = split.get('stat', {})
                    games = stat.get('gamesPlayed', 0)
                    pa = stat.get('plateAppearances', 0)
                    total_pa_career += pa

                    if games > 0:
                        logger.info(f"\n    {season} - {level} ({team})")
                        logger.info(f"      {games} games, {pa} PAs, ~{int(pa * 4.5)} pitches")
                        logger.info(f"      AVG: {stat.get('avg', '.000')}, OPS: {stat.get('ops', '.000')}")

                logger.info(f"\n  CAREER TOTAL: {total_pa_career} PAs, ~{int(total_pa_career * 4.5)} pitches")

        except Exception as e:
            logger.error(f"  Error fetching career stats: {e}")

    async def investigate_api_specific_games(self, session, game_pks):
        """Check specific game_pks in MLB API"""
        logger.info("\n" + "="*80)
        logger.info("MLB API - SPECIFIC GAME INVESTIGATION")
        logger.info("="*80)

        if not game_pks:
            logger.info("  No game_pks provided")
            return

        logger.info(f"  Checking {len(game_pks)} specific games...")

        for game_pk in game_pks:
            url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        logger.warning(f"    game_pk={game_pk}: API returned {resp.status}")
                        continue

                    data = await resp.json()
                    game_data = data.get('gameData', {})

                    game_date = game_data.get('datetime', {}).get('officialDate', 'Unknown')
                    venue = game_data.get('venue', {}).get('name', 'Unknown')
                    away_team = game_data.get('teams', {}).get('away', {}).get('name', 'Unknown')
                    home_team = game_data.get('teams', {}).get('home', {}).get('name', 'Unknown')

                    logger.info(f"\n    game_pk={game_pk} | {game_date}")
                    logger.info(f"      {away_team} @ {home_team} at {venue}")

                    # Check if our player appeared
                    all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])
                    player_appearances = 0
                    pitch_count = 0

                    for play in all_plays:
                        if play.get('matchup', {}).get('batter', {}).get('id') == self.mlb_player_id:
                            player_appearances += 1
                            pitch_count += len([e for e in play.get('playEvents', []) if e.get('isPitch')])

                    if player_appearances > 0:
                        logger.info(f"      Player appeared: {player_appearances} PAs, {pitch_count} pitches")
                    else:
                        logger.warning(f"      Player DID NOT APPEAR in this game!")

                await asyncio.sleep(0.3)

            except Exception as e:
                logger.error(f"    game_pk={game_pk}: Error - {e}")

    # =========================================================================
    # MAIN INVESTIGATION ORCHESTRATOR
    # =========================================================================

    async def run_full_investigation(self):
        """Run complete investigation using all methods"""
        logger.info("\n" + "="*80)
        logger.info(f"COMPREHENSIVE INVESTIGATION: Player {self.mlb_player_id}")
        logger.info("="*80)
        logger.info("\nThis investigation will:")
        logger.info("  1. Check all database tables comprehensively")
        logger.info("  2. Query MLB API for all seasons and game types")
        logger.info("  3. Check career stats endpoint")
        logger.info("  4. Validate specific games")
        logger.info("  5. Cross-reference all data sources")
        logger.info("  6. Generate findings report")

        # Step 1: Database investigation
        self.investigate_database_comprehensive()

        # Step 2: API investigation
        async with aiohttp.ClientSession() as session:
            await self.investigate_api_all_seasons(session)
            await self.investigate_api_career_stats(session)

            # Step 3: If we found any games in database, check them in API
            conn = self.connect_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT game_pk
                FROM milb_game_logs
                WHERE mlb_player_id = %s
                LIMIT 10
            """, (self.mlb_player_id,))
            game_pks = [row[0] for row in cursor.fetchall()]
            conn.close()

            if game_pks:
                await self.investigate_api_specific_games(session, game_pks)

        # Step 4: Generate findings report
        self.generate_findings_report()

    def generate_findings_report(self):
        """Generate comprehensive findings report"""
        logger.info("\n" + "="*80)
        logger.info("FINDINGS REPORT")
        logger.info("="*80)

        logger.info("\n[DATABASE SUMMARY]")
        if self.findings['database']:
            for key, data in self.findings['database'].items():
                logger.info(f"  {key}: {data['games']} games, {data['pa']} PAs, ~{data['expected_pitches']} pitches")
        else:
            logger.info("  No data found in database")

        logger.info("\n[API SUMMARY]")
        if self.findings['api']:
            for key, data in self.findings['api'].items():
                logger.info(f"  {key}: {data['games']} games, {data['pa']} PAs, ~{data['expected_pitches']} pitches")
        else:
            logger.info("  No data found in API")

        logger.info("\n[DISCREPANCIES]")
        if self.findings['discrepancies']:
            logger.warning(f"  Found {len(self.findings['discrepancies'])} discrepancies:")
            for disc in self.findings['discrepancies']:
                logger.warning(f"    game_pk={disc['game_pk']} | {disc['date']}")
                logger.warning(f"      Pitch level: {disc['pitch_level']}, Game log level: {disc['gamelog_level']}")
        else:
            logger.info("  No discrepancies found")

        logger.info("\n[RECOMMENDATIONS]")

        # Generate recommendations based on findings
        db_total = sum(d.get('expected_pitches', 0) for d in self.findings['database'].values())
        api_total = sum(d.get('expected_pitches', 0) for d in self.findings['api'].values())

        if db_total == 0 and api_total == 0:
            logger.warning("  1. NO DATA FOUND in either database or API")
            logger.warning("  2. Player may not have played in tracked leagues/seasons")
            logger.warning("  3. Verify player ID is correct")
            logger.warning("  4. Check if data exists in alternative sources")
        elif db_total < api_total:
            logger.warning("  1. Database is MISSING data that exists in API")
            logger.warning(f"  2. Expected ~{api_total} pitches from API, only {db_total} in database")
            logger.warning("  3. Run collection scripts to backfill missing games")
        elif len(self.findings['discrepancies']) > 0:
            logger.warning("  1. Level attribution MISMATCH detected")
            logger.warning("  2. Re-run collection scripts with correct level extraction")
        else:
            logger.info("  1. Data appears complete and consistent")
            logger.info("  2. Database matches API data")


async def main():
    """Main entry point"""
    investigator = BryceEldridgeInvestigator(mlb_player_id=805811)
    await investigator.run_full_investigation()


if __name__ == "__main__":
    asyncio.run(main())
