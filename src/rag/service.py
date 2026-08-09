"""Simple RAG module - knowledge base retrieval + LLM generation.

Uses in-memory FAQ database with keyword matching for retrieval,
and D4's ResilientLLMClient for answer generation with D6's prompt templates.
"""

from src.resilience.client import ResilientLLMClient
from src.prompts.manager import PromptManager
from src.dialog.context import DialogContext


FAQ_KNOWLEDGE_BASE = [
    {"id": "faq_001", "category": "优惠", "q": "怎么使用优惠券", "a": "优惠券使用规则：1. 下单时在结算页选择可用优惠券 2. 每笔订单只能使用一张 3. 有效期30天。"},
    {"id": "faq_002", "category": "优惠", "q": "优惠券过期了怎么办", "a": "过期优惠券无法使用，建议关注活动页面领取新优惠券。"},
    {"id": "faq_003", "category": "会员", "q": "会员有什么权益", "a": "会员权益：1. 专属折扣（最高9折）2. 免费配送 3. 优先客服 4. 生日礼包。"},
    {"id": "faq_004", "category": "会员", "q": "怎么开通会员", "a": "开通会员：进入「我的-会员中心」，选择套餐（月卡/季卡/年卡），完成支付即可。"},
    {"id": "faq_005", "category": "积分", "q": "积分怎么兑换", "a": "积分规则：1. 消费1元=1积分 2. 100积分=1元 3. 积分有效期1年 4. 在结算页勾选使用积分。"},
    {"id": "faq_006", "category": "物流", "q": "快递什么时候到", "a": "一般订单24小时内发货，3-5个工作日送达。偏远地区可能延长至7天。"},
    {"id": "faq_007", "category": "物流", "q": "怎么修改收货地址", "a": "修改地址：进入「我的-地址管理」，点击对应地址进行修改。订单发货前可修改。"},
    {"id": "faq_008", "category": "售后", "q": "退款多久到账", "a": "退款到账时间：1. 原路退回3-7个工作日 2. 余额即时到账 3. 银行卡5-10个工作日。"},
    {"id": "faq_009", "category": "售后", "q": "七天无理由退货", "a": "七天无理由退货：签收后7天内可申请，商品需保持原包装完好。生鲜、定制商品不支持。"},
    {"id": "faq_010", "category": "账户", "q": "忘记密码怎么办", "a": "找回密码：点击登录页「忘记密码」，通过手机号验证码重置密码。"},
]


class SimpleRAGService:
    """Simple keyword-based RAG for demo purposes."""

    def __init__(self, prompt_manager: PromptManager):
        self.prompt_manager = prompt_manager
        self.knowledge_base = FAQ_KNOWLEDGE_BASE

    async def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        """Retrieve relevant FAQ entries by keyword matching."""
        scored = []
        for item in self.knowledge_base:
            score = 0
            for char in query:
                if char in item["q"]:
                    score += 1
                if char in item["a"]:
                    score += 0.5
            for word in item["q"]:
                if word in query:
                    score += 2
            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for score, item in scored[:top_k] if score > 0]

    async def answer(
        self,
        user_input: str,
        context: DialogContext,
        llm_client: ResilientLLMClient,
    ) -> str:
        """Retrieve relevant docs and generate an answer via LLM."""
        docs = await self.retrieve(user_input)
        if not docs:
            return (
                "我暂时无法回答这个问题。\n\n"
                "您可以尝试：\n"
                "1. 换一种方式描述您的问题\n"
                "2. 回复「转人工」联系人工客服"
            )

        context_text = "\n\n".join(
            f"Q: {d['q']}\nA: {d['a']}" for d in docs
        )

        try:
            prompt = self.prompt_manager.render("rag_answer", {
                "context": context_text,
                "question": user_input,
            })
            reply = await llm_client.generate(prompt)
            return reply.strip()
        except Exception as e:
            print(f"[RAG] LLM generation failed, using direct answer: {e}")
            return docs[0]["a"]
