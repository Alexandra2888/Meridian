"""FastAPI entry. RFC §4.7, §9.2.

Endpoints:
- POST /chat            → SSE stream of orchestration events + synthesis tokens
- GET  /health          → fast liveness + CRM provider status (for the FE proxy)
- GET  /learner/{id}    → resolve a LearnerProfile via the active CRM client
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.api.sse import chat_event_stream
from app.clients.crm import get_crm_client
from app.config import get_settings
from app.db import ConversationRepo, session_scope
from app.db.session import dispose_db, init_db
from app.observability import configure_logging, get_logger
from app.schemas import (
    ChatRequest,
    ConversationDetail,
    ConversationSummary,
    ConversationTitleUpdate,
    LearnerProfile,
    LearnerSummary,
    MessageView,
)

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("app_started", crm_provider=get_settings().crm_provider)
    try:
        yield
    finally:
        await dispose_db()
        log.info("app_stopped")


app = FastAPI(
    title="Meridian — Learner Orchestration Layer",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    crm = get_crm_client()
    crm_ok = await crm.health()
    return {
        "status": "ok",
        "crm_provider": settings.crm_provider,
        "crm_healthy": crm_ok,
        "models": {
            "planner": settings.model_planner,
            "agent": settings.model_agent,
            "synthesizer": settings.model_synthesizer,
        },
    }


@app.get("/learners", response_model=list[LearnerSummary])
async def list_learners(limit: int = 25) -> list[LearnerSummary]:
    """Lightweight list backing the FE learner-picker. RFC §0.1."""

    crm = get_crm_client()
    return await crm.list_learners(limit=limit)


@app.get("/learner/{learner_id}", response_model=LearnerProfile)
async def get_learner(learner_id: str) -> LearnerProfile:
    crm = get_crm_client()
    profile = await crm.get_learner(learner_id)
    if profile.degraded and settings.crm_provider == "hubspot":
        # The CRM client never raises; surface the degraded state to the FE
        # so the context card can show a "couldn't load profile" affordance.
        raise HTTPException(status_code=503, detail="CRM lookup degraded")
    return profile


@app.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    learner_id: str, limit: int = 50
) -> list[ConversationSummary]:
    """Sidebar list — most-recently-updated first, per learner."""

    async with session_scope() as session:
        repo = ConversationRepo(session)
        rows = await repo.list_by_learner(learner_id, limit=limit)
        return [ConversationSummary.model_validate(r) for r in rows]


@app.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str) -> ConversationDetail:
    """Full conversation with ordered messages, for replaying into the chat view."""

    async with session_scope() as session:
        repo = ConversationRepo(session)
        row = await repo.get_with_messages(conversation_id)
        if row is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        return ConversationDetail(
            id=row.id,
            learner_id=row.learner_id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
            messages=[MessageView.model_validate(m) for m in row.messages],
        )


@app.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
async def update_conversation(
    conversation_id: str, body: ConversationTitleUpdate
) -> ConversationSummary:
    async with session_scope() as session:
        repo = ConversationRepo(session)
        row = await repo.update_title(conversation_id, body.title.strip())
        if row is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        return ConversationSummary.model_validate(row)


@app.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str) -> Response:
    async with session_scope() as session:
        repo = ConversationRepo(session)
        ok = await repo.delete(conversation_id)
        if not ok:
            raise HTTPException(status_code=404, detail="conversation not found")
    return Response(status_code=204)


@app.post("/chat")
async def chat(req: ChatRequest, request: Request) -> StreamingResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # disable nginx buffering on hosts that use it
    }
    return StreamingResponse(
        chat_event_stream(req),
        media_type="text/event-stream",
        headers=headers,
    )
