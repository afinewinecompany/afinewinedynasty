#!/usr/bin/env python3
"""
Comprehensive Audit System for Pitch Data Completeness
Identifies missing pitch data, generates reports, and tracks collection progress.
"""

import psycopg2
from psycopg2 import pool
import pandas as pd
from datetime import datetime, timedelta
import json
import csv
from typing import Dict, List, Tuple
import logging
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

# Create connection pool
connection_pool = psycopg2.pool.ThreadedConnectionPool(
    1, 5,
    DB_URL,
    connect_timeout=30
)

class PitchDataAuditor:
    def __init__(self):
        self.audit_timestamp = datetime.now()
        self.audit_results = {
            'timestamp': self.audit_timestamp.isoformat(),
            'summary': {},
            'details': {},
            'recommendations': []
        }

    def get_connection(self):
        """Get database connection from pool"""
        return connection_pool.getconn()

    def return_connection(self, conn):
        """Return connection to pool"""
        connection_pool.putconn(conn)

    def audit_overall_completeness(self) -> Dict:
        """Audit overall pitch data completeness across all prospects"""
        conn = self.get_connection()
        try:
            cur = conn.cursor()

            # Overall statistics
            query = """
                WITH coverage_stats AS (
                    SELECT
                        p.id,
                        p.name,
                        p.mlb_player_id,
                        p.position,
                        p.organization,
                        -- 2025 Season
                        COUNT(DISTINCT CASE WHEN gl.season = 2025 THEN gl.game_pk END) as games_2025,
                        COUNT(DISTINCT CASE WHEN bp.season = 2025 THEN bp.game_pk END) as games_with_pitches_2025,
                        COUNT(CASE WHEN bp.season = 2025 THEN 1 END) as pitches_2025,
                        SUM(CASE WHEN gl.season = 2025 THEN gl.plate_appearances ELSE 0 END) as pas_2025,
                        -- 2024 Season
                        COUNT(DISTINCT CASE WHEN gl.season = 2024 THEN gl.game_pk END) as games_2024,
                        COUNT(DISTINCT CASE WHEN bp.season = 2024 THEN bp.game_pk END) as games_with_pitches_2024,
                        COUNT(CASE WHEN bp.season = 2024 THEN 1 END) as pitches_2024,
                        SUM(CASE WHEN gl.season = 2024 THEN gl.plate_appearances ELSE 0 END) as pas_2024
                    FROM prospects p
                    LEFT JOIN milb_game_logs gl
                        ON p.mlb_player_id::text = gl.mlb_player_id::text
                        AND gl.season IN (2024, 2025)
                    LEFT JOIN milb_batter_pitches bp
                        ON p.mlb_player_id::integer = bp.mlb_batter_id
                        AND bp.season IN (2024, 2025)
                    WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH', 'IF', 'UT')
                        AND p.mlb_player_id IS NOT NULL
                    GROUP BY p.id, p.name, p.mlb_player_id, p.position, p.organization
                )
                SELECT
                    COUNT(*) as total_prospects,
                    -- 2025 Stats
                    COUNT(CASE WHEN games_2025 > 0 THEN 1 END) as prospects_with_2025_games,
                    COUNT(CASE WHEN games_2025 > 0 AND games_with_pitches_2025 = 0 THEN 1 END) as prospects_no_2025_pitch_data,
                    COUNT(CASE WHEN games_2025 > games_with_pitches_2025 THEN 1 END) as prospects_partial_2025,
                    COUNT(CASE WHEN games_2025 > 0 AND games_2025 = games_with_pitches_2025 THEN 1 END) as prospects_complete_2025,
                    SUM(games_2025) as total_games_2025,
                    SUM(games_with_pitches_2025) as total_games_with_pitches_2025,
                    SUM(games_2025 - games_with_pitches_2025) as total_missing_games_2025,
                    SUM(pitches_2025) as total_pitches_2025,
                    -- 2024 Stats
                    COUNT(CASE WHEN games_2024 > 0 THEN 1 END) as prospects_with_2024_games,
                    COUNT(CASE WHEN games_2024 > 0 AND games_with_pitches_2024 = 0 THEN 1 END) as prospects_no_2024_pitch_data,
                    COUNT(CASE WHEN games_2024 > games_with_pitches_2024 THEN 1 END) as prospects_partial_2024,
                    SUM(games_2024 - games_with_pitches_2024) as total_missing_games_2024
                FROM coverage_stats
            """

            cur.execute(query)
            result = cur.fetchone()

            overall_stats = {
                'total_prospects': result[0],
                '2025': {
                    'prospects_with_games': result[1],
                    'prospects_no_pitch_data': result[2],
                    'prospects_partial_coverage': result[3],
                    'prospects_complete_coverage': result[4],
                    'total_games': result[5],
                    'games_with_pitches': result[6],
                    'missing_games': result[7],
                    'total_pitches': result[8],
                    'coverage_percentage': (result[6] / result[5] * 100) if result[5] > 0 else 0
                },
                '2024': {
                    'prospects_with_games': result[9],
                    'prospects_no_pitch_data': result[10],
                    'prospects_partial_coverage': result[11],
                    'missing_games': result[12]
                }
            }

            return overall_stats

        finally:
            self.return_connection(conn)

    def identify_critical_gaps(self) -> List[Dict]:
        """Identify players with critical data gaps (high-priority prospects with missing data)"""
        conn = self.get_connection()
        try:
            cur = conn.cursor()

            query = """
                WITH player_gaps AS (
                    SELECT
                        p.name,
                        p.mlb_player_id,
                        p.position,
                        p.organization,
                        COALESCE(fg.fv_value, 0) as fv_value,
                        -- 2025 Coverage
                        COUNT(DISTINCT CASE WHEN gl.season = 2025 THEN gl.game_pk END) as games_2025,
                        COUNT(DISTINCT CASE WHEN bp.season = 2025 THEN bp.game_pk END) as games_with_pitches_2025,
                        -- Missing games list
                        array_agg(DISTINCT gl.game_pk ORDER BY gl.game_date)
                            FILTER (WHERE gl.season = 2025 AND bp.game_pk IS NULL) as missing_game_pks,
                        -- Date ranges
                        MIN(CASE WHEN gl.season = 2025 THEN gl.game_date END) as first_game_2025,
                        MAX(CASE WHEN gl.season = 2025 THEN gl.game_date END) as last_game_2025,
                        MIN(CASE WHEN bp.season = 2025 THEN bp.game_date END) as first_pitch_2025,
                        MAX(CASE WHEN bp.season = 2025 THEN bp.game_date END) as last_pitch_2025
                    FROM prospects p
                    LEFT JOIN fangraphs_prospects fg ON p.fg_player_id = fg.player_id
                    LEFT JOIN milb_game_logs gl
                        ON p.mlb_player_id::text = gl.mlb_player_id::text
                    LEFT JOIN milb_batter_pitches bp
                        ON gl.game_pk = bp.game_pk
                        AND p.mlb_player_id::integer = bp.mlb_batter_id
                    WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH', 'IF', 'UT')
                        AND p.mlb_player_id IS NOT NULL
                    GROUP BY p.name, p.mlb_player_id, p.position, p.organization, fg.fv_value
                )
                SELECT
                    name,
                    mlb_player_id,
                    position,
                    organization,
                    fv_value,
                    games_2025,
                    games_with_pitches_2025,
                    games_2025 - games_with_pitches_2025 as missing_games,
                    CASE
                        WHEN games_2025 > 0
                        THEN ROUND((games_with_pitches_2025::numeric / games_2025) * 100, 1)
                        ELSE 100
                    END as coverage_pct,
                    missing_game_pks,
                    first_game_2025,
                    last_game_2025,
                    first_pitch_2025,
                    last_pitch_2025,
                    CASE
                        WHEN fv_value >= 50 AND games_2025 - games_with_pitches_2025 > 20 THEN 'CRITICAL'
                        WHEN games_2025 - games_with_pitches_2025 > 50 THEN 'HIGH'
                        WHEN games_2025 - games_with_pitches_2025 > 20 THEN 'MEDIUM'
                        WHEN games_2025 - games_with_pitches_2025 > 0 THEN 'LOW'
                        ELSE 'COMPLETE'
                    END as priority
                FROM player_gaps
                WHERE games_2025 > 0
                ORDER BY
                    CASE
                        WHEN fv_value >= 50 AND games_2025 - games_with_pitches_2025 > 20 THEN 0
                        WHEN games_2025 - games_with_pitches_2025 > 50 THEN 1
                        WHEN games_2025 - games_with_pitches_2025 > 20 THEN 2
                        WHEN games_2025 - games_with_pitches_2025 > 0 THEN 3
                        ELSE 4
                    END,
                    games_2025 - games_with_pitches_2025 DESC
                LIMIT 100
            """

            cur.execute(query)
            results = cur.fetchall()

            critical_gaps = []
            for row in results:
                critical_gaps.append({
                    'name': row[0],
                    'mlb_player_id': row[1],
                    'position': row[2],
                    'organization': row[3],
                    'fv_value': row[4],
                    'games_2025': row[5],
                    'games_with_pitches': row[6],
                    'missing_games': row[7],
                    'coverage_pct': float(row[8]) if row[8] else 0,
                    'missing_game_pks': row[9] if row[9] else [],
                    'game_date_range': f"{row[10]} to {row[11]}" if row[10] else None,
                    'pitch_date_range': f"{row[12]} to {row[13]}" if row[12] else None,
                    'priority': row[14]
                })

            return critical_gaps

        finally:
            self.return_connection(conn)

    def analyze_collection_patterns(self) -> Dict:
        """Analyze patterns in data collection to identify systematic issues"""
        conn = self.get_connection()
        try:
            cur = conn.cursor()

            # Check for date patterns in missing data
            query = """
                WITH missing_patterns AS (
                    SELECT
                        DATE_TRUNC('month', gl.game_date) as month,
                        COUNT(DISTINCT gl.game_pk) as total_games,
                        COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                        COUNT(DISTINCT gl.game_pk) - COUNT(DISTINCT bp.game_pk) as missing_games,
                        COUNT(DISTINCT gl.mlb_player_id) as affected_players
                    FROM milb_game_logs gl
                    LEFT JOIN milb_batter_pitches bp
                        ON gl.game_pk = bp.game_pk
                        AND gl.mlb_player_id::integer = bp.mlb_batter_id
                    WHERE gl.season = 2025
                        AND gl.plate_appearances > 0
                    GROUP BY DATE_TRUNC('month', gl.game_date)
                    ORDER BY month
                )
                SELECT
                    TO_CHAR(month, 'YYYY-MM') as month_str,
                    total_games,
                    games_with_pitches,
                    missing_games,
                    affected_players,
                    ROUND((games_with_pitches::numeric / total_games) * 100, 1) as coverage_pct
                FROM missing_patterns
            """

            cur.execute(query)
            monthly_patterns = cur.fetchall()

            # Check for level-specific issues
            query = """
                SELECT
                    gl.level,
                    COUNT(DISTINCT gl.game_pk) as total_games,
                    COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                    COUNT(DISTINCT gl.game_pk) - COUNT(DISTINCT bp.game_pk) as missing_games,
                    ROUND((COUNT(DISTINCT bp.game_pk)::numeric / COUNT(DISTINCT gl.game_pk)) * 100, 1) as coverage_pct
                FROM milb_game_logs gl
                LEFT JOIN milb_batter_pitches bp
                    ON gl.game_pk = bp.game_pk
                    AND gl.mlb_player_id::integer = bp.mlb_batter_id
                WHERE gl.season = 2025
                    AND gl.plate_appearances > 0
                GROUP BY gl.level
                ORDER BY missing_games DESC
            """

            cur.execute(query)
            level_patterns = cur.fetchall()

            patterns = {
                'monthly': [
                    {
                        'month': row[0],
                        'total_games': row[1],
                        'games_with_pitches': row[2],
                        'missing_games': row[3],
                        'affected_players': row[4],
                        'coverage_pct': float(row[5]) if row[5] else 0
                    }
                    for row in monthly_patterns
                ],
                'by_level': [
                    {
                        'level': row[0],
                        'total_games': row[1],
                        'games_with_pitches': row[2],
                        'missing_games': row[3],
                        'coverage_pct': float(row[4]) if row[4] else 0
                    }
                    for row in level_patterns
                ]
            }

            return patterns

        finally:
            self.return_connection(conn)

    def check_recent_updates(self, hours: int = 24) -> Dict:
        """Check recent data collection activity"""
        conn = self.get_connection()
        try:
            cur = conn.cursor()

            query = """
                SELECT
                    COUNT(*) as new_pitches,
                    COUNT(DISTINCT mlb_batter_id) as players_updated,
                    COUNT(DISTINCT game_pk) as games_updated,
                    MIN(created_at) as earliest_update,
                    MAX(created_at) as latest_update
                FROM milb_batter_pitches
                WHERE created_at > NOW() - INTERVAL %s
            """

            cur.execute(query, (f'{hours} hours',))
            result = cur.fetchone()

            recent_updates = {
                'hours_checked': hours,
                'new_pitches': result[0],
                'players_updated': result[1],
                'games_updated': result[2],
                'earliest_update': result[3].isoformat() if result[3] else None,
                'latest_update': result[4].isoformat() if result[4] else None
            }

            # Get player-specific updates
            query = """
                WITH recent_players AS (
                    SELECT
                        p.name,
                        COUNT(*) as new_pitches,
                        COUNT(DISTINCT bp.game_pk) as games_added
                    FROM milb_batter_pitches bp
                    JOIN prospects p ON bp.mlb_batter_id = p.mlb_player_id::integer
                    WHERE bp.created_at > NOW() - INTERVAL %s
                    GROUP BY p.name
                    ORDER BY new_pitches DESC
                    LIMIT 10
                )
                SELECT * FROM recent_players
            """

            cur.execute(query, (f'{hours} hours',))
            top_updates = cur.fetchall()

            recent_updates['top_players_updated'] = [
                {
                    'name': row[0],
                    'new_pitches': row[1],
                    'games_added': row[2]
                }
                for row in top_updates
            ]

            return recent_updates

        finally:
            self.return_connection(conn)

    def generate_recommendations(self, overall_stats: Dict, critical_gaps: List[Dict], patterns: Dict) -> List[str]:
        """Generate actionable recommendations based on audit findings"""
        recommendations = []

        # Check overall coverage
        if overall_stats['2025']['coverage_percentage'] < 80:
            recommendations.append(
                f"CRITICAL: Overall 2025 pitch data coverage is only {overall_stats['2025']['coverage_percentage']:.1f}%. "
                f"Run comprehensive collection for {overall_stats['2025']['missing_games']} missing games."
            )

        # Check for players with no data
        if overall_stats['2025']['prospects_no_pitch_data'] > 0:
            recommendations.append(
                f"HIGH: {overall_stats['2025']['prospects_no_pitch_data']} prospects have games but NO pitch data at all. "
                "These should be collected immediately."
            )

        # Check for critical gaps
        critical_count = sum(1 for p in critical_gaps if p['priority'] == 'CRITICAL')
        if critical_count > 0:
            recommendations.append(
                f"HIGH: {critical_count} high-value prospects (FV 50+) have significant data gaps. "
                "Prioritize collection for these players."
            )

        # Check monthly patterns
        for month_data in patterns['monthly']:
            if month_data['coverage_pct'] < 50:
                recommendations.append(
                    f"MEDIUM: {month_data['month']} has only {month_data['coverage_pct']}% pitch data coverage. "
                    f"Focus collection on {month_data['missing_games']} games from this period."
                )

        # Check level-specific issues
        for level_data in patterns['by_level']:
            if level_data['coverage_pct'] < 70 and level_data['missing_games'] > 100:
                recommendations.append(
                    f"MEDIUM: {level_data['level']} level has {level_data['missing_games']} games missing pitch data. "
                    f"Current coverage: {level_data['coverage_pct']}%"
                )

        # Add general recommendations
        if overall_stats['2025']['prospects_partial_coverage'] > 20:
            recommendations.append(
                f"Schedule regular audit checks. {overall_stats['2025']['prospects_partial_coverage']} prospects have partial coverage."
            )

        return recommendations

    def save_audit_report(self, output_dir: str = '.') -> str:
        """Save comprehensive audit report"""
        timestamp = self.audit_timestamp.strftime("%Y%m%d_%H%M%S")

        # Gather all audit data
        logger.info("Running comprehensive pitch data audit...")

        overall_stats = self.audit_overall_completeness()
        critical_gaps = self.identify_critical_gaps()
        patterns = self.analyze_collection_patterns()
        recent_updates = self.check_recent_updates(24)
        recommendations = self.generate_recommendations(overall_stats, critical_gaps, patterns)

        # Create report structure
        self.audit_results = {
            'timestamp': self.audit_timestamp.isoformat(),
            'overall_statistics': overall_stats,
            'critical_gaps': critical_gaps[:20],  # Top 20 critical gaps
            'collection_patterns': patterns,
            'recent_updates': recent_updates,
            'recommendations': recommendations
        }

        # Save JSON report
        json_filename = os.path.join(output_dir, f'pitch_data_audit_{timestamp}.json')
        with open(json_filename, 'w') as f:
            json.dump(self.audit_results, f, indent=2, default=str)
        logger.info(f"JSON report saved: {json_filename}")

        # Save CSV of critical gaps
        csv_filename = os.path.join(output_dir, f'missing_pitch_data_{timestamp}.csv')
        with open(csv_filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'MLB_ID', 'Position', 'Team', 'Priority',
                           'Total_Games', 'Games_With_Pitches', 'Missing_Games',
                           'Coverage_Pct', 'FV_Value'])

            for gap in critical_gaps:
                writer.writerow([
                    gap['name'], gap['mlb_player_id'], gap['position'],
                    gap['organization'], gap['priority'],
                    gap['games_2025'], gap['games_with_pitches'],
                    gap['missing_games'], gap['coverage_pct'], gap['fv_value']
                ])
        logger.info(f"CSV report saved: {csv_filename}")

        # Generate HTML summary report
        html_filename = os.path.join(output_dir, f'pitch_audit_summary_{timestamp}.html')
        self.generate_html_report(html_filename)
        logger.info(f"HTML report saved: {html_filename}")

        return json_filename

    def generate_html_report(self, filename: str):
        """Generate an HTML summary report"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Pitch Data Audit Report - {self.audit_timestamp.strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #666; margin-top: 30px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat-card {{ background: #f9f9f9; padding: 15px; border-radius: 8px; border-left: 4px solid #4CAF50; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #333; }}
        .stat-label {{ color: #666; font-size: 12px; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #4CAF50; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f5f5f5; }}
        .priority-CRITICAL {{ background: #ffebee; color: #c62828; font-weight: bold; }}
        .priority-HIGH {{ background: #fff3e0; color: #e65100; }}
        .priority-MEDIUM {{ background: #fff8e1; color: #f57c00; }}
        .priority-LOW {{ background: #f1f8e9; color: #558b2f; }}
        .priority-COMPLETE {{ background: #e8f5e9; color: #2e7d32; }}
        .recommendation {{ background: #e3f2fd; padding: 10px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #1976d2; }}
        .coverage-bar {{ background: #e0e0e0; height: 20px; border-radius: 10px; overflow: hidden; }}
        .coverage-fill {{ background: #4CAF50; height: 100%; transition: width 0.3s; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Pitch Data Completeness Audit Report</h1>
        <p>Generated: {self.audit_timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>

        <h2>📊 Overall Statistics - 2025 Season</h2>
        <div class="summary-grid">
            <div class="stat-card">
                <div class="stat-value">{self.audit_results['overall_statistics']['2025']['coverage_percentage']:.1f}%</div>
                <div class="stat-label">Overall Coverage</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{self.audit_results['overall_statistics']['2025']['prospects_complete_coverage']}</div>
                <div class="stat-label">Prospects Complete</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{self.audit_results['overall_statistics']['2025']['prospects_partial_coverage']}</div>
                <div class="stat-label">Prospects Partial</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{self.audit_results['overall_statistics']['2025']['prospects_no_pitch_data']}</div>
                <div class="stat-label">No Pitch Data</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{self.audit_results['overall_statistics']['2025']['missing_games']:,}</div>
                <div class="stat-label">Games Missing Data</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{self.audit_results['overall_statistics']['2025']['total_pitches']:,}</div>
                <div class="stat-label">Total Pitches</div>
            </div>
        </div>

        <h2>🚨 Critical Data Gaps</h2>
        <table>
            <thead>
                <tr>
                    <th>Player</th>
                    <th>Position</th>
                    <th>Team</th>
                    <th>Priority</th>
                    <th>Coverage</th>
                    <th>Missing Games</th>
                    <th>FV Value</th>
                </tr>
            </thead>
            <tbody>
"""

        # Add critical gaps to table
        for gap in self.audit_results['critical_gaps'][:20]:
            priority_class = f"priority-{gap['priority']}"
            html_content += f"""
                <tr>
                    <td><strong>{gap['name']}</strong></td>
                    <td>{gap['position']}</td>
                    <td>{gap['organization']}</td>
                    <td class="{priority_class}">{gap['priority']}</td>
                    <td>
                        <div class="coverage-bar">
                            <div class="coverage-fill" style="width: {gap['coverage_pct']}%"></div>
                        </div>
                        {gap['coverage_pct']:.1f}%
                    </td>
                    <td>{gap['missing_games']} / {gap['games_2025']}</td>
                    <td>{gap['fv_value']}</td>
                </tr>
"""

        html_content += """
            </tbody>
        </table>

        <h2>📈 Collection Patterns by Month</h2>
        <table>
            <thead>
                <tr>
                    <th>Month</th>
                    <th>Total Games</th>
                    <th>With Pitch Data</th>
                    <th>Missing</th>
                    <th>Coverage</th>
                </tr>
            </thead>
            <tbody>
"""

        # Add monthly patterns
        for month in self.audit_results['collection_patterns']['monthly']:
            html_content += f"""
                <tr>
                    <td>{month['month']}</td>
                    <td>{month['total_games']}</td>
                    <td>{month['games_with_pitches']}</td>
                    <td>{month['missing_games']}</td>
                    <td>
                        <div class="coverage-bar">
                            <div class="coverage-fill" style="width: {month['coverage_pct']}%"></div>
                        </div>
                        {month['coverage_pct']:.1f}%
                    </td>
                </tr>
"""

        html_content += """
            </tbody>
        </table>

        <h2>💡 Recommendations</h2>
"""

        # Add recommendations
        for rec in self.audit_results['recommendations']:
            priority = "HIGH" if "CRITICAL" in rec or "HIGH" in rec else "MEDIUM"
            color = "#c62828" if "CRITICAL" in rec else "#e65100" if "HIGH" in rec else "#f57c00"
            html_content += f"""
        <div class="recommendation">
            <strong style="color: {color};">{rec}</strong>
        </div>
"""

        # Add recent updates section
        recent = self.audit_results['recent_updates']
        html_content += f"""
        <h2>🔄 Recent Collection Activity (Last 24 Hours)</h2>
        <div class="summary-grid">
            <div class="stat-card">
                <div class="stat-value">{recent['new_pitches']:,}</div>
                <div class="stat-label">New Pitches</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{recent['players_updated']}</div>
                <div class="stat-label">Players Updated</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{recent['games_updated']}</div>
                <div class="stat-label">Games Updated</div>
            </div>
        </div>

        <p style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px;">
            Report generated by PitchDataAuditor | {self.audit_timestamp.strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
</body>
</html>
"""

        with open(filename, 'w') as f:
            f.write(html_content)

    def print_summary(self):
        """Print a console summary of the audit"""
        overall = self.audit_results.get('overall_statistics', {})
        gaps = self.audit_results.get('critical_gaps', [])
        recent = self.audit_results.get('recent_updates', {})

        print("\n" + "=" * 80)
        print("PITCH DATA AUDIT SUMMARY")
        print("=" * 80)

        print(f"\n📊 2025 Season Coverage: {overall.get('2025', {}).get('coverage_percentage', 0):.1f}%")
        print(f"   Complete: {overall.get('2025', {}).get('prospects_complete_coverage', 0)} prospects")
        print(f"   Partial: {overall.get('2025', {}).get('prospects_partial_coverage', 0)} prospects")
        print(f"   No Data: {overall.get('2025', {}).get('prospects_no_pitch_data', 0)} prospects")
        print(f"   Missing: {overall.get('2025', {}).get('missing_games', 0):,} games")

        print(f"\n🚨 Top Priority Gaps:")
        for gap in gaps[:5]:
            print(f"   {gap['name']:<25} {gap['position']:<3} - {gap['missing_games']} games missing ({gap['coverage_pct']:.1f}% coverage)")

        print(f"\n🔄 Recent Activity (24h):")
        print(f"   New pitches: {recent.get('new_pitches', 0):,}")
        print(f"   Players updated: {recent.get('players_updated', 0)}")
        print(f"   Games updated: {recent.get('games_updated', 0)}")

        print(f"\n💡 Top Recommendations:")
        for rec in self.audit_results.get('recommendations', [])[:3]:
            print(f"   • {rec}")

        print("\n" + "=" * 80)


def main():
    """Run the audit and generate reports"""
    auditor = PitchDataAuditor()

    # Run audit and save reports
    report_file = auditor.save_audit_report()

    # Print summary to console
    auditor.print_summary()

    print(f"\n✅ Audit complete! Reports saved:")
    print(f"   • JSON: {report_file}")
    print(f"   • CSV: {report_file.replace('.json', '.csv')}")
    print(f"   • HTML: {report_file.replace('json', 'html')}")


if __name__ == "__main__":
    main()