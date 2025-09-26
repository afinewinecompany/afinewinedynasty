"""Backup data source strategy and failover management."""

import logging
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime, timedelta
import asyncio

from app.services.mlb_api_service import MLBAPIService
from app.services.fangraphs_service import FangraphsService
from app.services.pipeline_monitoring import PipelineMonitor, DataSource

logger = logging.getLogger(__name__)


class SourceStatus(Enum):
    """Data source availability status."""
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"


class SourcePriority(Enum):
    """Data source priority levels."""
    PRIMARY = 1
    SECONDARY = 2
    TERTIARY = 3
    FALLBACK = 4


class DataSourceManager:
    """Manage data sources with automatic failover and recovery."""

    def __init__(self):
        self.sources = {
            DataSource.MLB_API: {
                'service': MLBAPIService,
                'priority': SourcePriority.PRIMARY,
                'status': SourceStatus.AVAILABLE,
                'last_check': None,
                'failure_count': 0,
                'max_failures': 3,
                'cooldown_minutes': 30,
                'capabilities': ['prospects', 'stats', 'teams', 'schedule']
            },
            DataSource.FANGRAPHS: {
                'service': FangraphsService,
                'priority': SourcePriority.SECONDARY,
                'status': SourceStatus.AVAILABLE,
                'last_check': None,
                'failure_count': 0,
                'max_failures': 5,
                'cooldown_minutes': 60,
                'capabilities': ['prospects', 'stats', 'scouting_grades', 'rankings']
            }
        }

        self.monitor = PipelineMonitor()
        self.health_check_interval = 300  # 5 minutes
        self.last_health_check = None

    async def get_available_source(self, capability: str) -> Optional[DataSource]:
        """
        Get the best available data source for a specific capability.

        Args:
            capability: The required data capability (e.g., 'prospects', 'stats')

        Returns:
            Best available DataSource or None if all sources are down
        """
        # Run health check if needed
        await self._check_sources_health()

        # Filter sources by capability and availability
        capable_sources = [
            (source, config) for source, config in self.sources.items()
            if capability in config['capabilities'] and config['status'] != SourceStatus.UNAVAILABLE
        ]

        if not capable_sources:
            logger.error(f"No available sources for capability: {capability}")
            return None

        # Sort by priority and status
        capable_sources.sort(key=lambda x: (
            x[1]['priority'].value,
            0 if x[1]['status'] == SourceStatus.AVAILABLE else 1
        ))

        selected_source = capable_sources[0][0]
        logger.info(f"Selected {selected_source.value} for {capability} (status: {capable_sources[0][1]['status'].value})")

        return selected_source

    async def _check_sources_health(self):
        """Periodically check health of all data sources."""
        current_time = datetime.utcnow()

        # Check if health check is needed
        if self.last_health_check:
            time_since_check = (current_time - self.last_health_check).total_seconds()
            if time_since_check < self.health_check_interval:
                return

        logger.info("Running data source health checks")
        self.last_health_check = current_time

        for source, config in self.sources.items():
            try:
                # Check if source is in cooldown
                if config['status'] == SourceStatus.UNAVAILABLE and config['last_check']:
                    cooldown_elapsed = (current_time - config['last_check']).total_seconds() / 60
                    if cooldown_elapsed < config['cooldown_minutes']:
                        logger.info(f"{source.value} still in cooldown ({cooldown_elapsed:.1f}/{config['cooldown_minutes']} min)")
                        continue

                # Perform health check
                is_healthy = await self._health_check_source(source)

                if is_healthy:
                    if config['status'] == SourceStatus.UNAVAILABLE:
                        logger.info(f"{source.value} recovered and is now available")
                        await self.monitor.send_alert(
                            level='info',
                            message=f"Data source {source.value} has recovered"
                        )

                    config['status'] = SourceStatus.AVAILABLE
                    config['failure_count'] = 0
                else:
                    config['failure_count'] += 1

                    if config['failure_count'] >= config['max_failures']:
                        config['status'] = SourceStatus.UNAVAILABLE
                        await self.monitor.send_alert(
                            level='error',
                            message=f"Data source {source.value} marked as unavailable after {config['failure_count']} failures"
                        )
                    else:
                        config['status'] = SourceStatus.DEGRADED

                config['last_check'] = current_time

            except Exception as e:
                logger.error(f"Error checking health of {source.value}: {str(e)}")
                config['status'] = SourceStatus.DEGRADED

    async def _health_check_source(self, source: DataSource) -> bool:
        """
        Perform a health check on a specific data source.

        Returns:
            True if source is healthy, False otherwise
        """
        try:
            if source == DataSource.MLB_API:
                # Simple MLB API health check
                service = MLBAPIService()
                # Try to fetch a small amount of data
                test_data = await service.get_top_prospects(limit=1)
                return test_data is not None and len(test_data) > 0

            elif source == DataSource.FANGRAPHS:
                # Simple Fangraphs health check
                async with FangraphsService() as service:
                    # Try to fetch top prospects list
                    test_data = await service.get_top_prospects_list(limit=1)
                    return test_data is not None and len(test_data) > 0

            return False

        except Exception as e:
            logger.warning(f"Health check failed for {source.value}: {str(e)}")
            return False

    async def mark_source_failed(self, source: DataSource, error: str):
        """Mark a source as failed and trigger failover if needed."""
        if source not in self.sources:
            return

        config = self.sources[source]
        config['failure_count'] += 1
        config['last_check'] = datetime.utcnow()

        logger.warning(f"{source.value} failure #{config['failure_count']}: {error}")

        if config['failure_count'] >= config['max_failures']:
            config['status'] = SourceStatus.UNAVAILABLE
            await self.monitor.send_alert(
                level='error',
                message=f"{source.value} marked unavailable: {error}"
            )

            # Trigger failover notification
            await self._notify_failover(source)
        else:
            config['status'] = SourceStatus.DEGRADED

    async def mark_source_rate_limited(self, source: DataSource):
        """Mark a source as rate limited."""
        if source not in self.sources:
            return

        config = self.sources[source]
        config['status'] = SourceStatus.RATE_LIMITED
        config['last_check'] = datetime.utcnow()

        logger.warning(f"{source.value} is rate limited")

    async def _notify_failover(self, failed_source: DataSource):
        """Notify about failover to backup source."""
        # Find next available source
        for source, config in sorted(self.sources.items(), key=lambda x: x[1]['priority'].value):
            if source != failed_source and config['status'] == SourceStatus.AVAILABLE:
                await self.monitor.send_alert(
                    level='warning',
                    message=f"Failing over from {failed_source.value} to {source.value}"
                )
                return

        # No backup available
        await self.monitor.send_alert(
            level='critical',
            message=f"No backup source available after {failed_source.value} failure"
        )

    async def get_source_status_report(self) -> Dict[str, Any]:
        """Generate a status report for all data sources."""
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'sources': {}
        }

        for source, config in self.sources.items():
            report['sources'][source.value] = {
                'status': config['status'].value,
                'priority': config['priority'].name,
                'failure_count': config['failure_count'],
                'last_check': config['last_check'].isoformat() if config['last_check'] else None,
                'capabilities': config['capabilities']
            }

        return report


class FailoverOrchestrator:
    """Orchestrate failover and recovery procedures."""

    def __init__(self, source_manager: DataSourceManager):
        self.source_manager = source_manager
        self.monitor = PipelineMonitor()
        self.retry_strategies = {
            'exponential_backoff': self._exponential_backoff_retry,
            'linear_backoff': self._linear_backoff_retry,
            'immediate': self._immediate_retry
        }

    async def fetch_with_failover(
        self,
        capability: str,
        fetch_function: str,
        *args,
        **kwargs
    ) -> Optional[Any]:
        """
        Fetch data with automatic failover to backup sources.

        Args:
            capability: Required capability (e.g., 'prospects')
            fetch_function: Name of the function to call on the service
            *args, **kwargs: Arguments to pass to the fetch function

        Returns:
            Fetched data or None if all sources fail
        """
        attempted_sources = []

        while True:
            # Get next available source
            source = await self.source_manager.get_available_source(capability)

            if source is None:
                logger.error(f"No available sources for {capability}")
                break

            if source in attempted_sources:
                logger.error(f"All sources attempted for {capability}, failing")
                break

            attempted_sources.append(source)

            try:
                # Get service instance
                service_class = self.source_manager.sources[source]['service']

                if source == DataSource.FANGRAPHS:
                    async with service_class() as service:
                        if hasattr(service, fetch_function):
                            result = await getattr(service, fetch_function)(*args, **kwargs)
                            if result is not None:
                                logger.info(f"Successfully fetched {capability} from {source.value}")
                                return result
                else:
                    service = service_class()
                    if hasattr(service, fetch_function):
                        result = await getattr(service, fetch_function)(*args, **kwargs)
                        if result is not None:
                            logger.info(f"Successfully fetched {capability} from {source.value}")
                            return result

            except Exception as e:
                logger.error(f"Failed to fetch {capability} from {source.value}: {str(e)}")
                await self.source_manager.mark_source_failed(source, str(e))

        # All sources failed
        await self.monitor.send_alert(
            level='critical',
            message=f"Failed to fetch {capability} from all available sources"
        )
        return None

    async def _exponential_backoff_retry(
        self,
        func: Callable,
        max_attempts: int = 3,
        initial_delay: float = 1.0
    ) -> Optional[Any]:
        """Retry with exponential backoff."""
        delay = initial_delay

        for attempt in range(max_attempts):
            try:
                result = await func()
                if result is not None:
                    return result
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.info(f"Retry {attempt + 1}/{max_attempts} after {delay}s")
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    raise

        return None

    async def _linear_backoff_retry(
        self,
        func: Callable,
        max_attempts: int = 3,
        delay: float = 2.0
    ) -> Optional[Any]:
        """Retry with linear backoff."""
        for attempt in range(max_attempts):
            try:
                result = await func()
                if result is not None:
                    return result
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.info(f"Retry {attempt + 1}/{max_attempts} after {delay}s")
                    await asyncio.sleep(delay)
                else:
                    raise

        return None

    async def _immediate_retry(
        self,
        func: Callable,
        max_attempts: int = 3
    ) -> Optional[Any]:
        """Retry immediately without delay."""
        for attempt in range(max_attempts):
            try:
                result = await func()
                if result is not None:
                    return result
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise

        return None


class GracefulDegradation:
    """Manage graceful degradation when data sources are limited."""

    def __init__(self, source_manager: DataSourceManager):
        self.source_manager = source_manager
        self.degradation_levels = {
            'full': ['prospects', 'stats', 'scouting_grades', 'rankings'],
            'limited': ['prospects', 'stats'],
            'minimal': ['prospects'],
            'emergency': []
        }

    async def get_degradation_level(self) -> str:
        """Determine current degradation level based on source availability."""
        available_capabilities = set()

        for source, config in self.source_manager.sources.items():
            if config['status'] in [SourceStatus.AVAILABLE, SourceStatus.DEGRADED]:
                available_capabilities.update(config['capabilities'])

        # Determine degradation level
        if len(available_capabilities) >= 4:
            return 'full'
        elif len(available_capabilities) >= 2:
            return 'limited'
        elif len(available_capabilities) >= 1:
            return 'minimal'
        else:
            return 'emergency'

    async def get_available_features(self) -> List[str]:
        """Get list of available features based on current degradation level."""
        level = await self.get_degradation_level()
        return self.degradation_levels[level]

    async def notify_degradation(self, level: str):
        """Notify about service degradation."""
        monitor = PipelineMonitor()

        if level == 'emergency':
            await monitor.send_alert(
                level='critical',
                message="Emergency mode: No data sources available"
            )
        elif level == 'minimal':
            await monitor.send_alert(
                level='error',
                message="Minimal service: Only basic prospect data available"
            )
        elif level == 'limited':
            await monitor.send_alert(
                level='warning',
                message="Limited service: Some features unavailable"
            )