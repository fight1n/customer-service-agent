"""D4 Layer 2 - Retry with exponential backoff + jitter."""

import asyncio
import random
from dataclasses import dataclass


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True


class RetryPolicy:
    """Exponential backoff retry policy for async functions."""

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or RetryConfig()

    async def execute(self, func, *args, **kwargs):
        """Execute func with retry. Does NOT retry on CircuitOpenError."""
        from .circuit_breaker import CircuitOpenError

        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except CircuitOpenError:
                raise
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    delay = min(
                        self.config.base_delay * (self.config.exponential_base ** attempt),
                        self.config.max_delay,
                    )
                    if self.config.jitter:
                        delay *= 0.5 + random.random() * 0.5
                    print(f"[Retry] attempt {attempt+1}/{self.config.max_retries}, "
                          f"waiting {delay:.1f}s, error: {e}")
                    await asyncio.sleep(delay)

        raise last_error
