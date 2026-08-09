"""D6 Layer 1 - Model adapter abstraction.

Provides a unified interface for multiple LLM providers (DeepSeek, GLM, etc.)
so that switching models only requires a config change, not code changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator
import os
import json


@dataclass
class ModelConfig:
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.3
    max_tokens: int = 2048
    timeout: int = 15

    @classmethod
    def from_dict(cls, data: dict) -> "ModelConfig":
        raw = dict(data)
        val = raw.get("api_key", "")
        if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
            env_name = val[2:-1]
            raw["api_key"] = os.environ.get(env_name, "")
        return cls(**raw)


class ModelAdapter(ABC):
    """Abstract interface that every LLM provider adapter must implement."""

    def __init__(self, config: ModelConfig):
        self.config = config

    @abstractmethod
    async def generate(self, prompt: str, system: str = "", **kwargs) -> str:
        """Generate a completion string."""
        ...

    @abstractmethod
    async def stream_generate(self, prompt: str, system: str = "", **kwargs) -> AsyncIterator[str]:
        """Yield tokens one by one."""
        ...

    async def structured_call(self, prompt: str, schema: dict | None = None, **kwargs) -> dict:
        """Call LLM and parse JSON response. Falls back to best-effort parse."""
        raw = await self.generate(prompt, **kwargs)
        text = raw.strip()

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


class OpenAICompatibleAdapter(ModelAdapter):
    """Adapter for any provider that speaks the OpenAI chat completions API.
    Covers DeepSeek, GLM (Zhipu), Qwen (DashScope), and others.
    """

    def _get_client(self):
        from openai import AsyncOpenAI
        return AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

    async def generate(self, prompt: str, system: str = "", **kwargs) -> str:
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = await client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            messages=messages,
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        )
        return resp.choices[0].message.content or ""

    async def stream_generate(self, prompt: str, system: str = "", **kwargs) -> AsyncIterator[str]:
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        stream = await client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            messages=messages,
            temperature=kwargs.get("temperature", self.config.temperature),
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content


class DeepSeekAdapter(OpenAICompatibleAdapter):
    """DeepSeek adapter - uses OpenAI-compatible API."""
    pass


class GLMAdapter(OpenAICompatibleAdapter):
    """GLM (Zhipu BigModel) adapter - uses OpenAI-compatible API."""
    pass


class MockAdapter(ModelAdapter):
    """Offline mock adapter for development and testing without API keys."""

    async def generate(self, prompt: str, system: str = "", **kwargs) -> str:
        import re
        # Check more specific patterns first
        if "槽位" in prompt or "提取" in prompt and "槽位" in prompt:
            # Extract only from the "用户输入：" section, not from examples
            slots = {}
            user_input_section = ""
            if "用户输入：" in prompt:
                parts = prompt.split("用户输入：")
                if len(parts) > 1:
                    user_input_section = parts[1].split("已有槽位")[0] if "已有槽位" in parts[1] else parts[1]
            # Look for order ID pattern only in user input
            order_match = re.search(r'(DD\d+|[A-Z]{2}\d+)', user_input_section)
            if order_match:
                slots["order_id"] = order_match.group(1)
            # Look for refund reason keywords only in user input
            if "损坏" in user_input_section or "坏了" in user_input_section:
                slots["reason"] = "商品损坏"
            elif "不想要" in user_input_section:
                slots["reason"] = "不想要了"
            elif "质量" in user_input_section:
                slots["reason"] = "质量问题"
            return json.dumps(slots, ensure_ascii=False)
        if "反问" in prompt or "clarif" in prompt.lower() or "引导性问题" in prompt:
            return "请问您能详细描述一下遇到的问题吗？您可以通过以下方式补充：1. 提供订单号 2. 说明具体遇到的情况。"
        if "意图分类" in prompt or "intent" in prompt.lower() and "分类" in prompt:
            return '{"intent": "faq", "reason": "mock classification"}'
        if "知识库" in prompt or "客服" in prompt and "回答" in prompt:
            return "根据知识库内容，为您解答如下：该问题已在FAQ中有记录，请参考相关说明。"
        return "这是一个模拟回复。当前未配置真实API Key，系统运行在Mock模式。"

    async def stream_generate(self, prompt: str, system: str = "", **kwargs) -> AsyncIterator[str]:
        text = await self.generate(prompt, system, **kwargs)
        for ch in text:
            yield ch


class ModelFactory:
    """Factory that creates the right adapter from config."""

    _registry: dict[str, type[ModelAdapter]] = {
        "deepseek": DeepSeekAdapter,
        "glm": GLMAdapter,
        "mock": MockAdapter,
    }

    @classmethod
    def register(cls, provider: str, adapter_cls: type[ModelAdapter]):
        cls._registry[provider] = adapter_cls

    @classmethod
    def create(cls, config: ModelConfig) -> ModelAdapter:
        adapter_cls = cls._registry.get(config.provider)
        if adapter_cls is None:
            raise ValueError(f"Unknown provider: {config.provider}. "
                           f"Registered: {list(cls._registry.keys())}")
        return adapter_cls(config)

    @classmethod
    def create_from_config(cls, config_dict: dict) -> ModelAdapter:
        cfg = ModelConfig.from_dict(config_dict)
        if not cfg.api_key:
            print(f"[ModelFactory] No API key for '{cfg.provider}', falling back to MockAdapter")
            return MockAdapter(cfg)
        return cls.create(cfg)
