#!/usr/bin/env python3
"""
Scheduled audit process for pitch data completeness.
Can be run via cron job or Windows Task Scheduler.
Generates reports and triggers collection if needed.
"""

import psycopg2
from datetime import datetime, timedelta
import json
import csv
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import argparse
import logging

# Configuration
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
REPORT_DIR = './audit_reports'
LOG_FILE = 'pitch_audit.log'

# Thresholds for alerts
COVERAGE_THRESHOLD = 95  # Alert if coverage drops below 95%
MISSING_GAMES_THRESHOLD = 100  # Alert if more than 100 games missing

# Set up logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ScheduledPitchAuditor:
    def __init__(self, output_dir=REPORT_DIR):
        self.output_dir = output_dir
        self.timestamp = datetime.now()
        self.conn = psycopg2.connect(DB_URL)
        self.alerts = []

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

    def run_audit(self):
        """Run the complete audit process"""
        logging.info("Starting scheduled pitch data audit")

        try:
            # Collect audit data
            overall_stats = self.get_overall_statistics()
            critical_gaps = self.identify_critical_gaps()
            recent_activity = self.check_recent_activity()

            # Check for issues
            self.check_thresholds(overall_stats, critical_gaps)

            # Generate reports
            report_path = self.generate_report(overall_stats, critical_gaps, recent_activity)

            # Trigger collection if needed
            if self.alerts:
                self.trigger_collection(critical_gaps)

            # Send notifications if configured
            if self.alerts:
                self.send_alert_notification()

            logging.info(f"Audit completed. Report saved to {report_path}")
            return True

        except Exception as e:
            logging.error(f"Audit failed: {str(e)}")
            return False
        finally:
            self.conn.close()

    def get_overall_statistics(self):
        """Get overall coverage statistics"""
        cur = self.conn.cursor()

        cur.execute("""
            WITH stats AS (
                SELECT
                    COUNT(DISTINCT p.id) as total_prospects,
                    COUNT(DISTINCT CASE WHEN gl.season = 2025 THEN gl.mlb_player_id END) as active_players,
                    COUNT(DISTINCT gl.game_pk) as total_games,
                    COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                    COUNT(bp.*) as total_pitches,
                    SUM(gl.plate_appearances) as total_pas
                FROM prospects p
                LEFT JOIN milb_game_logs gl ON p.mlb_player_id::text = gl.mlb_player_id::text
                    AND gl.season = 2025
                LEFT JOIN milb_batter_pitches bp ON gl.game_pk = bp.game_pk
                    AND p.mlb_player_id::integer = bp.mlb_batter_id
                WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH')
            )
            SELECT
                total_prospects,
                active_players,
                total_games,
                games_with_pitches,
                total_games - games_with_pitches as missing_games,
                ROUND((games_with_pitches::numeric / NULLIF(total_games, 0)) * 100, 2) as coverage_pct,
                total_pitches,
                total_pas
            FROM stats
        """)

        result = cur.fetchone()

        return {
            'total_prospects': result[0],
            'active_players': result[1],
            'total_games': result[2],
            'games_with_pitches': result[3],
            'missing_games': result[4],
            'coverage_pct': float(result[5]) if result[5] else 0,
            'total_pitches': result[6],
            'total_pas': result[7]
        }

    def identify_critical_gaps(self, limit=50):
        """Identify players with critical data gaps"""
        cur = self.conn.cursor()

        cur.execute("""
            SELECT
                p.name,
                p.mlb_player_id,
                p.position,
                p.organization,
                COUNT(DISTINCT gl.game_pk) as total_games,
                COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                COUNT(DISTINCT gl.game_pk) - COUNT(DISTINCT bp.game_pk) as missing_games,
                array_agg(DISTINCT gl.game_pk) FILTER (WHERE bp.game_pk IS NULL) as missing_game_pks
            FROM prospects p
            JOIN milb_game_logs gl ON p.mlb_player_id::text = gl.mlb_player_id::text
                AND gl.season = 2025
            LEFT JOIN milb_batter_pitches bp ON gl.game_pk = bp.game_pk
                AND p.mlb_player_id::integer = bp.mlb_batter_id
            WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF')
            GROUP BY p.name, p.mlb_player_id, p.position, p.organization
            HAVING COUNT(DISTINCT gl.game_pk) > COUNT(DISTINCT bp.game_pk)
            ORDER BY COUNT(DISTINCT gl.game_pk) - COUNT(DISTINCT bp.game_pk) DESC
            LIMIT %s
        """, (limit,))

        gaps = []
        for row in cur.fetchall():
            gaps.append({
                'name': row[0],
                'mlb_player_id': row[1],
                'position': row[2],
                'organization': row[3],
                'total_games': row[4],
                'games_with_pitches': row[5],
                'missing_games': row[6],
                'missing_game_pks': row[7] if row[7] else []
            })

        return gaps

    def check_recent_activity(self, hours=24):
        """Check collection activity in the last N hours"""
        cur = self.conn.cursor()

        cur.execute("""
            SELECT
                COUNT(*) as new_pitches,
                COUNT(DISTINCT mlb_batter_id) as players_updated,
                COUNT(DISTINCT game_pk) as games_updated,
                MIN(created_at) as earliest,
                MAX(created_at) as latest
            FROM milb_batter_pitches
            WHERE created_at > NOW() - INTERVAL %s
        """, (f'{hours} hours',))

        result = cur.fetchone()

        return {
            'hours_checked': hours,
            'new_pitches': result[0],
            'players_updated': result[1],
            'games_updated': result[2],
            'earliest_update': result[3],
            'latest_update': result[4]
        }

    def check_thresholds(self, overall_stats, critical_gaps):
        """Check if any thresholds are breached"""
        # Check coverage threshold
        if overall_stats['coverage_pct'] < COVERAGE_THRESHOLD:
            self.alerts.append({
                'type': 'LOW_COVERAGE',
                'message': f"Coverage dropped to {overall_stats['coverage_pct']:.2f}% (threshold: {COVERAGE_THRESHOLD}%)",
                'severity': 'HIGH'
            })

        # Check missing games threshold
        if overall_stats['missing_games'] > MISSING_GAMES_THRESHOLD:
            self.alerts.append({
                'type': 'MISSING_GAMES',
                'message': f"{overall_stats['missing_games']} games missing pitch data (threshold: {MISSING_GAMES_THRESHOLD})",
                'severity': 'MEDIUM'
            })

        # Check for players with no data
        no_data_count = sum(1 for gap in critical_gaps if gap['games_with_pitches'] == 0)
        if no_data_count > 5:
            self.alerts.append({
                'type': 'NO_DATA_PLAYERS',
                'message': f"{no_data_count} players have games but no pitch data at all",
                'severity': 'HIGH'
            })

    def generate_report(self, overall_stats, critical_gaps, recent_activity):
        """Generate audit report files"""
        timestamp_str = self.timestamp.strftime("%Y%m%d_%H%M%S")

        # Generate JSON report
        report_data = {
            'audit_timestamp': self.timestamp.isoformat(),
            'overall_statistics': overall_stats,
            'critical_gaps': critical_gaps[:20],  # Top 20
            'recent_activity': recent_activity,
            'alerts': self.alerts
        }

        json_path = os.path.join(self.output_dir, f'audit_{timestamp_str}.json')
        with open(json_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)

        # Generate CSV of gaps
        csv_path = os.path.join(self.output_dir, f'gaps_{timestamp_str}.csv')
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'MLB_ID', 'Position', 'Team', 'Total_Games',
                           'Games_With_Pitches', 'Missing_Games'])

            for gap in critical_gaps:
                writer.writerow([
                    gap['name'], gap['mlb_player_id'], gap['position'],
                    gap['organization'], gap['total_games'],
                    gap['games_with_pitches'], gap['missing_games']
                ])

        # Generate summary text report
        summary_path = os.path.join(self.output_dir, f'summary_{timestamp_str}.txt')
        with open(summary_path, 'w') as f:
            f.write("PITCH DATA AUDIT SUMMARY\n")
            f.write(f"Generated: {self.timestamp}\n")
            f.write("=" * 60 + "\n\n")

            f.write("OVERALL STATISTICS:\n")
            f.write(f"  Coverage: {overall_stats['coverage_pct']:.2f}%\n")
            f.write(f"  Total Games: {overall_stats['total_games']:,}\n")
            f.write(f"  Games with Pitch Data: {overall_stats['games_with_pitches']:,}\n")
            f.write(f"  Missing Games: {overall_stats['missing_games']:,}\n")
            f.write(f"  Total Pitches: {overall_stats['total_pitches']:,}\n\n")

            f.write("RECENT ACTIVITY (24h):\n")
            f.write(f"  New Pitches: {recent_activity['new_pitches']:,}\n")
            f.write(f"  Players Updated: {recent_activity['players_updated']}\n")
            f.write(f"  Games Updated: {recent_activity['games_updated']}\n\n")

            if self.alerts:
                f.write("ALERTS:\n")
                for alert in self.alerts:
                    f.write(f"  [{alert['severity']}] {alert['message']}\n")
            else:
                f.write("No alerts - system healthy\n")

        logging.info(f"Reports generated: {json_path}, {csv_path}, {summary_path}")
        return json_path

    def trigger_collection(self, critical_gaps):
        """Trigger collection for critical gaps"""
        # Create a collection list for the most critical gaps
        collection_list = []

        for gap in critical_gaps[:20]:  # Top 20 most critical
            if gap['missing_games'] > 10:  # Only if significant gaps
                collection_list.append({
                    'name': gap['name'],
                    'mlb_player_id': gap['mlb_player_id'],
                    'missing_games': gap['missing_games'],
                    'game_pks': gap['missing_game_pks'][:50]  # Limit to 50 games
                })

        if collection_list:
            # Save collection list
            collection_path = os.path.join(
                self.output_dir,
                f'collection_needed_{self.timestamp.strftime("%Y%m%d_%H%M%S")}.json'
            )

            with open(collection_path, 'w') as f:
                json.dump(collection_list, f, indent=2)

            logging.info(f"Collection list created: {collection_path}")

            # Here you could trigger the actual collection script
            # os.system(f"python collect_missing_pitches_final.py --input {collection_path}")

    def send_alert_notification(self):
        """Send alert notifications (placeholder for email/Slack/etc.)"""
        if not self.alerts:
            return

        # Log alerts
        for alert in self.alerts:
            logging.warning(f"ALERT [{alert['severity']}]: {alert['message']}")

        # Here you could implement email, Slack, or other notifications
        # Example structure:
        """
        if EMAIL_CONFIGURED:
            msg = MIMEMultipart()
            msg['Subject'] = f'Pitch Data Audit Alert - {len(self.alerts)} issues found'
            msg['From'] = 'audit@system.com'
            msg['To'] = 'admin@example.com'

            body = f"Audit performed at {self.timestamp}\n\n"
            for alert in self.alerts:
                body += f"[{alert['severity']}] {alert['message']}\n"

            msg.attach(MIMEText(body, 'plain'))

            # Send email via SMTP
        """


def main():
    parser = argparse.ArgumentParser(description='Scheduled pitch data audit')
    parser.add_argument('--output', default=REPORT_DIR, help='Output directory for reports')
    parser.add_argument('--trigger-collection', action='store_true',
                       help='Trigger collection for gaps if found')

    args = parser.parse_args()

    auditor = ScheduledPitchAuditor(output_dir=args.output)
    success = auditor.run_audit()

    if success:
        print(f"Audit completed successfully. Reports saved to {args.output}")
        return 0
    else:
        print("Audit failed. Check logs for details.")
        return 1


if __name__ == "__main__":
    exit(main())