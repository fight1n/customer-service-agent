"""D1 Layer 4 - Slot filling service.

Extracts slot values from user input using LLM (via D4 resilient client)
and D6 prompt templates.
"""

from src.resilience.client import ResilientLLMClient
from src.prompts.manager import PromptManager
from .context import DialogContext


class SlotFillingService:
    """Extracts slot values from user input via LLM."""

    def __init__(self, llm_client: ResilientLLMClient, prompt_manager: PromptManager):
        self.llm_client = llm_client
        self.prompt_manager = prompt_manager

    async def extract_slots(self, user_input: str, context: DialogContext) -> dict:
        """Extract missing slot values from user input."""
        missing = context.missing_slots()
        if not missing:
            return {}

        slot_desc = "\n".join(
            f"- {s.name}: {s.description}（示例: {s.example}）"
            for s in missing
        )

        prompt = self.prompt_manager.render("slot_extraction", {
            "intent": context.intent or "unknown",
            "slot_descriptions": slot_desc,
            "user_input": user_input,
            "existing_slots": str(context.slots),
        })

        try:
            result = await self.llm_client.structured_call(prompt)
            if isinstance(result, dict):
                valid_keys = {s.name for s in context.slot_definitions}
                return {k: v for k, v in result.items() if k in valid_keys}
        except Exception as e:
            print(f"[SlotFilling] LLM extraction failed: {e}")

        return {}
