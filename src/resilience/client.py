"""D4 Layer 2 - Resilient LLM client.

Wraps D6's ModelAdapter with circuit breaker + retry + multi-model failover.
This is the single entry point for all LLM calls in the system.
"""

import asyncio
from typing import AsyncIterator

from src.models.adapter import ModelAdapter, ModelConfig, ModelFactory
from .circuit_breaker import CircuitBreaker, CircuitConfig, CircuitOpenError
from .retry import RetryPolicy, RetryConfig


class AllProvidersDownError(Exception):
    """All LLM providers are unavailable."""
    pass


class ResilientLLMClient:
    """High-availability LLM client with circuit breaker, retry, and failover.

    Usage:
        client = ResilientLLMClient(primary_config, fallback_configs)
        reply = await client.generate("Hello")
    """

    def __init__(
        self,
        primary_adapter: ModelAdapter,
        fallback_adapters: list[ModelAdapter] | None = None,
        circuit_config: CircuitConfig | None = None,
        retry_config: RetryConfig | None = None,
    ):
        self.adapters: list[ModelAdapter] = [primary_adapter]
        if fallback_adapters:
            self.adapters.extend(fallback_adapters)

        self.circuits = {
            f"provider_{i}": CircuitBreaker(f"provider_{i}", circuit_config)
            for i in range(len(self.adapters))
        }
        self.retry = RetryPolicy(retry_config)
        self._current_index = 0

    async def generate(self, prompt: str, system: str = "", **kwargs) -> str:
        """Generate completion with full resilience."""
        errors = []

        for i, adapter in enumerate(self.adapters):
            circuit = self.circuits[f"provider_{i}"]
            try:
                result = await self.retry.execute(
                    circuit.call,
                    self._safe_generate,
                    adapter,
                    prompt,
                    system,
                    **kwargs
                )
                self._current_index = i
                return result
            except CircuitOpenError:
                errors.append(f"{adapter.config.provider}: circuit open")
                continue
            except Exception as e:
                errors.append(f"{adapter.config.provider}: {type(e).__name__}: {e}")
                continue

        raise AllProvidersDownError(
            f"All LLM providers failed: {'; '.join(errors)}"
        )

    async def stream_generate(self, prompt: str, system: str = "", **kwargs) -> AsyncIterator[str]:
        """Stream tokens with resilience. Tries providers in order."""
        errors = []
        for i, adapter in enumerate(self.adapters):
            circuit = self.circuits[f"provider_{i}"]
            try:
                if circuit.state.value == "open":
                    raise CircuitOpenError(f"circuit open")

                async for token in adapter.stream_generate(prompt, system, **kwargs):
                    yield token
                await circuit._on_success()
                return
            except Exception as e:
                await circuit._on_failure()
                errors.append(f"{adapter.config.provider}: {e}")
                continue

        raise AllProvidersDownError(f"All providers failed: {'; '.join(errors)}")

    async def structured_call(self, prompt: str, schema: dict | None = None, **kwargs) -> dict:
        """Call LLM and parse JSON response."""
        raw = await self.generate(prompt, **kwargs)
        return await self._parse_json(raw)

    async def _safe_generate(self, adapter: ModelAdapter, prompt: str, system: str, **kwargs) -> str:
        """Wrapper with timeout for generate."""
        return await asyncio.wait_for(
            adapter.generate(prompt, system, **kwargs),
            timeout=adapter.config.timeout,
        )

    async def _parse_json(self, text: str) -> dict:
        import json
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [ln for ln in lines if not ln.startswith("```")]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
            return {}

    def get_status(self) -> list[dict]:
        """Return health status of all providers."""
        return [
            {
                "provider": self.adapters[i].config.provider,
                **self.circuits[f"provider_{i}"].get_status(),
            }
            for i in range(len(self.adapters))
        ]
