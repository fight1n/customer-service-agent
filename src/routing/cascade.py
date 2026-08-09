"""D2 Layer 3 - Cascade Router.

Orchestrates L1 -> L2 -> L3 routing in order.
Returns the first successful route result, or a default.
"""

from .base import BaseRouter, RouteResult
from .rule_router import RuleRouter
from .vector_router import VectorRouter
from .llm_router import LLMRouter


class CascadeRouter(BaseRouter):
    """Three-level cascade router: Rule -> Vector -> LLM."""

    def __init__(self, vector_router: VectorRouter | None = None, llm_router: LLMRouter | None = None):
        self.rule_router = RuleRouter()
        self.vector_router = vector_router
        self.llm_router = llm_router

    async def route(self, user_input: str) -> RouteResult:
        # L1: Rule-based (fastest)
        result = await self.rule_router.route(user_input)
        if result is not None:
            return result

        # L2: Vector-based
        if self.vector_router is not None:
            result = await self.vector_router.route(user_input)
            if result is not None:
                return result

        # L3: LLM-based (slowest, most accurate)
        if self.llm_router is not None:
            result = await self.llm_router.route(user_input)
            if result is not None:
                return result

        # Default fallback
        return RouteResult("faq", 0.0, "default")
