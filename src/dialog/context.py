"""D1 Layer 4 - Dialog context and slot definitions.

Maintains multi-turn conversation state and defines what slots
each intent requires before it can be executed.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DialogState(Enum):
    INTENT_DETECTION = "intent_detection"
    SLOT_FILLING = "slot_filling"
    CLARIFYING = "clarifying"
    RETRIEVING = "retrieving"
    EXECUTING = "executing"
    DONE = "done"


@dataclass
class SlotDefinition:
    name: str
    description: str
    required: bool = True
    example: str = ""


@dataclass
class DialogContext:
    session_id: str
    state: DialogState = DialogState.INTENT_DETECTION
    intent: Optional[str] = None
    slots: dict = field(default_factory=dict)
    slot_definitions: list[SlotDefinition] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    turn_count: int = 0
    max_clarify_rounds: int = 2

    def missing_slots(self) -> list[SlotDefinition]:
        return [
            s for s in self.slot_definitions
            if s.required and s.name not in self.slots
        ]

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "intent": self.intent,
            "slots": self.slots,
            "turn_count": self.turn_count,
            "history": self.history[-10:],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DialogContext":
        ctx = cls(session_id=data.get("session_id", "default"))
        ctx.state = DialogState(data.get("state", "intent_detection"))
        ctx.intent = data.get("intent")
        ctx.slots = data.get("slots", {})
        ctx.turn_count = data.get("turn_count", 0)
        ctx.history = data.get("history", [])
        return ctx


INTENT_SLOTS_MAP: dict[str, list[SlotDefinition]] = {
    "refund": [
        SlotDefinition("order_id", "订单编号", example="DD20240801001"),
        SlotDefinition("reason", "退款原因", example="商品损坏"),
    ],
    "query_order": [
        SlotDefinition("order_id", "订单编号", example="DD20240801001"),
    ],
    "faq": [],
    "human": [],
    "complaint": [],
}
