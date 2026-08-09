"""D1 Layer 4 - Dialog Manager.

The top-level orchestrator that ties together D2 (routing), D4 (resilient LLM),
D6 (prompts), and the RAG module. Manages multi-turn conversation flow.
"""

from src.routing.cascade import CascadeRouter
from src.routing.base import RouteResult
from src.resilience.client import ResilientLLMClient
from src.prompts.manager import PromptManager
from .context import DialogContext, DialogState, INTENT_SLOTS_MAP
from .slots import SlotFillingService
from .clarify import ClarificationService


class DialogManager:
    """Orchestrates multi-turn dialog: route -> fill slots -> clarify -> execute."""

    def __init__(
        self,
        router: CascadeRouter,
        llm_client: ResilientLLMClient,
        prompt_manager: PromptManager,
        rag_service=None,
    ):
        self.router = router
        self.llm_client = llm_client
        self.prompt_manager = prompt_manager
        self.rag_service = rag_service
        self.slot_service = SlotFillingService(llm_client, prompt_manager)
        self.clarify_service = ClarificationService(llm_client, prompt_manager)

    async def handle_message(self, user_input: str, context: DialogContext) -> str:
        """Process a user message and return a response.

        This is the main entry point for the dialog system.
        """
        context.turn_count += 1
        context.add_message("user", user_input)

        # Step 1: Intent detection (first turn or user changed topic)
        if context.state == DialogState.INTENT_DETECTION:
            route_result = await self.router.route(user_input)
            context.intent = route_result.intent
            context.slot_definitions = INTENT_SLOTS_MAP.get(context.intent, [])
            context.state = DialogState.SLOT_FILLING
            print(f"[Dialog] Routed to '{context.intent}' via {route_result.level}")

        # Step 2: Slot extraction
        if context.state == DialogState.SLOT_FILLING:
            extracted = await self.slot_service.extract_slots(user_input, context)
            context.slots.update(extracted)

            # Check if slots are complete
            missing = context.missing_slots()
            if missing and context.turn_count <= context.max_clarify_rounds:
                # Need more info -> clarify
                context.state = DialogState.CLARIFYING
                reply = await self.clarify_service.generate_clarification(context)
                context.add_message("assistant", reply)
                context.state = DialogState.SLOT_FILLING
                return reply

        # Step 3: Slots complete (or max rounds reached) -> execute
        return await self._execute_intent(context, user_input)

    async def _execute_intent(self, context: DialogContext, user_input: str) -> str:
        """Execute the detected intent: RAG for FAQ, template for tool calls."""
        context.state = DialogState.EXECUTING

        if context.intent == "human":
            reply = (
                "好的，正在为您转接人工客服，请稍候...\n\n"
                "当前排队人数：3人，预计等待2分钟。"
            )
            context.add_message("assistant", reply)
            context.state = DialogState.DONE
            return reply

        if context.intent == "complaint":
            reply = (
                "非常抱歉给您带来了不好的体验。您的反馈已记录，"
                "我们的客服主管将在24小时内联系您处理。\n\n"
                "投诉编号：TS" + str(abs(hash(context.session_id)) % 100000).zfill(5)
            )
            context.add_message("assistant", reply)
            context.state = DialogState.DONE
            return reply

        if context.intent == "refund":
            order_id = context.slots.get("order_id", "未知")
            reason = context.slots.get("reason", "未说明")
            reply = (
                f"已为您发起退款申请：\n"
                f"  订单编号：{order_id}\n"
                f"  退款原因：{reason}\n"
                f"  预计审核时间：1-3个工作日\n\n"
                f"审核结果将通过短信通知您。"
            )
            context.add_message("assistant", reply)
            context.state = DialogState.DONE
            return reply

        if context.intent == "query_order":
            order_id = context.slots.get("order_id", "未知")
            reply = (
                f"订单查询结果：\n"
                f"  订单编号：{order_id}\n"
                f"  订单状态：运输中\n"
                f"  预计送达：明天下午\n\n"
                f"物流轨迹：已到达【XX转运中心】，正在派送中。"
            )
            context.add_message("assistant", reply)
            context.state = DialogState.DONE
            return reply

        # Default: FAQ via RAG
        context.state = DialogState.RETRIEVING
        if self.rag_service:
            reply = await self.rag_service.answer(user_input, context, self.llm_client)
        else:
            # Simple FAQ fallback
            reply = self._simple_faq_answer(user_input)

        context.add_message("assistant", reply)
        context.state = DialogState.DONE
        return reply

    def _simple_faq_answer(self, user_input: str) -> str:
        """Simple FAQ matching without RAG (fallback)."""
        faq_db = {
            "优惠券": "优惠券使用规则：1. 下单时在结算页选择可用优惠券 2. 每笔订单只能使用一张 3. 有效期30天。",
            "会员": "会员权益：1. 专属折扣 2. 免费配送 3. 优先客服。开通请前往「我的-会员中心」。",
            "积分": "积分规则：1. 消费1元=1积分 2. 100积分=1元 3. 积分有效期1年。",
            "地址": "修改收货地址：进入「我的-地址管理」，点击对应地址进行修改。",
            "时间": "客服工作时间：9:00-21:00，全年无休。",
        }
        for keyword, answer in faq_db.items():
            if keyword in user_input:
                return answer
        return (
            "我暂时无法回答这个问题。\n\n"
            "您可以尝试：\n"
            "1. 换一种方式描述您的问题\n"
            "2. 回复「转人工」联系人工客服\n"
            "3. 访问帮助中心查看常见问题"
        )
