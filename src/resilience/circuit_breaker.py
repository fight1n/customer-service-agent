"""D4 Layer 2 - Circuit Breaker.

Protects downstream LLM services from cascading failures.
States: CLOSED -> OPEN -> HALF_OPEN -> CLOSED/OPEN
"""

import asyncio
import time
from enum import Enum
from dataclasses import dataclass


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitConfig:
    failure_threshold: int = 5
    failure_rate_threshold: float = 0.5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3
    min_requests: int = 10


@dataclass
class CircuitMetrics:
    total: int = 0
    failures: int = 0
    consecutive_failures: int = 0
    last_failure_time: float = 0.0


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open and rejects a call."""
    pass


class CircuitBreaker:
    """Circuit breaker that wraps async function calls."""

    def __init__(self, name: str, config: CircuitConfig | None = None):
        self.name = name
        self.config = config or CircuitConfig()
        self.state = CircuitState.CLOSED
        self.metrics = CircuitMetrics()
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """Execute func through the circuit breaker."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                elapsed = time.time() - self.metrics.last_failure_time
                if elapsed > self.config.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                else:
                    raise CircuitOpenError(
                        f"Circuit [{self.name}] is OPEN. "
                        f"Retry in {self.config.recovery_timeout - elapsed:.0f}s."
                    )

            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitOpenError(
                        f"Circuit [{self.name}] HALF_OPEN at max probe calls."
                    )
                self._half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except CircuitOpenError:
            raise
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self):
        async with self._lock:
            self.metrics.total += 1
            self.metrics.consecutive_failures = 0
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.metrics = CircuitMetrics()

    async def _on_failure(self):
        async with self._lock:
            self.metrics.total += 1
            self.metrics.failures += 1
            self.metrics.consecutive_failures += 1
            self.metrics.last_failure_time = time.time()

            if self.metrics.consecutive_failures >= self.config.failure_threshold:
                self.state = CircuitState.OPEN

            if self.metrics.total >= self.config.min_requests:
                rate = self.metrics.failures / self.metrics.total
                if rate >= self.config.failure_rate_threshold:
                    self.state = CircuitState.OPEN

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "total": self.metrics.total,
            "failures": self.metrics.failures,
            "consecutive_failures": self.metrics.consecutive_failures,
        }
