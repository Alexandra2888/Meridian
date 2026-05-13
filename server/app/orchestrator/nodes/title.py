"""Background AI title generation for a new conversation.

Runs once per conversation, after the first user/assistant pair is persisted.
Uses the cheap `agent` role (gpt-4o-mini, temp=0.2) — accuracy matters less
than latency/cost since the user can always rename it.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.clients.llm import get_llm
from app.db import ConversationRepo, session_scope
from app.observability import get_logger

log = get_logger(__name__)

_SYSTEM = (
    "You write short conversation titles for a sidebar. "
    "Output 4 to 7 words capturing the learner's core question. "
    "Plain text only — no quotes, no trailing period, no emoji."
)


def _clean(raw: str) -> str:
    title = raw.strip().strip('"').strip("'").rstrip(".").strip()
    # Hard cap at the column width.
    return title[:256] if title else ""


async def generate_and_save_title(
    conversation_id: str, user_message: str, assistant_message: str
) -> None:
    """Generate and persist a title. Never raises — logs failure silently."""

    try:
        llm = get_llm("agent")
        prompt = (
            f"LEARNER:\n{user_message.strip()}\n\n"
            f"MERIDIAN:\n{assistant_message.strip()[:1200]}\n\n"
            "TITLE:"
        )
        resp = await llm.ainvoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
        )
        content = resp.content if isinstance(resp.content, str) else ""
        title = _clean(content)
        if not title:
            log.warning("title_gen_empty", conversation_id=conversation_id)
            return

        async with session_scope() as session:
            repo = ConversationRepo(session)
            await repo.update_title(conversation_id, title)

        log.info("title_generated", conversation_id=conversation_id, title=title)

    except Exception as exc:  # noqa: BLE001 — best-effort background task
        log.warning(
            "title_gen_failed", conversation_id=conversation_id, error=str(exc)
        )
