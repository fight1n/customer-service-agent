"""D2 Layer 3 - Router base classes and result types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RouteResult:
    intent: str
    confidence: float
    level: str  # "L1", "L2", "L3", "default"

    def __str__(self):
        return f"[{self.level}] intent={self.intent} confidence={self.confidence:.2f}"


class BaseRouter(ABC):
    """Abstract router. Returns None if it cannot route (falls through to next level)."""

    @abstractmethod
    async def route(self, user_input: str) -> RouteResult | None:
        ...
