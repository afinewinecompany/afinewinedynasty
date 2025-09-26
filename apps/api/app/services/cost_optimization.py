"""Cost monitoring and optimization for data acquisition operations."""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json
from dataclasses import dataclass, asdict
import asyncio

from app.core.config import settings
from app.services.pipeline_monitoring import PipelineMonitor, AlertLevel

logger = logging.getLogger(__name__)


@dataclass
class CostMetrics:
    """Metrics for tracking operational costs."""
    timestamp: datetime
    source: str
    operation_type: str
    request_count: int
    data_volume_mb: float
    processing_time_seconds: float
    compute_cost: float
    storage_cost: float
    network_cost: float
    total_cost: float


class CostCategory(Enum):
    """Categories of operational costs."""
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    API = "api"
    PROCESSING = "processing"


class CostOptimizer:
    """Optimize data acquisition and processing costs."""

    def __init__(self):
        self.cost_history = []
        self.optimization_rules = self._initialize_optimization_rules()
        self.cost_thresholds = {
            'daily': 10.0,  # $10 per day
            'weekly': 50.0,  # $50 per week
            'monthly': 200.0  # $200 per month
        }
        self.monitor = PipelineMonitor()

    def _initialize_optimization_rules(self) -> Dict[str, Any]:
        """Initialize cost optimization rules."""
        return {
            'caching': {
                'enabled': True,
                'ttl_hours': 24,
                'cost_savings_factor': 0.8
            },
            'batch_processing': {
                'enabled': True,
                'optimal_batch_size': 100,
                'min_batch_size': 10
            },
            'request_deduplication': {
                'enabled': True,
                'window_minutes': 60
            },
            'data_compression': {
                'enabled': True,
                'compression_ratio': 0.3
            },
            'smart_scheduling': {
                'enabled': True,
                'off_peak_hours': [0, 1, 2, 3, 4, 5],
                'off_peak_discount': 0.2
            }
        }

    async def track_operation_cost(
        self,
        source: str,
        operation_type: str,
        request_count: int = 1,
        data_volume_mb: float = 0.0,
        processing_time_seconds: float = 0.0
    ) -> CostMetrics:
        """Track cost of a data operation."""
        # Calculate costs based on usage
        compute_cost = self._calculate_compute_cost(processing_time_seconds)
        storage_cost = self._calculate_storage_cost(data_volume_mb)
        network_cost = self._calculate_network_cost(data_volume_mb)
        total_cost = compute_cost + storage_cost + network_cost

        metrics = CostMetrics(
            timestamp=datetime.utcnow(),
            source=source,
            operation_type=operation_type,
            request_count=request_count,
            data_volume_mb=data_volume_mb,
            processing_time_seconds=processing_time_seconds,
            compute_cost=compute_cost,
            storage_cost=storage_cost,
            network_cost=network_cost,
            total_cost=total_cost
        )

        self.cost_history.append(metrics)

        # Check thresholds
        await self._check_cost_thresholds()

        logger.info(f"Operation cost tracked: {source}/{operation_type} = ${total_cost:.4f}")
        return metrics

    def _calculate_compute_cost(self, processing_time_seconds: float) -> float:
        """Calculate compute cost based on processing time."""
        # Assuming $0.0001 per CPU second (example rate)
        cpu_rate_per_second = 0.0001
        return processing_time_seconds * cpu_rate_per_second

    def _calculate_storage_cost(self, data_volume_mb: float) -> float:
        """Calculate storage cost based on data volume."""
        # Assuming $0.000001 per MB per day (example rate)
        storage_rate_per_mb_day = 0.000001
        return data_volume_mb * storage_rate_per_mb_day

    def _calculate_network_cost(self, data_volume_mb: float) -> float:
        """Calculate network transfer cost."""
        # Assuming $0.00001 per MB transferred (example rate)
        transfer_rate_per_mb = 0.00001
        return data_volume_mb * transfer_rate_per_mb

    async def _check_cost_thresholds(self):
        """Check if costs exceed defined thresholds."""
        current_time = datetime.utcnow()

        # Calculate costs for different periods
        daily_cost = self._calculate_period_cost(timedelta(days=1))
        weekly_cost = self._calculate_period_cost(timedelta(days=7))
        monthly_cost = self._calculate_period_cost(timedelta(days=30))

        # Check thresholds and alert if exceeded
        if daily_cost > self.cost_thresholds['daily']:
            await self.monitor.send_alert(
                level='warning',
                message=f"Daily cost threshold exceeded: ${daily_cost:.2f} > ${self.cost_thresholds['daily']}"
            )

        if weekly_cost > self.cost_thresholds['weekly']:
            await self.monitor.send_alert(
                level='warning',
                message=f"Weekly cost threshold exceeded: ${weekly_cost:.2f} > ${self.cost_thresholds['weekly']}"
            )

        if monthly_cost > self.cost_thresholds['monthly']:
            await self.monitor.send_alert(
                level='error',
                message=f"Monthly cost threshold exceeded: ${monthly_cost:.2f} > ${self.cost_thresholds['monthly']}"
            )

    def _calculate_period_cost(self, period: timedelta) -> float:
        """Calculate total cost for a given period."""
        cutoff_time = datetime.utcnow() - period
        period_costs = [
            m.total_cost for m in self.cost_history
            if m.timestamp >= cutoff_time
        ]
        return sum(period_costs)

    async def optimize_batch_size(
        self,
        current_batch_size: int,
        processing_time: float,
        error_rate: float
    ) -> int:
        """Optimize batch size for cost efficiency."""
        if not self.optimization_rules['batch_processing']['enabled']:
            return current_batch_size

        optimal_size = self.optimization_rules['batch_processing']['optimal_batch_size']
        min_size = self.optimization_rules['batch_processing']['min_batch_size']

        # Adjust based on performance metrics
        if error_rate > 0.05:  # More than 5% errors
            # Reduce batch size
            new_size = max(int(current_batch_size * 0.8), min_size)
        elif processing_time > 60:  # Taking too long
            # Reduce batch size
            new_size = max(int(current_batch_size * 0.9), min_size)
        elif error_rate < 0.01 and processing_time < 30:  # Running well
            # Increase batch size
            new_size = min(int(current_batch_size * 1.2), optimal_size * 2)
        else:
            # Move toward optimal size
            if current_batch_size < optimal_size:
                new_size = min(int(current_batch_size * 1.1), optimal_size)
            else:
                new_size = max(int(current_batch_size * 0.95), optimal_size)

        logger.info(f"Batch size optimization: {current_batch_size} -> {new_size}")
        return new_size

    async def should_use_cache(self, data_type: str, age_hours: float) -> bool:
        """Determine if cached data should be used to save costs."""
        if not self.optimization_rules['caching']['enabled']:
            return False

        ttl = self.optimization_rules['caching']['ttl_hours']
        return age_hours <= ttl

    async def get_optimal_scheduling_time(self) -> datetime:
        """Get optimal time for scheduling data operations."""
        if not self.optimization_rules['smart_scheduling']['enabled']:
            return datetime.utcnow()

        off_peak_hours = self.optimization_rules['smart_scheduling']['off_peak_hours']
        current_hour = datetime.utcnow().hour

        if current_hour in off_peak_hours:
            # Already in off-peak
            return datetime.utcnow()

        # Find next off-peak hour
        for hours_ahead in range(1, 24):
            target_hour = (current_hour + hours_ahead) % 24
            if target_hour in off_peak_hours:
                next_time = datetime.utcnow().replace(
                    hour=target_hour,
                    minute=0,
                    second=0,
                    microsecond=0
                )
                if next_time < datetime.utcnow():
                    next_time += timedelta(days=1)
                return next_time

        return datetime.utcnow()

    async def estimate_operation_cost(
        self,
        source: str,
        operation_type: str,
        request_count: int,
        data_volume_mb: float
    ) -> Dict[str, float]:
        """Estimate cost before executing operation."""
        # Base estimates
        est_processing_time = request_count * 0.5  # 0.5 seconds per request estimate
        est_compute = self._calculate_compute_cost(est_processing_time)
        est_storage = self._calculate_storage_cost(data_volume_mb)
        est_network = self._calculate_network_cost(data_volume_mb)

        # Apply optimization factors
        if self.optimization_rules['caching']['enabled']:
            cache_factor = self.optimization_rules['caching']['cost_savings_factor']
            est_compute *= cache_factor

        if self.optimization_rules['data_compression']['enabled']:
            compression_ratio = self.optimization_rules['data_compression']['compression_ratio']
            est_storage *= compression_ratio
            est_network *= compression_ratio

        current_hour = datetime.utcnow().hour
        if current_hour in self.optimization_rules['smart_scheduling']['off_peak_hours']:
            discount = self.optimization_rules['smart_scheduling']['off_peak_discount']
            est_compute *= (1 - discount)

        return {
            'compute': est_compute,
            'storage': est_storage,
            'network': est_network,
            'total': est_compute + est_storage + est_network
        }

    async def generate_cost_report(self, period_days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive cost report."""
        cutoff_time = datetime.utcnow() - timedelta(days=period_days)
        period_metrics = [m for m in self.cost_history if m.timestamp >= cutoff_time]

        report = {
            'period': f'last_{period_days}_days',
            'generated_at': datetime.utcnow().isoformat(),
            'summary': {
                'total_cost': sum(m.total_cost for m in period_metrics),
                'total_operations': len(period_metrics),
                'total_requests': sum(m.request_count for m in period_metrics),
                'total_data_mb': sum(m.data_volume_mb for m in period_metrics),
                'total_processing_seconds': sum(m.processing_time_seconds for m in period_metrics)
            },
            'breakdown_by_source': {},
            'breakdown_by_category': {},
            'daily_trend': {},
            'optimization_savings': {},
            'recommendations': []
        }

        # Breakdown by source
        sources = set(m.source for m in period_metrics)
        for source in sources:
            source_metrics = [m for m in period_metrics if m.source == source]
            report['breakdown_by_source'][source] = {
                'cost': sum(m.total_cost for m in source_metrics),
                'operations': len(source_metrics),
                'requests': sum(m.request_count for m in source_metrics)
            }

        # Breakdown by cost category
        report['breakdown_by_category'] = {
            'compute': sum(m.compute_cost for m in period_metrics),
            'storage': sum(m.storage_cost for m in period_metrics),
            'network': sum(m.network_cost for m in period_metrics)
        }

        # Daily trend
        for i in range(period_days):
            day = datetime.utcnow().date() - timedelta(days=i)
            day_metrics = [
                m for m in period_metrics
                if m.timestamp.date() == day
            ]
            report['daily_trend'][day.isoformat()] = sum(m.total_cost for m in day_metrics)

        # Optimization savings estimate
        report['optimization_savings'] = await self._calculate_optimization_savings(period_metrics)

        # Generate recommendations
        report['recommendations'] = self._generate_cost_recommendations(report)

        return report

    async def _calculate_optimization_savings(self, metrics: List[CostMetrics]) -> Dict[str, float]:
        """Calculate estimated savings from optimizations."""
        baseline_cost = sum(m.total_cost for m in metrics)

        savings = {
            'caching': 0.0,
            'batch_processing': 0.0,
            'compression': 0.0,
            'off_peak_scheduling': 0.0
        }

        if self.optimization_rules['caching']['enabled']:
            savings['caching'] = baseline_cost * 0.2  # Estimate 20% savings

        if self.optimization_rules['batch_processing']['enabled']:
            savings['batch_processing'] = baseline_cost * 0.15  # Estimate 15% savings

        if self.optimization_rules['data_compression']['enabled']:
            compression_factor = 1 - self.optimization_rules['data_compression']['compression_ratio']
            savings['compression'] = baseline_cost * compression_factor * 0.3  # Network/storage portion

        if self.optimization_rules['smart_scheduling']['enabled']:
            off_peak_discount = self.optimization_rules['smart_scheduling']['off_peak_discount']
            savings['off_peak_scheduling'] = baseline_cost * off_peak_discount * 0.5  # Assume 50% could be scheduled

        savings['total'] = sum(v for k, v in savings.items() if k != 'total')
        return savings

    def _generate_cost_recommendations(self, report: Dict) -> List[str]:
        """Generate cost optimization recommendations."""
        recommendations = []

        # Check if costs are increasing
        daily_costs = list(report['daily_trend'].values())
        if len(daily_costs) >= 7:
            week_ago = sum(daily_costs[-7:-3])
            recent = sum(daily_costs[-3:])
            if recent > week_ago * 1.2:
                recommendations.append("Costs trending upward - review recent changes")

        # Check source costs
        for source, data in report['breakdown_by_source'].items():
            if data['cost'] > report['summary']['total_cost'] * 0.5:
                recommendations.append(f"High costs from {source} - consider optimizing requests")

        # Check category costs
        if report['breakdown_by_category']['network'] > report['summary']['total_cost'] * 0.4:
            recommendations.append("High network costs - enable compression")

        if report['breakdown_by_category']['compute'] > report['summary']['total_cost'] * 0.5:
            recommendations.append("High compute costs - optimize processing algorithms")

        # Check optimization usage
        if not self.optimization_rules['caching']['enabled']:
            recommendations.append("Enable caching to reduce costs")

        if not self.optimization_rules['smart_scheduling']['enabled']:
            recommendations.append("Enable off-peak scheduling for cost savings")

        return recommendations


class ResourceUsageMonitor:
    """Monitor resource usage for cost tracking."""

    def __init__(self):
        self.usage_metrics = {
            'cpu': [],
            'memory': [],
            'disk': [],
            'network': []
        }

    async def record_usage(
        self,
        cpu_percent: float,
        memory_mb: float,
        disk_io_mb: float,
        network_io_mb: float
    ):
        """Record resource usage metrics."""
        timestamp = datetime.utcnow()

        self.usage_metrics['cpu'].append((timestamp, cpu_percent))
        self.usage_metrics['memory'].append((timestamp, memory_mb))
        self.usage_metrics['disk'].append((timestamp, disk_io_mb))
        self.usage_metrics['network'].append((timestamp, network_io_mb))

        # Keep only last 24 hours of metrics
        cutoff = timestamp - timedelta(hours=24)
        for key in self.usage_metrics:
            self.usage_metrics[key] = [
                (ts, val) for ts, val in self.usage_metrics[key]
                if ts > cutoff
            ]

    async def get_average_usage(self, hours: int = 1) -> Dict[str, float]:
        """Get average resource usage over specified period."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        averages = {}
        for resource, metrics in self.usage_metrics.items():
            recent_values = [val for ts, val in metrics if ts > cutoff]
            if recent_values:
                averages[resource] = sum(recent_values) / len(recent_values)
            else:
                averages[resource] = 0.0

        return averages

    async def detect_resource_spikes(self) -> List[Dict[str, Any]]:
        """Detect unusual resource usage spikes."""
        spikes = []

        for resource, metrics in self.usage_metrics.items():
            if len(metrics) < 10:
                continue

            # Calculate baseline (median of last 100 points)
            recent_values = [val for _, val in metrics[-100:]]
            baseline = sorted(recent_values)[len(recent_values) // 2]

            # Check for spikes (3x baseline)
            for timestamp, value in metrics[-10:]:
                if value > baseline * 3:
                    spikes.append({
                        'resource': resource,
                        'timestamp': timestamp.isoformat(),
                        'value': value,
                        'baseline': baseline,
                        'factor': value / baseline if baseline > 0 else 0
                    })

        return spikes