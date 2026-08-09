"""D1 Layer 4 - Clarification service.

Generates follow-up questions when required slots are missing.
Has LLM mode (natural language) and template fallback (when LLM is unavailable).
"""

from src.resilience.client import ResilientLLMClient
from src.resilience.circuit_breaker import CircuitOpenError
from src.prompts.manager import PromptManager
from .context import DialogContext


class ClarificationService:
    """Generates clarification questions for missing slots."""

    TEMPLATE_CLARIFY: dict[str, str] = {
        "order_id": "请问您的订单号是多少？（例如：DD20240801001）",
        "reason": "请问退款原因是什么？（例如：商品损坏、不想要了）",
    }

    def __init__(self, llm_client: ResilientLLMClient, prompt_manager: PromptManager):
        self.llm_client = llm_client
        self.prompt_manager = prompt_manager

    async def generate_clarification(self, context: DialogContext) -> str:
        """Generate a clarification question. Falls back to template if LLM fails."""
        missing = context.missing_slots()
        if not missing:
            return ""

        # Try LLM-generated natural clarification
        try:
            missing_desc = "、".join(s.description for s in missing)
            last_input = context.history[-1]["content"] if context.history else ""

            prompt = self.prompt_manager.render("clarification", {
                "intent": context.intent or "unknown",
                "missing_info": missing_desc,
                "user_input": last_input,
            })

            reply = await self.llm_client.generate(prompt)
            if reply and len(reply) > 5:
                return reply.strip()
        except (CircuitOpenError, Exception) as e:
            print(f"[Clarification] LLM failed, using template: {e}")

        # Fallback: template-based clarification
        return self._template_clarify(missing)

    def _template_clarify(self, missing_slots) -> str:
        """Generate clarification from static templates (no LLM needed)."""
        questions = []
        for slot in missing_slots:
            template = self.TEMPLATE_CLARIFY.get(slot.name)
            if template:
                questions.append(template)
            else:
                questions.append(f"请提供{slot.description}。")

        return " ".join(questions)
