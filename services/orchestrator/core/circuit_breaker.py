"""
Circuit Breaker implementation for microservice calls.
Prevents cascading failures by tracking service health.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class CircuitState:
    """Tracks circuit breaker state for a service."""
    failures: int = 0
    last_failure_time: float = 0
    is_open: bool = False
    is_half_open: bool = False


class CircuitBreaker:
    """
    Circuit breaker for microservice calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests are rejected immediately
    - HALF_OPEN: Testing if service recovered, limited requests allowed
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._states: dict[str, CircuitState] = {}
        self._lock = asyncio.Lock()

    def _get_state(self, service_name: str) -> CircuitState:
        if service_name not in self._states:
            self._states[service_name] = CircuitState()
        return self._states[service_name]

    def _should_allow_request(self, state: CircuitState) -> bool:
        """Determine if a request should be allowed."""
        if not state.is_open:
            return True

        # Check if recovery timeout has passed to try half-open
        if time.time() - state.last_failure_time >= self.recovery_timeout:
            if state.is_half_open:
                # Already in half-open, check if we allow more test calls
                return state.failures < self.half_open_max_calls
            # Transition to half-open
            state.is_half_open = True
            state.failures = 0
            return True

        return False

    async def call(
        self,
        service_name: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """
        Execute a function with circuit breaker protection.

        Args:
            service_name: Identifier for the service
            func: Function to call
            *args, **kwargs: Arguments to pass to function

        Returns:
            Result from function call

        Raises:
            Exception: Re-raised if circuit is open or call fails
        """
        async with self._lock:
            state = self._get_state(service_name)

            if not self._should_allow_request(state):
                raise CircuitOpenError(
                    f"Circuit breaker open for {service_name}. "
                    f"Service unavailable after {state.failures} failures."
                )

        try:
            result = await func(*args, **kwargs)
            # Success - reset failure count
            async with self._lock:
                state = self._get_state(service_name)
                state.failures = 0
                if state.is_half_open:
                    state.is_open = False
                    state.is_half_open = False
                    logger.info(f"Circuit breaker CLOSED for {service_name}")
            return result
        except Exception as e:
            # Failure - increment counter
            async with self._lock:
                state = self._get_state(service_name)
                state.failures += 1
                state.last_failure_time = time.time()

                if state.failures >= self.failure_threshold:
                    state.is_open = True
                    logger.warning(
                        f"Circuit breaker OPEN for {service_name} after {state.failures} failures"
                    )
                elif state.is_half_open:
                    # Any failure in half-open goes back to open
                    state.is_open = True
                    state.is_half_open = False
                    logger.warning(f"Circuit breaker re-OPEN for {service_name}")

            raise e


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and rejecting requests."""
    pass


# Global circuit breaker instance for microservice calls
circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30.0,
    half_open_max_calls=2,
)


async def call_with_circuit_breaker(service_name: str, func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Convenience function to call with global circuit breaker."""
    return await circuit_breaker.call(service_name, func, *args, **kwargs)