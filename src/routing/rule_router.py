"""D2 Layer 3 - L1 Rule Router.

Fastest routing level: keyword/regex matching (~1ms).
Handles the most common and explicit user intents.
"""

import re
from .base import BaseRouter, RouteResult


class RuleRouter(BaseRouter):
    """L1: Keyword and regex-based routing."""

    RULES: dict[str, list[str]] = {
        "refund": [
            r"(退款|退货|退钱|退掉|申请退)",
            r"(商品|东西).*(坏了|破损|质量)",
            r"不想要了",
        ],
        "query_order": [
            r"(查询|查看|看一下|查一下).*(订单|物流|快递|状态)",
            r"订单号\s*[A-Za-z0-9]+",
            r"(到哪了|什么时候到|发货了吗)",
        ],
        "human": [
            r"(人工|客服|真人|转人工)",
            r"找人工",
        ],
        "complaint": [
            r"(投诉|差评|态度)",
        ],
    }

    async def route(self, user_input: str) -> RouteResult | None:
        for intent, patterns in self.RULES.items():
            for pattern in patterns:
                if re.search(pattern, user_input, re.IGNORECASE):
                    return RouteResult(intent, 1.0, "L1")
        return None
