"""Legal compliance and data attribution management."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json

from app.core.config import settings
from app.services.pipeline_monitoring import PipelineMonitor

logger = logging.getLogger(__name__)


class DataSourceAttribution:
    """Attribution requirements for different data sources."""

    ATTRIBUTIONS = {
        'fangraphs': {
            'required': True,
            'text': 'Data provided by Fangraphs.com',
            'url': 'https://www.fangraphs.com',
            'logo_url': 'https://www.fangraphs.com/logo.png',
            'terms_url': 'https://www.fangraphs.com/terms',
            'update_frequency': 'daily',
            'retention_days': 30,
            'display_requirements': {
                'position': 'footer',
                'font_size': 'minimum 10px',
                'visibility': 'clearly visible',
                'link_required': True
            }
        },
        'mlb_api': {
            'required': True,
            'text': '© MLB Advanced Media, L.P.',
            'url': 'https://www.mlb.com',
            'logo_url': None,
            'terms_url': 'https://www.mlb.com/official-information/terms-of-use',
            'update_frequency': 'real-time',
            'retention_days': 90,
            'display_requirements': {
                'position': 'footer',
                'font_size': 'standard',
                'visibility': 'visible',
                'link_required': False
            }
        }
    }

    @classmethod
    def get_attribution(cls, source: str) -> Dict[str, Any]:
        """Get attribution requirements for a data source."""
        return cls.ATTRIBUTIONS.get(source, {})

    @classmethod
    def get_display_html(cls, source: str) -> str:
        """Generate HTML for attribution display."""
        attr = cls.get_attribution(source)
        if not attr or not attr.get('required'):
            return ""

        if attr.get('url') and attr['display_requirements'].get('link_required'):
            return f'<div class="data-attribution"><a href="{attr["url"]}" target="_blank">{attr["text"]}</a></div>'
        else:
            return f'<div class="data-attribution">{attr["text"]}</div>'

    @classmethod
    def get_all_required_attributions(cls, sources: List[str]) -> List[Dict[str, Any]]:
        """Get all required attributions for a list of sources."""
        attributions = []
        for source in sources:
            attr = cls.get_attribution(source)
            if attr and attr.get('required'):
                attributions.append({
                    'source': source,
                    **attr
                })
        return attributions


class DataRetentionPolicy:
    """Manage data retention policies for compliance."""

    RETENTION_POLICIES = {
        'prospect_data': {
            'raw_data': 90,  # days
            'processed_data': 365,
            'predictions': 180,
            'audit_logs': 730  # 2 years
        },
        'user_data': {
            'profile': 'indefinite',
            'activity_logs': 365,
            'preferences': 'indefinite',
            'deleted_user_data': 30  # grace period
        },
        'system_data': {
            'error_logs': 90,
            'performance_metrics': 180,
            'api_logs': 30
        }
    }

    @classmethod
    async def apply_retention_policy(cls, data_type: str, category: str) -> int:
        """Get retention period in days for specific data type."""
        policy = cls.RETENTION_POLICIES.get(data_type, {})
        retention_days = policy.get(category, 90)  # Default to 90 days

        if retention_days == 'indefinite':
            return -1  # Special value for indefinite retention

        return retention_days

    @classmethod
    async def cleanup_expired_data(cls) -> Dict[str, int]:
        """Clean up data that has exceeded retention period."""
        cleanup_stats = {}

        for data_type, policies in cls.RETENTION_POLICIES.items():
            for category, retention_days in policies.items():
                if retention_days != 'indefinite':
                    count = await cls._cleanup_category(data_type, category, retention_days)
                    cleanup_stats[f"{data_type}.{category}"] = count

        logger.info(f"Data cleanup completed: {cleanup_stats}")
        return cleanup_stats

    @classmethod
    async def _cleanup_category(cls, data_type: str, category: str, retention_days: int) -> int:
        """Clean up specific data category (placeholder for actual implementation)."""
        # This would connect to database and delete old records
        logger.info(f"Cleaning {data_type}.{category} older than {retention_days} days")
        return 0  # Return count of deleted records


class ComplianceAuditor:
    """Audit and track compliance with data usage policies."""

    def __init__(self):
        self.audit_log = []
        self.monitor = PipelineMonitor()

    async def log_data_access(
        self,
        source: str,
        data_type: str,
        purpose: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log data access for audit purposes."""
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'source': source,
            'data_type': data_type,
            'purpose': purpose,
            'user_id': user_id,
            'ip_address': ip_address,
            'hash': None
        }

        # Create hash for integrity
        audit_entry['hash'] = self._create_audit_hash(audit_entry)

        self.audit_log.append(audit_entry)

        # Persist to database (placeholder)
        await self._persist_audit_log(audit_entry)

    def _create_audit_hash(self, entry: Dict) -> str:
        """Create cryptographic hash for audit entry."""
        # Remove hash field before hashing
        entry_copy = {k: v for k, v in entry.items() if k != 'hash'}
        entry_str = json.dumps(entry_copy, sort_keys=True)
        return hashlib.sha256(entry_str.encode()).hexdigest()

    async def _persist_audit_log(self, entry: Dict):
        """Persist audit log to database (placeholder)."""
        # This would save to database
        pass

    async def verify_compliance(self, source: str) -> Dict[str, Any]:
        """Verify compliance with source's terms of service."""
        compliance_status = {
            'source': source,
            'compliant': True,
            'issues': [],
            'checked_at': datetime.utcnow().isoformat()
        }

        # Check rate limiting compliance
        if source == 'fangraphs':
            rate_limit_ok = await self._check_rate_limit_compliance(source, 1, 1)  # 1 req/sec
            if not rate_limit_ok:
                compliance_status['compliant'] = False
                compliance_status['issues'].append('Rate limit exceeded')

        # Check attribution compliance
        attribution_ok = await self._check_attribution_compliance(source)
        if not attribution_ok:
            compliance_status['compliant'] = False
            compliance_status['issues'].append('Attribution not properly displayed')

        # Check data retention compliance
        retention_ok = await self._check_retention_compliance(source)
        if not retention_ok:
            compliance_status['compliant'] = False
            compliance_status['issues'].append('Data retention policy violated')

        if not compliance_status['compliant']:
            await self.monitor.send_alert(
                level='warning',
                message=f"Compliance issues for {source}: {', '.join(compliance_status['issues'])}"
            )

        return compliance_status

    async def _check_rate_limit_compliance(
        self,
        source: str,
        max_requests: int,
        period_seconds: int
    ) -> bool:
        """Check if rate limiting is within compliance."""
        # This would check actual request logs
        # Placeholder implementation
        return True

    async def _check_attribution_compliance(self, source: str) -> bool:
        """Check if attribution requirements are met."""
        # This would verify attribution is displayed correctly
        # Placeholder implementation
        return True

    async def _check_retention_compliance(self, source: str) -> bool:
        """Check if data retention policies are followed."""
        # This would verify old data is properly deleted
        # Placeholder implementation
        return True

    async def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate comprehensive compliance report."""
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'sources': {},
            'data_retention': {},
            'audit_summary': {},
            'recommendations': []
        }

        # Check compliance for each source
        for source in ['fangraphs', 'mlb_api']:
            report['sources'][source] = await self.verify_compliance(source)

        # Add retention policy status
        for data_type, policies in DataRetentionPolicy.RETENTION_POLICIES.items():
            report['data_retention'][data_type] = {
                'policies': policies,
                'status': 'compliant'  # Placeholder
            }

        # Add audit summary
        report['audit_summary'] = {
            'total_accesses': len(self.audit_log),
            'period': 'last_30_days',
            'suspicious_activity': False
        }

        # Add recommendations
        if any(not status['compliant'] for status in report['sources'].values()):
            report['recommendations'].append('Review and fix compliance issues immediately')

        return report


class TermsOfServiceManager:
    """Manage and track terms of service compliance."""

    TOS_VERSIONS = {
        'fangraphs': {
            'version': '2024-01-01',
            'accepted': True,
            'key_terms': [
                'Non-commercial use only',
                'Attribution required',
                'Rate limit 1 request/second',
                'No redistribution without permission'
            ]
        },
        'mlb_api': {
            'version': '2023-06-15',
            'accepted': True,
            'key_terms': [
                'Official API usage only',
                'No real-time game data redistribution',
                'Copyright notice required',
                'Commercial use requires license'
            ]
        }
    }

    @classmethod
    def get_tos_requirements(cls, source: str) -> Dict[str, Any]:
        """Get terms of service requirements for a source."""
        return cls.TOS_VERSIONS.get(source, {})

    @classmethod
    def verify_tos_acceptance(cls, source: str) -> bool:
        """Verify that terms of service have been accepted."""
        tos = cls.get_tos_requirements(source)
        return tos.get('accepted', False)

    @classmethod
    async def log_tos_violation(cls, source: str, violation: str):
        """Log a potential terms of service violation."""
        logger.error(f"ToS violation for {source}: {violation}")

        # This would trigger immediate action
        monitor = PipelineMonitor()
        await monitor.send_alert(
            level='critical',
            message=f"Terms of Service violation detected for {source}: {violation}"
        )


class CostTracker:
    """Track and monitor data acquisition costs."""

    def __init__(self):
        self.cost_data = {
            'fangraphs': {
                'cost_per_request': 0.0,  # Free with rate limits
                'monthly_limit': None,
                'current_usage': 0
            },
            'mlb_api': {
                'cost_per_request': 0.0,  # Free public API
                'monthly_limit': None,
                'current_usage': 0
            }
        }

    async def track_request(self, source: str):
        """Track a request for cost monitoring."""
        if source in self.cost_data:
            self.cost_data[source]['current_usage'] += 1

    async def get_monthly_cost(self, source: str) -> float:
        """Calculate monthly cost for a data source."""
        if source not in self.cost_data:
            return 0.0

        data = self.cost_data[source]
        return data['current_usage'] * data['cost_per_request']

    async def get_cost_report(self) -> Dict[str, Any]:
        """Generate cost report for all sources."""
        report = {
            'period': datetime.utcnow().strftime('%Y-%m'),
            'sources': {},
            'total_cost': 0.0
        }

        for source, data in self.cost_data.items():
            cost = await self.get_monthly_cost(source)
            report['sources'][source] = {
                'requests': data['current_usage'],
                'cost': cost,
                'limit': data['monthly_limit']
            }
            report['total_cost'] += cost

        return report