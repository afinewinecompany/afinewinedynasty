"""Automated compliance monitoring and validation scheduler."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
from pathlib import Path

from app.services.compliance_attribution import ComplianceAuditor, DataRetentionPolicy
from app.services.pipeline_monitoring import PipelineMonitor
from app.core.config import settings

logger = logging.getLogger(__name__)


class ComplianceScheduler:
    """Automated compliance monitoring and validation scheduler."""

    def __init__(self):
        self.auditor = ComplianceAuditor()
        self.monitor = PipelineMonitor()
        self.is_running = False
        self.last_run_times = {}
        self.compliance_history = []

        # Compliance check intervals (in minutes)
        self.check_intervals = {
            'rate_limiting': 15,      # Check rate limiting every 15 minutes
            'attribution': 60,        # Check attribution hourly
            'data_retention': 1440,   # Check data retention daily (24 hours)
            'tos_compliance': 720,    # Check ToS compliance twice daily
            'cost_monitoring': 60,    # Check costs hourly
            'full_audit': 10080       # Full audit weekly (7 days)
        }

    async def start_monitoring(self):
        """Start the automated compliance monitoring."""
        if self.is_running:
            logger.warning("Compliance monitoring is already running")
            return

        self.is_running = True
        logger.info("Starting automated compliance monitoring")

        try:
            while self.is_running:
                await self._run_scheduled_checks()
                await asyncio.sleep(60)  # Check every minute for due tasks

        except Exception as e:
            logger.error(f"Error in compliance monitoring loop: {str(e)}")
            await self.monitor.send_alert('error', f"Compliance monitoring failed: {str(e)}")
        finally:
            self.is_running = False

    async def stop_monitoring(self):
        """Stop the automated compliance monitoring."""
        self.is_running = False
        logger.info("Stopping automated compliance monitoring")

    async def _run_scheduled_checks(self):
        """Run checks that are due based on their intervals."""
        current_time = datetime.utcnow()

        for check_name, interval_minutes in self.check_intervals.items():
            last_run = self.last_run_times.get(check_name)

            if not last_run or (current_time - last_run).total_seconds() >= interval_minutes * 60:
                logger.info(f"Running scheduled compliance check: {check_name}")

                try:
                    await self._execute_compliance_check(check_name)
                    self.last_run_times[check_name] = current_time

                except Exception as e:
                    logger.error(f"Error in compliance check {check_name}: {str(e)}")
                    await self.monitor.send_alert(
                        'error',
                        f"Compliance check {check_name} failed: {str(e)}"
                    )

    async def _execute_compliance_check(self, check_name: str):
        """Execute a specific compliance check."""
        if check_name == 'rate_limiting':
            await self._check_rate_limiting_compliance()
        elif check_name == 'attribution':
            await self._check_attribution_compliance()
        elif check_name == 'data_retention':
            await self._check_data_retention_compliance()
        elif check_name == 'tos_compliance':
            await self._check_tos_compliance()
        elif check_name == 'cost_monitoring':
            await self._check_cost_compliance()
        elif check_name == 'full_audit':
            await self._run_full_audit()
        else:
            logger.warning(f"Unknown compliance check: {check_name}")

    async def _check_rate_limiting_compliance(self):
        """Check rate limiting compliance for all services."""
        logger.info("Checking rate limiting compliance")

        # Check FanGraphs service rate limiting
        fangraphs_compliance = await self.auditor.verify_compliance('fangraphs')

        if not fangraphs_compliance['compliant']:
            await self.monitor.send_alert(
                'warning',
                f"Rate limiting compliance issue: {', '.join(fangraphs_compliance['issues'])}"
            )

        # Log successful compliance check
        if fangraphs_compliance['compliant']:
            logger.info("Rate limiting compliance check passed")

    async def _check_attribution_compliance(self):
        """Check attribution compliance across the platform."""
        logger.info("Checking attribution compliance")

        from app.services.compliance_attribution import DataSourceAttribution

        # Verify all required attributions are properly configured
        sources = ['fangraphs', 'mlb_api']
        attributions = DataSourceAttribution.get_all_required_attributions(sources)

        compliance_issues = []

        for attr in attributions:
            source = attr['source']

            # Check if display requirements are met
            display_req = attr.get('display_requirements', {})

            if not display_req.get('position'):
                compliance_issues.append(f"Missing display position for {source}")

            if not display_req.get('visibility'):
                compliance_issues.append(f"Missing visibility requirement for {source}")

            # Verify HTML generation works
            html = DataSourceAttribution.get_display_html(source)
            if attr['required'] and not html:
                compliance_issues.append(f"Failed to generate attribution HTML for {source}")

        if compliance_issues:
            await self.monitor.send_alert(
                'warning',
                f"Attribution compliance issues: {', '.join(compliance_issues)}"
            )
        else:
            logger.info("Attribution compliance check passed")

    async def _check_data_retention_compliance(self):
        """Check data retention policy compliance."""
        logger.info("Checking data retention compliance")

        try:
            # Run cleanup for expired data
            cleanup_stats = await DataRetentionPolicy.cleanup_expired_data()

            # Log cleanup results
            total_cleaned = sum(cleanup_stats.values())
            if total_cleaned > 0:
                logger.info(f"Data retention cleanup: {total_cleaned} records cleaned")
                await self.monitor.send_alert(
                    'info',
                    f"Data retention cleanup completed: {total_cleaned} records cleaned"
                )

            logger.info("Data retention compliance check completed")

        except Exception as e:
            logger.error(f"Data retention compliance check failed: {str(e)}")
            await self.monitor.send_alert(
                'error',
                f"Data retention compliance check failed: {str(e)}"
            )

    async def _check_tos_compliance(self):
        """Check Terms of Service compliance."""
        logger.info("Checking Terms of Service compliance")

        from app.services.compliance_attribution import TermsOfServiceManager

        compliance_issues = []

        # Check ToS acceptance for all sources
        sources = ['fangraphs', 'mlb_api']
        for source in sources:
            if not TermsOfServiceManager.verify_tos_acceptance(source):
                compliance_issues.append(f"ToS not accepted for {source}")

            # Check if ToS requirements are current
            tos_req = TermsOfServiceManager.get_tos_requirements(source)
            if not tos_req:
                compliance_issues.append(f"Missing ToS requirements for {source}")

        if compliance_issues:
            await self.monitor.send_alert(
                'critical',
                f"ToS compliance issues: {', '.join(compliance_issues)}"
            )
        else:
            logger.info("Terms of Service compliance check passed")

    async def _check_cost_compliance(self):
        """Check cost monitoring compliance."""
        logger.info("Checking cost compliance")

        from app.services.compliance_attribution import CostTracker

        cost_tracker = CostTracker()
        cost_report = await cost_tracker.get_cost_report()

        # Check for cost anomalies
        total_cost = cost_report.get('total_cost', 0)
        cost_alerts = []

        for source, source_data in cost_report.get('sources', {}).items():
            requests = source_data.get('requests', 0)
            cost = source_data.get('cost', 0)
            limit = source_data.get('limit')

            # Alert on high usage (if limits exist)
            if limit and requests > limit * 0.8:  # 80% of limit
                cost_alerts.append(f"{source} approaching usage limit: {requests}/{limit}")

            # Alert on unexpected costs for free services
            if cost > 0 and source in ['fangraphs', 'mlb_api']:
                cost_alerts.append(f"Unexpected cost for {source}: ${cost}")

        if cost_alerts:
            await self.monitor.send_alert(
                'warning',
                f"Cost compliance alerts: {', '.join(cost_alerts)}"
            )

        logger.info(f"Cost compliance check completed. Total cost: ${total_cost}")

    async def _run_full_audit(self):
        """Run comprehensive compliance audit."""
        logger.info("Running full compliance audit")

        try:
            # Generate comprehensive compliance report
            audit_report = await self.auditor.generate_compliance_report()

            # Store audit report
            await self._store_audit_report(audit_report)

            # Check for critical issues
            critical_issues = []

            for source, status in audit_report.get('sources', {}).items():
                if not status.get('compliant', True):
                    critical_issues.extend([
                        f"{source}: {issue}" for issue in status.get('issues', [])
                    ])

            # Send alerts for critical issues
            if critical_issues:
                await self.monitor.send_alert(
                    'critical',
                    f"Full audit found critical compliance issues: {', '.join(critical_issues)}"
                )
            else:
                await self.monitor.send_alert(
                    'info',
                    "Full compliance audit completed successfully - no critical issues found"
                )

            # Store in compliance history
            self.compliance_history.append({
                'timestamp': datetime.utcnow().isoformat(),
                'type': 'full_audit',
                'status': 'completed',
                'critical_issues_count': len(critical_issues),
                'report_id': audit_report.get('generated_at')
            })

            logger.info(f"Full compliance audit completed. Found {len(critical_issues)} critical issues")

        except Exception as e:
            logger.error(f"Full compliance audit failed: {str(e)}")
            await self.monitor.send_alert(
                'error',
                f"Full compliance audit failed: {str(e)}"
            )

    async def _store_audit_report(self, report: Dict[str, Any]):
        """Store audit report to file system."""
        try:
            # Create compliance reports directory
            reports_dir = Path("compliance_reports")
            reports_dir.mkdir(exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"compliance_audit_{timestamp}.json"
            filepath = reports_dir / filename

            # Save report
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            logger.info(f"Audit report saved to {filepath}")

        except Exception as e:
            logger.error(f"Failed to store audit report: {str(e)}")

    async def run_manual_check(self, check_name: str) -> Dict[str, Any]:
        """Run a manual compliance check."""
        logger.info(f"Running manual compliance check: {check_name}")

        start_time = datetime.utcnow()

        try:
            await self._execute_compliance_check(check_name)

            result = {
                'check_name': check_name,
                'status': 'completed',
                'start_time': start_time.isoformat(),
                'end_time': datetime.utcnow().isoformat(),
                'duration_seconds': (datetime.utcnow() - start_time).total_seconds()
            }

            logger.info(f"Manual compliance check {check_name} completed successfully")
            return result

        except Exception as e:
            logger.error(f"Manual compliance check {check_name} failed: {str(e)}")

            result = {
                'check_name': check_name,
                'status': 'failed',
                'start_time': start_time.isoformat(),
                'end_time': datetime.utcnow().isoformat(),
                'duration_seconds': (datetime.utcnow() - start_time).total_seconds(),
                'error': str(e)
            }

            return result

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status."""
        return {
            'is_running': self.is_running,
            'last_run_times': {
                name: time.isoformat() if time else None
                for name, time in self.last_run_times.items()
            },
            'check_intervals': self.check_intervals,
            'compliance_history_count': len(self.compliance_history),
            'recent_history': self.compliance_history[-5:] if self.compliance_history else []
        }

    async def update_check_interval(self, check_name: str, interval_minutes: int):
        """Update the interval for a specific compliance check."""
        if check_name in self.check_intervals:
            self.check_intervals[check_name] = interval_minutes
            logger.info(f"Updated interval for {check_name} to {interval_minutes} minutes")
        else:
            logger.error(f"Unknown compliance check: {check_name}")
            raise ValueError(f"Unknown compliance check: {check_name}")


# Global compliance scheduler instance
compliance_scheduler = ComplianceScheduler()


async def start_compliance_monitoring():
    """Start the global compliance monitoring."""
    await compliance_scheduler.start_monitoring()


async def stop_compliance_monitoring():
    """Stop the global compliance monitoring."""
    await compliance_scheduler.stop_monitoring()


def get_compliance_status() -> Dict[str, Any]:
    """Get current compliance monitoring status."""
    return compliance_scheduler.get_monitoring_status()