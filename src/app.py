"""FastAPI application - main entry point.

Wires together all four layers (D6 -> D4 -> D2 -> D1) and exposes
HTTP endpoints for the customer service agent.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.config import AppConfig
from src.models.adapter import ModelFactory
from src.prompts.manager import PromptManager
from src.resilience.client import ResilientLLMClient
from src.routing.cascade import CascadeRouter
from src.routing.vector_router import VectorRouter
from src.routing.llm_router import LLMRouter
from src.dialog.context import DialogContext
from src.dialog.manager import DialogManager
from src.rag.service import SimpleRAGService


# --- Application state ---
class AppState:
    config: AppConfig = None
    llm_client: ResilientLLMClient = None
    prompt_manager: PromptManager = None
    dialog_manager: DialogManager = None
    contexts: dict[str, DialogContext] = {}


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all services on startup."""
    state.config = AppConfig.load()
    state.prompt_manager = PromptManager(state.config.prompt_dir)

    # D6: Create model adapters
    primary_adapter = ModelFactory.create_from_config(state.config.model_config_dict)
    fallback_adapters = [
        ModelFactory.create_from_config(fc)
        for fc in state.config.fallback_model_configs
    ]

    # D4: Wrap with resilient client
    state.llm_client = ResilientLLMClient(
        primary_adapter=primary_adapter,
        fallback_adapters=fallback_adapters,
        circuit_config=state.config.circuit_config,
        retry_config=state.config.retry_config,
    )

    # D2: Create cascade router
    embedding_adapter = ModelFactory.create_from_config(state.config.embedding_config_dict)
    vector_router = VectorRouter(embedding_adapter if embedding_adapter.config.api_key else None)
    llm_router = LLMRouter(state.llm_client, state.prompt_manager)
    cascade_router = CascadeRouter(vector_router=vector_router, llm_router=llm_router)

    # RAG service
    rag_service = SimpleRAGService(state.prompt_manager)

    # D1: Create dialog manager
    state.dialog_manager = DialogManager(
        router=cascade_router,
        llm_client=state.llm_client,
        prompt_manager=state.prompt_manager,
        rag_service=rag_service,
    )

    print(f"[App] Started. Provider: {primary_adapter.config.provider}")
    print(f"[App] Fallbacks: {[a.config.provider for a in fallback_adapters]}")
    print(f"[App] Prompts dir: {state.config.prompt_dir}")
    yield
    print("[App] Shutdown.")


app = FastAPI(title="Customer Service Agent", lifespan=lifespan)


# --- Request/Response models ---
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    intent: str | None = None
    state: str = ""
    turn: int = 0


# --- Endpoints ---
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Synchronous chat endpoint."""
    ctx = state.contexts.get(req.session_id)
    if ctx is None:
        ctx = DialogContext(session_id=req.session_id)
        state.contexts[req.session_id] = ctx

    reply = await state.dialog_manager.handle_message(req.message, ctx)

    return ChatResponse(
        reply=reply,
        session_id=req.session_id,
        intent=ctx.intent,
        state=ctx.state.value,
        turn=ctx.turn_count,
    )


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming chat endpoint (SSE)."""
    ctx = state.contexts.get(req.session_id)
    if ctx is None:
        ctx = DialogContext(session_id=req.session_id)
        state.contexts[req.session_id] = ctx

    async def event_generator() -> AsyncIterator[str]:
        reply = await state.dialog_manager.handle_message(req.message, ctx)
        # Simulate streaming by chunking the reply
        chunk_size = 10
        for i in range(0, len(reply), chunk_size):
            chunk = reply[i:i+chunk_size]
            yield f"data: {json.dumps({'token': chunk})}\n\n"
            await asyncio.sleep(0.05)
        yield f"data: {json.dumps({'done': True, 'intent': ctx.intent, 'state': ctx.state.value})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/session/reset")
async def reset_session(req: ChatRequest):
    """Reset a dialog session."""
    if req.session_id in state.contexts:
        del state.contexts[req.session_id]
    return {"status": "ok", "session_id": req.session_id}


@app.get("/health")
async def health():
    """Health check with circuit breaker status."""
    return {
        "status": "ok",
        "providers": state.llm_client.get_status() if state.llm_client else [],
    }


@app.get("/")
async def root():
    """API info."""
    return {
        "name": "Customer Service Agent",
        "version": "1.0.0",
        "endpoints": {
            "chat": "POST /chat",
            "stream": "POST /chat/stream",
            "reset": "POST /session/reset",
            "health": "GET /health",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
