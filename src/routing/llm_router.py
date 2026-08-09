"""D2 Layer 3 - L3 LLM Router.

Slowest but most accurate: uses LLM for complex intent classification.
Protected by D4's circuit breaker via ResilientLLMClient.
"""

from .base import BaseRouter, RouteResult
from src.resilience.client import ResilientLLMClient
from src.prompts.manager import PromptManager


class LLMRouter(BaseRouter):
    """L3: LLM-based intent classification with RAG context support."""

    def __init__(self, llm_client: ResilientLLMClient, prompt_manager: PromptManager):
        self.llm_client = llm_client
        self.prompt_manager = prompt_manager

    async def route(self, user_input: str) -> RouteResult | None:
        try:
            prompt = self.prompt_manager.render("intent_route", {
                "rag_context": "(无额外知识库参考)",
                "user_input": user_input,
            })
            result = await self.llm_client.structured_call(prompt)
            intent = result.get("intent", "faq")
            return RouteResult(intent, 0.6, "L3")
        except Exception as e:
            print(f"[L3 LLMRouter] Failed: {e}")
            return None
