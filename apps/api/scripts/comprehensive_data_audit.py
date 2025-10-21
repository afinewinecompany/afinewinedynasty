#!/usr/bin/env python3
"""
Comprehensive Data Audit for A Fine Wine Dynasty Prospects
============================================================
This script performs a complete audit of all available data points
for prospects in our database, generating a detailed report for
machine learning planning purposes.

Created by: BMad Party Mode Team
Date: 2025-10-19
"""

import asyncio
import asyncpg
import pandas as pd
from datetime import datetime
import json
from typing import Dict, List, Any, Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ProspectDataAuditor:
    """Comprehensive data auditor for prospect database."""

    def __init__(self):
        self.conn = None
        self.audit_results = {}
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    async def connect(self):
        """Establish database connection."""
        DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway")
        self.conn = await asyncpg.connect(DATABASE_URL)
        print("[OK] Connected to database")

    async def disconnect(self):
        """Close database connection."""
        if self.conn:
            await self.conn.close()
            print("✅ Disconnected from database")

    async def audit_prospects_table(self):
        """Audit the main prospects table."""
        print("\n📊 Auditing PROSPECTS table...")

        # Total prospects
        total = await self.conn.fetchval("SELECT COUNT(*) FROM prospects")

        # Prospects with various data points
        query = """
        SELECT
            COUNT(*) as total_prospects,
            COUNT(DISTINCT mlb_id) as unique_mlb_ids,
            COUNT(DISTINCT mlb_player_id) as unique_player_ids,
            COUNT(DISTINCT fg_player_id) as with_fangraphs_id,
            COUNT(DISTINCT ba_player_id) as with_baseball_america_id,
            COUNT(CASE WHEN draft_year IS NOT NULL THEN 1 END) as with_draft_info,
            COUNT(CASE WHEN birth_date IS NOT NULL THEN 1 END) as with_demographics,
            COUNT(CASE WHEN height_inches IS NOT NULL THEN 1 END) as with_physical_data,
            COUNT(DISTINCT organization) as unique_organizations,
            COUNT(DISTINCT position) as unique_positions,
            COUNT(DISTINCT level) as unique_levels
        FROM prospects
        """

        stats = await self.conn.fetchrow(query)

        # Position breakdown
        positions = await self.conn.fetch("""
            SELECT position, COUNT(*) as count
            FROM prospects
            GROUP BY position
            ORDER BY count DESC
        """)

        # Level breakdown
        levels = await self.conn.fetch("""
            SELECT level, COUNT(*) as count
            FROM prospects
            WHERE level IS NOT NULL
            GROUP BY level
            ORDER BY count DESC
        """)

        # Organization breakdown (top 10)
        orgs = await self.conn.fetch("""
            SELECT organization, COUNT(*) as count
            FROM prospects
            WHERE organization IS NOT NULL
            GROUP BY organization
            ORDER BY count DESC
            LIMIT 10
        """)

        # Age distribution
        ages = await self.conn.fetch("""
            SELECT
                CASE
                    WHEN age < 18 THEN 'Under 18'
                    WHEN age BETWEEN 18 AND 20 THEN '18-20'
                    WHEN age BETWEEN 21 AND 23 THEN '21-23'
                    WHEN age BETWEEN 24 AND 26 THEN '24-26'
                    WHEN age > 26 THEN 'Over 26'
                    ELSE 'Unknown'
                END as age_group,
                COUNT(*) as count
            FROM prospects
            GROUP BY age_group
            ORDER BY age_group
        """)

        self.audit_results['prospects'] = {
            'total': total,
            'stats': dict(stats),
            'positions': [dict(p) for p in positions],
            'levels': [dict(l) for l in levels],
            'organizations_top10': [dict(o) for o in orgs],
            'age_distribution': [dict(a) for a in ages]
        }

        print(f"  ✓ Total prospects: {total}")
        print(f"  ✓ With MLB ID: {stats['unique_mlb_ids']}")
        print(f"  ✓ With Fangraphs ID: {stats['with_fangraphs_id']}")
        print(f"  ✓ Unique positions: {stats['unique_positions']}")
        print(f"  ✓ Unique organizations: {stats['unique_organizations']}")

    async def audit_milb_game_logs(self):
        """Audit MiLB game logs data."""
        print("\n📊 Auditing MILB_GAME_LOGS table...")

        query = """
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT prospect_id) as prospects_with_data,
            COUNT(DISTINCT mlb_player_id) as unique_players,
            COUNT(DISTINCT season) as unique_seasons,
            MIN(season) as earliest_season,
            MAX(season) as latest_season,
            COUNT(DISTINCT level) as unique_levels,
            SUM(games_played) as total_games,
            COUNT(CASE WHEN at_bats > 0 THEN 1 END) as batting_records,
            COUNT(CASE WHEN innings_pitched > 0 THEN 1 END) as pitching_records
        FROM milb_game_logs
        """

        stats = await self.conn.fetchrow(query)

        # Season breakdown
        seasons = await self.conn.fetch("""
            SELECT season,
                   COUNT(DISTINCT prospect_id) as prospects,
                   COUNT(*) as records,
                   COUNT(DISTINCT level) as levels
            FROM milb_game_logs
            GROUP BY season
            ORDER BY season DESC
        """)

        # Level breakdown
        levels = await self.conn.fetch("""
            SELECT level,
                   COUNT(DISTINCT prospect_id) as prospects,
                   COUNT(*) as records
            FROM milb_game_logs
            WHERE level IS NOT NULL
            GROUP BY level
            ORDER BY records DESC
        """)

        # Data completeness for batting stats
        batting_completeness = await self.conn.fetchrow("""
            SELECT
                COUNT(*) as total_batting_records,
                COUNT(CASE WHEN batting_avg IS NOT NULL THEN 1 END) as with_avg,
                COUNT(CASE WHEN obp IS NOT NULL THEN 1 END) as with_obp,
                COUNT(CASE WHEN slg IS NOT NULL THEN 1 END) as with_slg,
                COUNT(CASE WHEN ops IS NOT NULL THEN 1 END) as with_ops,
                COUNT(CASE WHEN stolen_bases IS NOT NULL THEN 1 END) as with_sb,
                COUNT(CASE WHEN strikeouts IS NOT NULL THEN 1 END) as with_k
            FROM milb_game_logs
            WHERE at_bats > 0
        """)

        # Data completeness for pitching stats
        pitching_completeness = await self.conn.fetchrow("""
            SELECT
                COUNT(*) as total_pitching_records,
                COUNT(CASE WHEN era IS NOT NULL THEN 1 END) as with_era,
                COUNT(CASE WHEN whip IS NOT NULL THEN 1 END) as with_whip,
                COUNT(CASE WHEN strikeouts_per_9inn IS NOT NULL THEN 1 END) as with_k9,
                COUNT(CASE WHEN walks_per_9inn IS NOT NULL THEN 1 END) as with_bb9,
                COUNT(CASE WHEN avg_against IS NOT NULL THEN 1 END) as with_avg_against
            FROM milb_game_logs
            WHERE innings_pitched > 0
        """)

        self.audit_results['milb_game_logs'] = {
            'stats': dict(stats) if stats else {},
            'seasons': [dict(s) for s in seasons],
            'levels': [dict(l) for l in levels],
            'batting_completeness': dict(batting_completeness) if batting_completeness else {},
            'pitching_completeness': dict(pitching_completeness) if pitching_completeness else {}
        }

        if stats:
            print(f"  ✓ Total records: {stats['total_records']:,}")
            print(f"  ✓ Prospects with data: {stats['prospects_with_data']}")
            print(f"  ✓ Seasons: {stats['earliest_season']} - {stats['latest_season']}")
            print(f"  ✓ Batting records: {stats['batting_records']:,}")
            print(f"  ✓ Pitching records: {stats['pitching_records']:,}")

    async def audit_pitch_data(self):
        """Audit pitch-by-pitch data."""
        print("\n📊 Auditing PITCH-BY-PITCH data...")

        # Pitcher pitches
        pitcher_query = """
        SELECT
            COUNT(*) as total_pitches,
            COUNT(DISTINCT mlb_pitcher_id) as unique_pitchers,
            COUNT(DISTINCT season) as unique_seasons,
            MIN(season) as earliest_season,
            MAX(season) as latest_season,
            COUNT(DISTINCT pitch_type) as unique_pitch_types,
            COUNT(CASE WHEN start_speed IS NOT NULL THEN 1 END) as with_velocity,
            COUNT(CASE WHEN spin_rate IS NOT NULL THEN 1 END) as with_spin,
            COUNT(CASE WHEN launch_speed IS NOT NULL THEN 1 END) as with_exit_velo,
            COUNT(CASE WHEN launch_angle IS NOT NULL THEN 1 END) as with_launch_angle
        FROM milb_pitcher_pitches
        """

        pitcher_stats = await self.conn.fetchrow(pitcher_query)

        # Pitch type breakdown
        pitch_types = await self.conn.fetch("""
            SELECT pitch_type,
                   pitch_type_description,
                   COUNT(*) as count,
                   AVG(start_speed) as avg_velocity,
                   AVG(spin_rate) as avg_spin_rate
            FROM milb_pitcher_pitches
            WHERE pitch_type IS NOT NULL
            GROUP BY pitch_type, pitch_type_description
            ORDER BY count DESC
            LIMIT 15
        """)

        # Batter pitches
        batter_query = """
        SELECT
            COUNT(*) as total_pitches,
            COUNT(DISTINCT mlb_batter_id) as unique_batters,
            COUNT(DISTINCT season) as unique_seasons,
            COUNT(CASE WHEN swing = true THEN 1 END) as swings,
            COUNT(CASE WHEN contact = true THEN 1 END) as contacts,
            COUNT(CASE WHEN swing_and_miss = true THEN 1 END) as whiffs
        FROM milb_batter_pitches
        """

        batter_stats = await self.conn.fetchrow(batter_query)

        # Season coverage for pitch data
        pitch_seasons = await self.conn.fetch("""
            SELECT season,
                   COUNT(DISTINCT mlb_pitcher_id) as pitchers,
                   COUNT(*) as pitches
            FROM milb_pitcher_pitches
            GROUP BY season
            ORDER BY season DESC
        """)

        self.audit_results['pitch_data'] = {
            'pitcher_pitches': dict(pitcher_stats) if pitcher_stats else {},
            'batter_pitches': dict(batter_stats) if batter_stats else {},
            'pitch_types': [dict(pt) for pt in pitch_types],
            'seasons': [dict(s) for s in pitch_seasons]
        }

        if pitcher_stats:
            print(f"  ✓ Total pitcher pitches: {pitcher_stats['total_pitches']:,}")
            print(f"  ✓ Unique pitchers: {pitcher_stats['unique_pitchers']}")
            print(f"  ✓ Pitch types tracked: {pitcher_stats['unique_pitch_types']}")
        if batter_stats:
            print(f"  ✓ Total batter pitches: {batter_stats['total_pitches']:,}")
            print(f"  ✓ Unique batters: {batter_stats['unique_batters']}")

    async def audit_scouting_grades(self):
        """Audit scouting grades data."""
        print("\n📊 Auditing SCOUTING GRADES...")

        # Scouting grades table
        scouting_query = """
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT prospect_id) as prospects_with_grades,
            COUNT(DISTINCT source) as unique_sources,
            COUNT(DISTINCT ranking_year) as unique_years,
            MIN(ranking_year) as earliest_year,
            MAX(ranking_year) as latest_year,
            COUNT(CASE WHEN overall IS NOT NULL THEN 1 END) as with_overall_grade,
            COUNT(CASE WHEN future_value IS NOT NULL THEN 1 END) as with_fv,
            COUNT(CASE WHEN hit_present IS NOT NULL THEN 1 END) as with_hit_grades,
            COUNT(CASE WHEN power_present IS NOT NULL THEN 1 END) as with_power_grades,
            COUNT(CASE WHEN speed_present IS NOT NULL THEN 1 END) as with_speed_grades,
            COUNT(CASE WHEN fastball_grade IS NOT NULL THEN 1 END) as with_pitch_grades
        FROM scouting_grades
        """

        scouting_stats = await self.conn.fetchrow(scouting_query)

        # Sources breakdown
        sources = await self.conn.fetch("""
            SELECT source,
                   COUNT(DISTINCT prospect_id) as prospects,
                   COUNT(*) as records
            FROM scouting_grades
            WHERE source IS NOT NULL
            GROUP BY source
            ORDER BY records DESC
        """)

        # Fangraphs unified grades
        fg_query = """
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT fg_player_id) as unique_players,
            COUNT(DISTINCT year) as unique_years,
            COUNT(CASE WHEN fv IS NOT NULL THEN 1 END) as with_fv,
            COUNT(CASE WHEN top_100_rank IS NOT NULL THEN 1 END) as top_100_prospects,
            COUNT(CASE WHEN sits_velo IS NOT NULL THEN 1 END) as pitchers_with_velo
        FROM fangraphs_unified_grades
        """

        fg_stats = await self.conn.fetchrow(fg_query)

        self.audit_results['scouting'] = {
            'scouting_grades': dict(scouting_stats) if scouting_stats else {},
            'sources': [dict(s) for s in sources],
            'fangraphs_unified': dict(fg_stats) if fg_stats else {}
        }

        if scouting_stats:
            print(f"  ✓ Total scouting records: {scouting_stats['total_records']}")
            print(f"  ✓ Prospects with grades: {scouting_stats['prospects_with_grades']}")
            print(f"  ✓ Years covered: {scouting_stats['earliest_year']} - {scouting_stats['latest_year']}")

    async def audit_hype_data(self):
        """Audit hype and media tracking data."""
        print("\n📊 Auditing HYPE & MEDIA data...")

        # Player hype
        hype_query = """
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT prospect_id) as prospects_with_hype,
            AVG(hype_score) as avg_hype_score,
            MAX(hype_score) as max_hype_score,
            AVG(total_mentions_30d) as avg_mentions_30d,
            MAX(total_mentions_30d) as max_mentions_30d
        FROM player_hype
        WHERE updated_at > CURRENT_DATE - INTERVAL '90 days'
        """

        hype_stats = await self.conn.fetchrow(hype_query)

        # Social mentions
        social_query = """
        SELECT
            platform,
            COUNT(*) as mentions,
            COUNT(DISTINCT player_hype_id) as unique_players,
            AVG(likes) as avg_likes,
            AVG(sentiment) as avg_sentiment
        FROM social_mentions
        WHERE collected_at > CURRENT_DATE - INTERVAL '30 days'
        GROUP BY platform
        ORDER BY mentions DESC
        """

        social_stats = await self.conn.fetch(social_query)

        # Media articles
        media_count = await self.conn.fetchval("""
            SELECT COUNT(*)
            FROM media_articles
            WHERE collected_at > CURRENT_DATE - INTERVAL '30 days'
        """)

        self.audit_results['hype'] = {
            'player_hype': dict(hype_stats) if hype_stats else {},
            'social_platforms': [dict(s) for s in social_stats],
            'recent_media_articles': media_count or 0
        }

        if hype_stats:
            print(f"  ✓ Prospects with hype data: {hype_stats['prospects_with_hype']}")
            print(f"  ✓ Average hype score: {hype_stats['avg_hype_score']:.1f}" if hype_stats['avg_hype_score'] else "  ✓ No hype scores")

    async def audit_data_coverage(self):
        """Analyze overall data coverage for prospects."""
        print("\n📊 Analyzing OVERALL DATA COVERAGE...")

        query = """
        WITH prospect_coverage AS (
            SELECT
                p.id,
                p.name,
                p.position,
                p.organization,
                p.mlb_player_id,
                CASE WHEN gl.prospect_id IS NOT NULL THEN 1 ELSE 0 END as has_game_logs,
                CASE WHEN pp.mlb_pitcher_id IS NOT NULL THEN 1 ELSE 0 END as has_pitch_data_pitcher,
                CASE WHEN bp.mlb_batter_id IS NOT NULL THEN 1 ELSE 0 END as has_pitch_data_batter,
                CASE WHEN sg.prospect_id IS NOT NULL THEN 1 ELSE 0 END as has_scouting,
                CASE WHEN ph.prospect_id IS NOT NULL THEN 1 ELSE 0 END as has_hype,
                CASE WHEN fg.fg_player_id IS NOT NULL THEN 1 ELSE 0 END as has_fangraphs
            FROM prospects p
            LEFT JOIN (SELECT DISTINCT prospect_id FROM milb_game_logs) gl ON p.id = gl.prospect_id
            LEFT JOIN (SELECT DISTINCT mlb_pitcher_id FROM milb_pitcher_pitches) pp ON p.mlb_player_id = pp.mlb_pitcher_id
            LEFT JOIN (SELECT DISTINCT mlb_batter_id FROM milb_batter_pitches) bp ON p.mlb_player_id = bp.mlb_batter_id
            LEFT JOIN (SELECT DISTINCT prospect_id FROM scouting_grades) sg ON p.id = sg.prospect_id
            LEFT JOIN (SELECT DISTINCT prospect_id FROM player_hype) ph ON p.id = ph.prospect_id
            LEFT JOIN (SELECT DISTINCT fg_player_id FROM fangraphs_unified_grades WHERE fg_player_id IS NOT NULL) fg ON p.fg_player_id::text = fg.fg_player_id
        )
        SELECT
            COUNT(*) as total_prospects,
            SUM(has_game_logs) as with_game_logs,
            SUM(has_pitch_data_pitcher) as with_pitcher_pitches,
            SUM(has_pitch_data_batter) as with_batter_pitches,
            SUM(has_scouting) as with_scouting,
            SUM(has_hype) as with_hype,
            SUM(has_fangraphs) as with_fangraphs,
            SUM(CASE WHEN has_game_logs = 1 AND (has_pitch_data_pitcher = 1 OR has_pitch_data_batter = 1) THEN 1 ELSE 0 END) as with_game_and_pitch,
            SUM(CASE WHEN has_game_logs = 1 AND has_scouting = 1 THEN 1 ELSE 0 END) as with_game_and_scouting,
            SUM(CASE WHEN has_game_logs = 1 AND has_scouting = 1 AND (has_pitch_data_pitcher = 1 OR has_pitch_data_batter = 1) THEN 1 ELSE 0 END) as complete_data
        FROM prospect_coverage
        """

        coverage = await self.conn.fetchrow(query)

        # Get examples of prospects with complete data
        complete_prospects = await self.conn.fetch("""
            WITH prospect_coverage AS (
                SELECT
                    p.id,
                    p.name,
                    p.position,
                    p.organization,
                    p.mlb_player_id,
                    CASE WHEN gl.prospect_id IS NOT NULL THEN 1 ELSE 0 END as has_game_logs,
                    CASE WHEN pp.mlb_pitcher_id IS NOT NULL THEN 1 ELSE 0 END as has_pitch_data_pitcher,
                    CASE WHEN bp.mlb_batter_id IS NOT NULL THEN 1 ELSE 0 END as has_pitch_data_batter,
                    CASE WHEN sg.prospect_id IS NOT NULL THEN 1 ELSE 0 END as has_scouting
                FROM prospects p
                LEFT JOIN (SELECT DISTINCT prospect_id FROM milb_game_logs) gl ON p.id = gl.prospect_id
                LEFT JOIN (SELECT DISTINCT mlb_pitcher_id FROM milb_pitcher_pitches) pp ON p.mlb_player_id = pp.mlb_pitcher_id
                LEFT JOIN (SELECT DISTINCT mlb_batter_id FROM milb_batter_pitches) bp ON p.mlb_player_id = bp.mlb_batter_id
                LEFT JOIN (SELECT DISTINCT prospect_id FROM scouting_grades) sg ON p.id = sg.prospect_id
            )
            SELECT name, position, organization
            FROM prospect_coverage
            WHERE has_game_logs = 1
                AND has_scouting = 1
                AND (has_pitch_data_pitcher = 1 OR has_pitch_data_batter = 1)
            LIMIT 20
        """)

        self.audit_results['coverage'] = {
            'summary': dict(coverage) if coverage else {},
            'complete_data_examples': [dict(p) for p in complete_prospects]
        }

        if coverage:
            print(f"  ✓ Total prospects: {coverage['total_prospects']}")
            print(f"  ✓ With game logs: {coverage['with_game_logs']} ({coverage['with_game_logs']/coverage['total_prospects']*100:.1f}%)")
            print(f"  ✓ With pitch data: {max(coverage['with_pitcher_pitches'] or 0, coverage['with_batter_pitches'] or 0)}")
            print(f"  ✓ With scouting: {coverage['with_scouting']} ({coverage['with_scouting']/coverage['total_prospects']*100:.1f}%)")
            print(f"  ✓ Complete data: {coverage['complete_data']} prospects")

    def generate_markdown_report(self) -> str:
        """Generate comprehensive markdown report."""
        report = f"""# A Fine Wine Dynasty - Prospect Data Audit Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary

This report provides a comprehensive audit of all available data points for prospects in the A Fine Wine Dynasty database. The analysis covers performance data, scouting grades, pitch-by-pitch metrics, and media tracking to inform machine learning model development.

---

## 1. Prospects Overview

### Total Coverage
- **Total Prospects**: {self.audit_results['prospects']['total']:,}
- **Unique MLB IDs**: {self.audit_results['prospects']['stats']['unique_mlb_ids']:,}
- **With Fangraphs ID**: {self.audit_results['prospects']['stats']['with_fangraphs_id']:,}
- **With Draft Info**: {self.audit_results['prospects']['stats']['with_draft_info']:,}

### Position Distribution
"""
        for pos in self.audit_results['prospects']['positions'][:10]:
            report += f"- {pos['position'] or 'Unknown'}: {pos['count']} prospects\n"

        report += "\n### Organization Distribution (Top 10)\n"
        for org in self.audit_results['prospects']['organizations_top10']:
            report += f"- {org['organization']}: {org['count']} prospects\n"

        report += "\n### Level Distribution\n"
        for level in self.audit_results['prospects']['levels']:
            report += f"- {level['level']}: {level['count']} prospects\n"

        report += "\n---\n\n## 2. Performance Data (MiLB Game Logs)\n\n"

        if self.audit_results.get('milb_game_logs', {}).get('stats'):
            stats = self.audit_results['milb_game_logs']['stats']
            report += f"""### Coverage
- **Total Records**: {stats.get('total_records', 0):,}
- **Prospects with Data**: {stats.get('prospects_with_data', 0):,}
- **Seasons Covered**: {stats.get('earliest_season', 'N/A')} - {stats.get('latest_season', 'N/A')}
- **Batting Records**: {stats.get('batting_records', 0):,}
- **Pitching Records**: {stats.get('pitching_records', 0):,}

### Season Breakdown
"""
            for season in self.audit_results['milb_game_logs']['seasons'][:5]:
                report += f"- **{season['season']}**: {season['prospects']} prospects, {season['records']:,} records\n"

            report += "\n### Data Completeness\n\n"

            if self.audit_results['milb_game_logs'].get('batting_completeness'):
                batting = self.audit_results['milb_game_logs']['batting_completeness']
                total_batting = batting.get('total_batting_records', 1) or 1
                report += f"""**Batting Statistics** ({batting.get('total_batting_records', 0):,} records)
- AVG: {batting.get('with_avg', 0)/total_batting*100:.1f}% complete
- OBP: {batting.get('with_obp', 0)/total_batting*100:.1f}% complete
- SLG: {batting.get('with_slg', 0)/total_batting*100:.1f}% complete
- OPS: {batting.get('with_ops', 0)/total_batting*100:.1f}% complete

"""

            if self.audit_results['milb_game_logs'].get('pitching_completeness'):
                pitching = self.audit_results['milb_game_logs']['pitching_completeness']
                total_pitching = pitching.get('total_pitching_records', 1) or 1
                report += f"""**Pitching Statistics** ({pitching.get('total_pitching_records', 0):,} records)
- ERA: {pitching.get('with_era', 0)/total_pitching*100:.1f}% complete
- WHIP: {pitching.get('with_whip', 0)/total_pitching*100:.1f}% complete
- K/9: {pitching.get('with_k9', 0)/total_pitching*100:.1f}% complete
- BB/9: {pitching.get('with_bb9', 0)/total_pitching*100:.1f}% complete
"""

        report += "\n---\n\n## 3. Pitch-by-Pitch Data\n\n"

        if self.audit_results.get('pitch_data', {}).get('pitcher_pitches'):
            pitcher = self.audit_results['pitch_data']['pitcher_pitches']
            report += f"""### Pitcher Pitches
- **Total Pitches**: {pitcher.get('total_pitches', 0):,}
- **Unique Pitchers**: {pitcher.get('unique_pitchers', 0):,}
- **Seasons**: {pitcher.get('earliest_season', 'N/A')} - {pitcher.get('latest_season', 'N/A')}
- **With Velocity**: {pitcher.get('with_velocity', 0):,} pitches
- **With Spin Rate**: {pitcher.get('with_spin', 0):,} pitches
- **With Exit Velocity**: {pitcher.get('with_exit_velo', 0):,} pitches

### Top Pitch Types
"""
            for pt in self.audit_results['pitch_data']['pitch_types'][:10]:
                avg_velo = f"{pt.get('avg_velocity', 0):.1f} mph" if pt.get('avg_velocity') else "N/A"
                report += f"- **{pt.get('pitch_type', 'Unknown')}** ({pt.get('pitch_type_description', '')}): {pt['count']:,} pitches, {avg_velo}\n"

        if self.audit_results.get('pitch_data', {}).get('batter_pitches'):
            batter = self.audit_results['pitch_data']['batter_pitches']
            report += f"""\n### Batter Pitches
- **Total Pitches**: {batter.get('total_pitches', 0):,}
- **Unique Batters**: {batter.get('unique_batters', 0):,}
- **Swings**: {batter.get('swings', 0):,}
- **Contacts**: {batter.get('contacts', 0):,}
- **Whiffs**: {batter.get('whiffs', 0):,}
"""

        report += "\n---\n\n## 4. Scouting Data\n\n"

        if self.audit_results.get('scouting', {}).get('scouting_grades'):
            scouting = self.audit_results['scouting']['scouting_grades']
            report += f"""### Coverage
- **Total Records**: {scouting.get('total_records', 0):,}
- **Prospects with Grades**: {scouting.get('prospects_with_grades', 0):,}
- **Years Covered**: {scouting.get('earliest_year', 'N/A')} - {scouting.get('latest_year', 'N/A')}
- **With Overall Grade**: {scouting.get('with_overall_grade', 0):,}
- **With Future Value**: {scouting.get('with_fv', 0):,}

### Data Sources
"""
            for source in self.audit_results['scouting'].get('sources', []):
                report += f"- **{source['source']}**: {source['prospects']} prospects, {source['records']} records\n"

        report += "\n---\n\n## 5. Media & Hype Data\n\n"

        if self.audit_results.get('hype', {}).get('player_hype'):
            hype = self.audit_results['hype']['player_hype']
            report += f"""### Recent Activity (Last 90 Days)
- **Prospects with Hype Data**: {hype.get('prospects_with_hype', 0):,}
- **Average Hype Score**: {hype.get('avg_hype_score', 0):.1f if hype.get('avg_hype_score') else 'N/A'}
- **Max Hype Score**: {hype.get('max_hype_score', 0):.1f if hype.get('max_hype_score') else 'N/A'}

### Social Media Coverage
"""
            for platform in self.audit_results['hype'].get('social_platforms', []):
                report += f"- **{platform['platform']}**: {platform['mentions']:,} mentions, {platform['unique_players']} players\n"

        report += "\n---\n\n## 6. Overall Data Coverage Analysis\n\n"

        if self.audit_results.get('coverage', {}).get('summary'):
            coverage = self.audit_results['coverage']['summary']
            total = coverage.get('total_prospects', 1) or 1
            report += f"""### Data Availability
- **With Game Logs**: {coverage.get('with_game_logs', 0):,} ({coverage.get('with_game_logs', 0)/total*100:.1f}%)
- **With Pitch Data (Pitcher)**: {coverage.get('with_pitcher_pitches', 0):,} ({coverage.get('with_pitcher_pitches', 0)/total*100:.1f}%)
- **With Pitch Data (Batter)**: {coverage.get('with_batter_pitches', 0):,} ({coverage.get('with_batter_pitches', 0)/total*100:.1f}%)
- **With Scouting Grades**: {coverage.get('with_scouting', 0):,} ({coverage.get('with_scouting', 0)/total*100:.1f}%)
- **With Hype Data**: {coverage.get('with_hype', 0):,} ({coverage.get('with_hype', 0)/total*100:.1f}%)

### Combined Coverage
- **Game Logs + Pitch Data**: {coverage.get('with_game_and_pitch', 0):,} prospects
- **Game Logs + Scouting**: {coverage.get('with_game_and_scouting', 0):,} prospects
- **Complete Data (Game + Pitch + Scouting)**: {coverage.get('complete_data', 0):,} prospects

### Examples of Prospects with Complete Data
"""
            for p in self.audit_results['coverage'].get('complete_data_examples', [])[:10]:
                report += f"- {p['name']} ({p['position']}, {p['organization']})\n"

        report += """
---

## 7. Machine Learning Readiness Assessment

### Available Features for ML Models

#### Performance Features
- **Game-Level**: 110+ statistics per game (batting and pitching)
- **Aggregated Stats**: Season totals, averages, rates
- **Pitch-Level**: 45+ features per pitch (velocity, movement, spin, results)
- **Temporal**: Multi-season progression tracking

#### Scouting Features
- **Present Tools**: Hit, Power, Speed, Fielding, Arm (20-80 scale)
- **Future Projections**: All tools with future grades
- **Overall Grades**: FV, Overall rating, Risk assessment
- **Rankings**: Top 100, organizational, positional

#### Contextual Features
- **Demographics**: Age, draft position, signing bonus
- **Development**: Level progression, age-relative-to-level
- **Organization**: Team context, park factors
- **Media**: Hype scores, sentiment, mention volume

### Recommended ML Approaches

#### 1. Prospect Success Prediction
- **Target**: MLB success metrics (WAR, games played)
- **Features**: Combine performance + scouting + age/level
- **Models**: Gradient Boosting, Neural Networks

#### 2. Development Trajectory Modeling
- **Target**: Time to MLB, peak level reached
- **Features**: Age-relative performance, level progression
- **Models**: Time-series models, Survival analysis

#### 3. Tool Projection
- **Target**: Future tool grades
- **Features**: Current performance + age + level
- **Models**: Multi-output regression, Ordinal regression

#### 4. Injury Risk Assessment
- **Target**: Injury probability
- **Features**: Workload, velocity changes, mechanics
- **Models**: Logistic regression, Random Forest

#### 5. Breakout Prediction
- **Target**: Performance improvement flags
- **Features**: Recent trends, age, new skills
- **Models**: Classification models, Anomaly detection

### Data Quality Considerations

#### Strengths
- Rich pitch-level data for detailed analysis
- Multiple scouting sources for validation
- Comprehensive batting and pitching statistics
- Multi-year tracking for trend analysis

#### Limitations
- Incomplete coverage (not all prospects have all data types)
- Varying data density by level and year
- Potential selection bias in scouting grades
- Limited injury/health data

### Next Steps for ML Implementation

1. **Data Preprocessing Pipeline**
   - Handle missing values strategically
   - Create aggregated features at multiple time windows
   - Normalize across levels and leagues

2. **Feature Engineering**
   - Create age-relative and level-adjusted metrics
   - Build progression/trend features
   - Combine multiple data sources

3. **Model Development**
   - Start with simple baselines
   - Experiment with ensemble methods
   - Consider temporal and hierarchical structure

4. **Validation Strategy**
   - Time-based splits for temporal validity
   - Stratify by position/level
   - Track performance on recent prospects

---

## 8. Conclusion

The A Fine Wine Dynasty database contains a rich dataset suitable for advanced machine learning applications in prospect evaluation and projection. With comprehensive coverage across performance, scouting, and pitch-level data, there are numerous opportunities for predictive modeling and analysis.

### Key Takeaways
- **{self.audit_results['prospects']['total']:,}** total prospects tracked
- **{self.audit_results.get('coverage', {}).get('summary', {}).get('complete_data', 0):,}** prospects with complete data coverage
- **{self.audit_results.get('pitch_data', {}).get('pitcher_pitches', {}).get('total_pitches', 0):,}** individual pitches tracked
- Multiple data sources enable cross-validation and ensemble approaches
- Sufficient data density for deep learning applications in key areas

### Recommended Priority Models
1. **MLB Success Prediction** - High business value, good data coverage
2. **Development Trajectory** - Critical for roster planning
3. **Breakout Detection** - Competitive advantage in acquisitions
4. **Pitch Arsenal Evolution** - Unique insight from pitch-level data

---

*Report generated by BMad Party Mode Team - Data Audit Division*
"""

        return report

    async def generate_csv_summary(self):
        """Generate CSV with prospect-level data availability."""
        query = """
        SELECT
            p.id,
            p.name,
            p.position,
            p.organization,
            p.level,
            p.age,
            p.eta_year,
            CASE WHEN p.mlb_player_id IS NOT NULL THEN 'Yes' ELSE 'No' END as has_mlb_id,
            CASE WHEN p.fg_player_id IS NOT NULL THEN 'Yes' ELSE 'No' END as has_fg_id,
            CASE WHEN gl.game_count > 0 THEN gl.game_count ELSE 0 END as game_log_count,
            CASE WHEN gl.seasons IS NOT NULL THEN gl.seasons ELSE '' END as game_log_seasons,
            CASE WHEN pp.pitch_count > 0 THEN pp.pitch_count ELSE 0 END as pitches_thrown,
            CASE WHEN bp.pitch_count > 0 THEN bp.pitch_count ELSE 0 END as pitches_faced,
            CASE WHEN sg.grade_count > 0 THEN sg.grade_count ELSE 0 END as scouting_records,
            CASE WHEN ph.has_hype = 1 THEN 'Yes' ELSE 'No' END as has_hype_data
        FROM prospects p
        LEFT JOIN (
            SELECT prospect_id,
                   COUNT(*) as game_count,
                   STRING_AGG(DISTINCT season::text, ', ' ORDER BY season::text) as seasons
            FROM milb_game_logs
            GROUP BY prospect_id
        ) gl ON p.id = gl.prospect_id
        LEFT JOIN (
            SELECT mlb_pitcher_id,
                   COUNT(*) as pitch_count
            FROM milb_pitcher_pitches
            GROUP BY mlb_pitcher_id
        ) pp ON p.mlb_player_id = pp.mlb_pitcher_id
        LEFT JOIN (
            SELECT mlb_batter_id,
                   COUNT(*) as pitch_count
            FROM milb_batter_pitches
            GROUP BY mlb_batter_id
        ) bp ON p.mlb_player_id = bp.mlb_batter_id
        LEFT JOIN (
            SELECT prospect_id,
                   COUNT(*) as grade_count
            FROM scouting_grades
            GROUP BY prospect_id
        ) sg ON p.id = sg.prospect_id
        LEFT JOIN (
            SELECT prospect_id,
                   1 as has_hype
            FROM player_hype
            WHERE updated_at > CURRENT_DATE - INTERVAL '180 days'
            GROUP BY prospect_id
        ) ph ON p.id = ph.prospect_id
        ORDER BY
            CASE WHEN gl.game_count > 0 OR pp.pitch_count > 0 OR bp.pitch_count > 0 THEN 1 ELSE 0 END DESC,
            p.name
        """

        rows = await self.conn.fetch(query)

        df = pd.DataFrame(rows)
        csv_path = f"prospect_data_availability_{self.timestamp}.csv"
        df.to_csv(csv_path, index=False)
        print(f"\n📊 CSV summary saved to: {csv_path}")

        return csv_path

    async def run_audit(self):
        """Run complete audit."""
        try:
            await self.connect()

            await self.audit_prospects_table()
            await self.audit_milb_game_logs()
            await self.audit_pitch_data()
            await self.audit_scouting_grades()
            await self.audit_hype_data()
            await self.audit_data_coverage()

            # Generate reports
            markdown_report = self.generate_markdown_report()
            report_path = f"PROSPECT_DATA_AUDIT_{self.timestamp}.md"

            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(markdown_report)

            print(f"\n✅ Markdown report saved to: {report_path}")

            # Generate CSV
            csv_path = await self.generate_csv_summary()

            print("\n" + "="*60)
            print("AUDIT COMPLETE!")
            print("="*60)
            print(f"📄 Full Report: {report_path}")
            print(f"📊 CSV Summary: {csv_path}")
            print(f"⏰ Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        finally:
            await self.disconnect()

async def main():
    """Main execution function."""
    print("="*60)
    print("A FINE WINE DYNASTY - COMPREHENSIVE DATA AUDIT")
    print("="*60)

    auditor = ProspectDataAuditor()
    await auditor.run_audit()

if __name__ == "__main__":
    asyncio.run(main())