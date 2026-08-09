"""Test suite for the customer service agent.

Run with: python -m pytest tests/ -v
Or: python tests/run_tests.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_rule_router():
    """Test L1 rule router."""
    from src.routing.rule_router import RuleRouter
    router = RuleRouter()

    result = await router.route("我要退款")
    assert result is not None and result.intent == "refund", f"Expected refund, got {result}"

    result = await router.route("查一下我的物流")
    assert result is not None and result.intent == "query_order", f"Expected query_order, got {result}"

    result = await router.route("转人工")
    assert result is not None and result.intent == "human", f"Expected human, got {result}"

    result = await router.route("今天天气真好")
    assert result is None, f"Expected None, got {result}"

    print("[PASS] test_rule_router")


async def test_vector_router():
    """Test L2 vector router (mock mode)."""
    from src.routing.vector_router import VectorRouter
    router = VectorRouter(embedding_adapter=None)

    result = await router.route("我的快递到哪了")
    assert result is not None, "Expected a result"
    assert result.level == "L2", f"Expected L2, got {result.level}"

    print(f"[PASS] test_vector_router (intent={result.intent}, conf={result.confidence:.2f})")


async def test_cascade_router():
    """Test cascade router with L1 + L2 (no LLM)."""
    from src.routing.cascade import CascadeRouter
    from src.routing.vector_router import VectorRouter

    vr = VectorRouter(embedding_adapter=None)
    router = CascadeRouter(vector_router=vr, llm_router=None)

    # L1 should catch this
    result = await router.route("我要退款")
    assert result.level == "L1", f"Expected L1, got {result.level}"
    assert result.intent == "refund"

    # L2 should handle this
    result = await router.route("我的快递到哪了")
    assert result.level in ("L1", "L2"), f"Expected L1/L2, got {result.level}"

    # Default fallback
    result = await router.route("asdfghjkl")
    assert result.level in ("L2", "default"), f"Expected L2/default, got {result.level}"

    print("[PASS] test_cascade_router")


async def test_circuit_breaker():
    """Test circuit breaker state transitions."""
    from src.resilience.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState, CircuitOpenError

    config = CircuitConfig(failure_threshold=3, recovery_timeout=0.5, min_requests=10)
    cb = CircuitBreaker("test", config)

    async def failing_func():
        raise ValueError("fail")

    # Trigger failures
    for i in range(3):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass

    assert cb.state == CircuitState.OPEN, f"Expected OPEN, got {cb.state}"

    # Should reject immediately
    try:
        await cb.call(failing_func)
        assert False, "Should have raised CircuitOpenError"
    except CircuitOpenError:
        pass

    # Wait for recovery
    await asyncio.sleep(0.6)

    async def success_func():
        return "ok"

    # Half-open -> success -> closed
    result = await cb.call(success_func)
    assert result == "ok"
    assert cb.state == CircuitState.CLOSED, f"Expected CLOSED, got {cb.state}"

    print("[PASS] test_circuit_breaker")


async def test_retry():
    """Test retry policy."""
    from src.resilience.retry import RetryPolicy, RetryConfig

    config = RetryConfig(max_retries=2, base_delay=0.1, jitter=False)
    retry = RetryPolicy(config)

    call_count = 0

    async def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("flaky")
        return "success"

    result = await retry.execute(flaky_func)
    assert result == "success"
    assert call_count == 3, f"Expected 3 calls, got {call_count}"

    print("[PASS] test_retry")


async def test_dialog_context():
    """Test dialog context and slot management."""
    from src.dialog.context import DialogContext, DialogState, SlotDefinition, INTENT_SLOTS_MAP

    ctx = DialogContext(session_id="test")
    ctx.intent = "refund"
    ctx.slot_definitions = INTENT_SLOTS_MAP["refund"]

    # Initially both slots missing
    missing = ctx.missing_slots()
    assert len(missing) == 2, f"Expected 2 missing, got {len(missing)}"

    # Fill one slot
    ctx.slots["order_id"] = "DD001"
    missing = ctx.missing_slots()
    assert len(missing) == 1, f"Expected 1 missing, got {len(missing)}"
    assert missing[0].name == "reason"

    # Fill remaining
    ctx.slots["reason"] = "broken"
    assert len(ctx.missing_slots()) == 0

    print("[PASS] test_dialog_context")


async def test_prompt_manager():
    """Test prompt template loading and rendering."""
    from src.prompts.manager import PromptManager

    pm = PromptManager("prompts")

    template = pm.load("slot_extraction")
    assert "{intent}" in template
    assert "{user_input}" in template

    rendered = pm.render("slot_extraction", {
        "intent": "refund",
        "slot_descriptions": "- order_id: 订单编号",
        "user_input": "我要退款",
        "existing_slots": "{}",
    })
    assert "refund" in rendered
    assert "我要退款" in rendered

    print("[PASS] test_prompt_manager")


async def test_mock_adapter():
    """Test mock adapter works without API keys."""
    from src.models.adapter import MockAdapter, ModelConfig

    adapter = MockAdapter(ModelConfig(provider="mock"))
    result = await adapter.generate("test")
    assert isinstance(result, str)
    assert len(result) > 0

    structured = await adapter.structured_call("classify intent")
    assert isinstance(structured, dict)

    print("[PASS] test_mock_adapter")


async def test_full_dialog_flow():
    """Test complete multi-turn dialog with mock LLM."""
    from src.config import AppConfig
    from src.models.adapter import ModelFactory, MockAdapter, ModelConfig
    from src.prompts.manager import PromptManager
    from src.resilience.client import ResilientLLMClient
    from src.routing.cascade import CascadeRouter
    from src.routing.vector_router import VectorRouter
    from src.routing.llm_router import LLMRouter
    from src.dialog.context import DialogContext
    from src.dialog.manager import DialogManager
    from src.rag.service import SimpleRAGService

    prompt_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")
    pm = PromptManager(prompt_dir)

    mock_adapter = MockAdapter(ModelConfig(provider="mock"))
    llm_client = ResilientLLMClient(primary_adapter=mock_adapter)

    vr = VectorRouter(embedding_adapter=None)
    lr = LLMRouter(llm_client, pm)
    router = CascadeRouter(vector_router=vr, llm_router=lr)

    rag = SimpleRAGService(pm)
    dm = DialogManager(router=router, llm_client=llm_client, prompt_manager=pm, rag_service=rag)

    # Turn 1: User says "我要退款"
    ctx = DialogContext(session_id="test_flow")
    reply1 = await dm.handle_message("我要退款", ctx)
    assert "退款" in reply1 or "订单" in reply1, f"Unexpected reply: {reply1}"
    print(f"  Turn 1 reply: {reply1[:60]}...")

    # Turn 2: User provides order info
    reply2 = await dm.handle_message("订单号DD001，商品损坏", ctx)
    assert "DD001" in reply2 or "退款" in reply2, f"Unexpected reply: {reply2}"
    print(f"  Turn 2 reply: {reply2[:60]}...")

    print("[PASS] test_full_dialog_flow")


async def main():
    print("=" * 60)
    print("Customer Service Agent - Test Suite")
    print("=" * 60)
    print()

    await test_mock_adapter()
    await test_prompt_manager()
    await test_rule_router()
    await test_vector_router()
    await test_cascade_router()
    await test_circuit_breaker()
    await test_retry()
    await test_dialog_context()
    await test_full_dialog_flow()

    print()
    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
