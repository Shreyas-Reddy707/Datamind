"""DataMind v2 Chat Router.

Server-Sent Events (SSE) streaming for multi-tier conversational interactions,
persisting conversation history (capped at 500 messages per user/file), and
triggering autonomous pattern extraction workers.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.classifier import ChatClassifier
from app.agents.graph import build_agent_graph
from app.api.deps import get_authorized_user_file, get_current_user
from app.db.session import get_db
from app.engine.duckdb_manager import DuckDBManager
from app.engine.instant_responder import InstantResponder
from app.llm.client import llm_client
from app.memory.context_builder import ContextBuilder
from app.memory.feedback import FeedbackManager
from app.memory.query_cache import query_cache
from app.models.chat import ChatHistory
from app.models.file import UserFile
from app.models.user import User
from app.schemas.chat import (
    ChatMessageResponse,
    ChatStreamRequest,
    PatternFeedbackRequest,
)
from app.workers.tasks import extract_learned_patterns_task

logger = logging.getLogger("datamind.api.v1.chat")

router = APIRouter(prefix="/chat", tags=["Chat"])


def _format_sse(event: str, data: dict | str) -> str:
    """Format SSE chunk according to text/event-stream specification."""
    data_str = json.dumps(data) if isinstance(data, dict) else str(data)
    return f"event: {event}\ndata: {data_str}\n\n"


@router.post("/{file_id}/stream")
async def chat_stream_endpoint(
    file_id: uuid.UUID,
    request: ChatStreamRequest,
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
    db: AsyncSession = Depends(get_db),
):
    """
    Stream analytical intelligence responses via Server-Sent Events (SSE).
    Dynamically routes to Tier 1 (<25ms DuckDB), Tier 2 (<3s LLM), or Tier 3 (LangGraph).
    """
    start_time = time.perf_counter()
    gf = user_file.global_file
    schema_json = gf.schema_json or {}
    active_columns = list(schema_json.get("columns", {}).keys())

    # 1. Classify Query into Tier
    classification = ChatClassifier.classify(request.query, active_columns)
    tier = classification["tier"]
    intent = classification["intent"]

    # 2. Retrieve recent conversation history
    hist_stmt = (
        select(ChatHistory)
        .where(ChatHistory.user_file_id == user_file.id)
        .order_by(ChatHistory.created_at.desc())
        .limit(6)
    )
    hist_rows = (await db.scalars(hist_stmt)).all()
    recent_history = [
        {"role": h.role, "content": h.message_text}
        for h in reversed(hist_rows)
    ]

    async def event_generator() -> AsyncGenerator[str, None]:
        full_response_text = ""
        lab_artifact = None

        # A. Emit Tier Detection Event
        yield _format_sse("tier_detected", {"tier": tier, "intent": intent})

        # B. Route execution based on tier
        if tier == 1:
            yield _format_sse("agent_status", {"status": "Executing Tier 1 instant DuckDB computation...", "step": 1})
            cached = await query_cache.get(current_user.id, user_file.id, request.query)
            if cached:
                full_response_text = cached.get("text", "")
                yield _format_sse("token", full_response_text)
            else:
                instant_res = InstantResponder.execute(
                    request.query, gf.parquet_path, schema_json
                )
                full_response_text = instant_res["result"]
                yield _format_sse("token", full_response_text)
                await query_cache.set(
                    current_user.id,
                    user_file.id,
                    request.query,
                    {"text": full_response_text},
                    tier=1,
                )

        elif tier == 2:
            yield _format_sse("agent_status", {"status": "Retrieving context & generating quick briefing...", "step": 1})
            cached = await query_cache.get(current_user.id, user_file.id, request.query)
            if cached:
                full_response_text = cached.get("text", "")
                yield _format_sse("token", full_response_text)
            else:
                context = await ContextBuilder.build_tier2_context(
                    request.query, schema_json, recent_history, classification.get("target_columns")
                )
                messages = [
                    {"role": "system", "content": context},
                    {"role": "user", "content": request.query},
                ]
                async for chunk in llm_client.stream_chat_completion(messages, timeout=15):
                    full_response_text += chunk
                    yield _format_sse("token", chunk)

                await query_cache.set(
                    current_user.id,
                    user_file.id,
                    request.query,
                    {"text": full_response_text},
                    tier=2,
                )

        else:
            # Tier 3: Bounded LangGraph Multi-Agent Pipeline
            yield _format_sse("agent_status", {"status": "Initializing Bounded LangGraph Multi-Agent Brain...", "step": 1})

            agent_graph = build_agent_graph()
            initial_state = {
                "query": request.query,
                "user_id": str(current_user.id),
                "user_file_id": str(user_file.id),
                "parquet_path": gf.parquet_path,
                "schema_json": schema_json,
                "data_profile": DuckDBManager.generate_data_profile(gf.parquet_path),
                "recent_history": recent_history,
                "intent": intent,
                "target_columns": classification.get("target_columns", []),
                "current_step": 0,
                "max_steps": 8,
                "token_budget": 6000,
                "tokens_used": 0,
                "brief_response": "",
                "detailed_narrative": "",
                "lab_artifact": None,
                "firewall_passed": False,
                "firewall_feedback": None,
                "error": None,
            }

            final_state = await agent_graph.ainvoke(initial_state)

            brief = final_state.get("brief_response", "")
            detailed = final_state.get("detailed_narrative", "")
            lab_artifact = final_state.get("lab_artifact")

            full_response_text = f"{brief}\n\n{detailed}" if detailed else brief
            yield _format_sse("token", full_response_text)

            if lab_artifact:
                yield _format_sse("lab_artifact", lab_artifact)

        # C. Compute total latency
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # D. Persist User and Assistant Messages
        user_msg = ChatHistory(
            user_id=current_user.id,
            user_file_id=user_file.id,
            role="user",
            tier=tier,
            message_text=request.query,
            latency_ms=0,
        )
        asst_msg = ChatHistory(
            user_id=current_user.id,
            user_file_id=user_file.id,
            role="assistant",
            tier=tier,
            message_text=full_response_text,
            latency_ms=latency_ms,
            lab_artifact_json=lab_artifact,
        )
        db.add_all([user_msg, asst_msg])

        # Enforce cap of 500 messages per user/file
        count_stmt = select(func.count()).select_from(ChatHistory).where(ChatHistory.user_file_id == user_file.id)
        total_msgs = (await db.scalar(count_stmt)) or 0
        if total_msgs > 500:
            excess = total_msgs - 500 + 2
            oldest_ids = (
                await db.scalars(
                    select(ChatHistory.id)
                    .where(ChatHistory.user_file_id == user_file.id)
                    .order_by(ChatHistory.created_at.asc())
                    .limit(excess)
                )
            ).all()
            if oldest_ids:
                await db.execute(delete(ChatHistory).where(ChatHistory.id.in_(oldest_ids)))

        await db.commit()

        # E. Trigger Async Background Pattern Learning Worker
        try:
            await extract_learned_patterns_task.kiq(
                str(current_user.id),
                str(user_file.id),
                full_response_text,
                request.query,
            )
        except Exception as e:
            logger.debug("Taskiq background task scheduling skipped: %s", e)

        # F. Emit Done Event
        yield _format_sse(
            "done",
            {
                "status": "completed",
                "tier": tier,
                "latency_ms": latency_ms,
                "message_id": str(asst_msg.id),
            },
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{file_id}/history", response_model=list[ChatMessageResponse])
async def get_chat_history_endpoint(
    file_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve historical chat turns for the authorized user and dataset."""
    stmt = (
        select(ChatHistory)
        .where(
            ChatHistory.user_file_id == user_file.id,
            ChatHistory.user_id == current_user.id,
        )
        .order_by(ChatHistory.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.scalars(stmt)
    return list(result.all())


@router.post("/patterns/{pattern_id}/feedback")
async def pattern_feedback_endpoint(
    pattern_id: uuid.UUID,
    feedback: PatternFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit thumbs up/down rating on an autonomous pattern, adjusting its confidence score."""
    res = await FeedbackManager.record_pattern_vote(
        pattern_id=pattern_id,
        user_id=current_user.id,
        is_helpful=feedback.is_helpful,
        db=db,
    )
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pattern not found or access denied.",
        )
    return res
