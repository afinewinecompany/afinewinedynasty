"""Circuit breaker pattern implementation for enhanced resilience."""

import asyncio
import logging
import time
from enum import Enum
from typing import Callable, Any, Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CircuitBreakerException(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Exception = Exception,
        success_threshold: int = 3,
        name: str = "default"
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open
            expected_exception: Exception type that triggers circuit breaker
            success_threshold: Number of successes needed to close circuit from half-open
            name: Name for logging and monitoring
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        self.name = name

        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change: datetime = datetime.utcnow()

        # Metrics
        self.total_requests = 0
        self.total_failures = 0
        self.total_timeouts = 0
        self.state_history = []

        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            self.total_requests += 1

            # Check if we should transition from OPEN to HALF_OPEN
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    await self._transition_to_half_open()
                else:
                    logger.warning(f"Circuit breaker {self.name} is OPEN, failing fast")
                    raise CircuitBreakerException(
                        f"Circuit breaker {self.name} is open. Last failure: {self.last_failure_time}"
                    )

            # Attempt the function call
            try:
                result = await self._execute_function(func, *args, **kwargs)
                await self._on_success()
                return result

            except self.expected_exception as e:
                await self._on_failure(e)
                raise

            except Exception as e:
                # Unexpected exceptions don't count as failures
                logger.error(f"Unexpected exception in circuit breaker {self.name}: {e}")
                raise

    async def _execute_function(self, func: Callable, *args, **kwargs) -> Any:
        """Execute the protected function."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    async def _on_success(self):
        """Handle successful function execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.info(f"Circuit breaker {self.name} success in HALF_OPEN: {self.success_count}/{self.success_threshold}")

            if self.success_count >= self.success_threshold:
                await self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    async def _on_failure(self, exception: Exception):
        """Handle failed function execution."""
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        logger.warning(f"Circuit breaker {self.name} failure {self.failure_count}/{self.failure_threshold}: {exception}")

        if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            await self._transition_to_open()
        elif self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open goes back to open
            await self._transition_to_open()

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True

        time_since_failure = datetime.utcnow() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.recovery_timeout

    async def _transition_to_open(self):
        """Transition circuit breaker to OPEN state."""
        previous_state = self.state
        self.state = CircuitState.OPEN
        self.last_state_change = datetime.utcnow()
        self.success_count = 0

        self._record_state_change(previous_state, CircuitState.OPEN)
        logger.error(f"Circuit breaker {self.name} transitioned to OPEN after {self.failure_count} failures")

    async def _transition_to_half_open(self):
        """Transition circuit breaker to HALF_OPEN state."""
        previous_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.last_state_change = datetime.utcnow()
        self.success_count = 0

        self._record_state_change(previous_state, CircuitState.HALF_OPEN)
        logger.info(f"Circuit breaker {self.name} transitioned to HALF_OPEN, testing recovery")

    async def _transition_to_closed(self):
        """Transition circuit breaker to CLOSED state."""
        previous_state = self.state
        self.state = CircuitState.CLOSED
        self.last_state_change = datetime.utcnow()
        self.failure_count = 0
        self.success_count = 0

        self._record_state_change(previous_state, CircuitState.CLOSED)
        logger.info(f"Circuit breaker {self.name} transitioned to CLOSED, service recovered")

    def _record_state_change(self, from_state: CircuitState, to_state: CircuitState):
        """Record state change for monitoring."""
        self.state_history.append({
            'from': from_state.value,
            'to': to_state.value,
            'timestamp': datetime.utcnow().isoformat(),
            'failure_count': self.failure_count
        })

        # Keep only last 100 state changes
        if len(self.state_history) > 100:
            self.state_history = self.state_history[-100:]

    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics."""
        uptime = datetime.utcnow() - self.last_state_change
        failure_rate = self.total_failures / self.total_requests if self.total_requests > 0 else 0

        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'total_requests': self.total_requests,
            'total_failures': self.total_failures,
            'failure_rate': failure_rate,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
            'last_state_change': self.last_state_change.isoformat(),
            'current_state_duration': uptime.total_seconds(),
            'state_history': self.state_history[-10:],  # Last 10 state changes
            'config': {
                'failure_threshold': self.failure_threshold,
                'recovery_timeout': self.recovery_timeout,
                'success_threshold': self.success_threshold
            }
        }

    async def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        async with self._lock:
            previous_state = self.state
            await self._transition_to_closed()
            logger.info(f"Circuit breaker {self.name} manually reset from {previous_state.value}")

    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        return self.state == CircuitState.OPEN

    def is_half_open(self) -> bool:
        """Check if circuit breaker is half-open."""
        return self.state == CircuitState.HALF_OPEN

    def is_closed(self) -> bool:
        """Check if circuit breaker is closed."""
        return self.state == CircuitState.CLOSED


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}

    def register(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Exception = Exception,
        success_threshold: int = 3
    ) -> CircuitBreaker:
        """Register a new circuit breaker."""
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            success_threshold=success_threshold,
            name=name
        )
        self.breakers[name] = breaker
        logger.info(f"Registered circuit breaker: {name}")
        return breaker

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self.breakers.get(name)

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all registered circuit breakers."""
        return {name: breaker.get_metrics() for name, breaker in self.breakers.items()}

    async def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self.breakers.values():
            await breaker.reset()
        logger.info("All circuit breakers reset")


# Global registry instance
circuit_breaker_registry = CircuitBreakerRegistry()


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: Exception = Exception,
    success_threshold: int = 3
):
    """Decorator for applying circuit breaker to functions."""
    def decorator(func):
        # Register circuit breaker if not exists
        breaker = circuit_breaker_registry.get(name)
        if not breaker:
            breaker = circuit_breaker_registry.register(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
                success_threshold=success_threshold
            )

        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)

        wrapper.circuit_breaker = breaker
        return wrapper

    return decorator