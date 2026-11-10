"""DataMind v2 Chat Router.

Server-Sent Events (SSE) streaming for multi-tier conversational interactions,
persisting conversation history (capped at 500 messages per user/file), and
triggering autonomous pattern extraction workers.
"""

from __future__ import annotations

import asyncio
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
from app.models.prediction import PredictionHistory
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


def _build_customer_help_response(
    query: str,
    display_name: str,
    schema_json: dict,
    latest_pred: PredictionHistory | None,
) -> str:
    """Build a friendly, strictly customer-facing platform guide & dataset onboarding response."""
    q_low = query.lower().strip()
    cols = list((schema_json or {}).get("columns", {}).keys())
    row_count = (schema_json or {}).get("row_count", 0)
    col_sample = ", ".join(f"`{c}`" for c in cols[:6])

    model_note = ""
    if latest_pred and latest_pred.status == "completed" and latest_pred.target_column:
        model_note = (
            f"\n\n**Active AutoML Benchmark on `{display_name}`**: "
            f"Predicting **`{latest_pred.target_column}`** ({latest_pred.task_type}) "
            f"with **{latest_pred.best_model_name or 'best model'}**."
        )

    if any(k in q_low for k in ["automl", "auto ml", "feature weight", "what-if", "simulator", "predict"]):
        return (
            f"### How Predictive AutoML Lab Works on `{display_name}`\n\n"
            "1. **Leakage Quarantine & Data Readiness**: Scans all columns and blocks post-outcome columns that would distort predictions.\n"
            "2. **Multi-Model Cross-Validation**: Automatically benchmarks algorithms (such as Random Forest, Gradient Boosting, Logistic Regression, or Ridge) and ranks them on the Model Benchmark Leaderboard.\n"
            "3. **Feature Weights & Driver Impact Chart**: Ranks which columns drive the predicted target most strongly and plots the top drivers.\n"
            "4. **What-If Outcome Simulator**: Lets you adjust sliders and category dropdowns for top drivers to test real scenarios and see how each factor pushes the predicted outcome up or down."
            f"{model_note}\n\n"
            "Open the **Predictive AutoML Lab** tab and click **Train Models** (or adjust the **What-If Simulator** sliders) to explore scenarios!"
        )

    if any(k in q_low for k in ["forensic", "chart", "plot", "sql"]):
        sql_example = "`SELECT * FROM dataset LIMIT 20`"
        return (
            f"### Exploring `{display_name}` ({row_count:,} rows × {len(cols)} columns)\n\n"
            "- **Forensic Analytics Lab**: Combines automated integrity findings (*Context → Finding → Evidence → Implication*) with an embedded **Interactive Plotly Studio** (2D charts & 3D WebGL). Click any finding card to visualize its columns.\n"
            f"- **DuckDB SQL Sandbox**: Run fast read-only SQL queries directly against `dataset` (e.g. {sql_example}).\n"
            "- **Predictive AutoML Lab**: Train predictive models, inspect driver weights, and test scenarios in the **What-If Simulator**."
        )

    return (
        f"Hello! I'm your **DataMind Analytical Partner** for **`{display_name}`** "
        f"({row_count:,} rows × {len(cols)} columns).\n\n"
        f"**Key columns detected**: {col_sample}\n\n"
        "Here are a few ways I can help right now:\n"
        "- **Ask about your data**: *\"How many rows are there?\"* or *\"How do lead_time and deposit_type affect is_canceled?\"*\n"
        "- **Explore drivers & predictions**: Open **Predictive AutoML Lab** to benchmark models and test scenarios in the **What-If Simulator**.\n"
        "- **Visual evidence**: Open **Forensic Analytics Lab** to click findings and update the embedded Plotly Studio."
        f"{model_note}"
    )


def _build_data_aware_fallback(
    query: str,
    parquet_path: str,
    schema_json: dict,
    target_columns: list[str],
    latest_pred: PredictionHistory | None,
) -> str:
    """Synthesize fast, verified dataset statistics via DuckDB when local LLM is offline."""
    import duckdb

    cols_meta = (schema_json or {}).get("columns", {})
    valid_cols = list(cols_meta.keys())
    q_low = query.lower()

    # Extract any schema columns referenced in query
    mentioned = [c for c in valid_cols if c.lower() in q_low]
    for tc in target_columns:
        if tc in valid_cols and tc not in mentioned:
            mentioned.append(tc)

    # Identify likely outcome column (from latest completed model or common target suffix or last mentioned)
    outcome_col = None
    if latest_pred and latest_pred.target_column in valid_cols and latest_pred.target_column in mentioned:
        outcome_col = latest_pred.target_column
    elif len(mentioned) >= 2:
        outcome_col = mentioned[-1]
    elif latest_pred and latest_pred.target_column in valid_cols:
        outcome_col = latest_pred.target_column

    drivers = [c for c in mentioned if c != outcome_col][:3]
    if not drivers and mentioned:
        drivers = mentioned[:3]
    if not drivers:
        drivers = valid_cols[:3]

    sections: list[str] = []
    conn = duckdb.connect(database=":memory:", read_only=False)
    try:
        conn.execute("SET memory_limit = '256MB'; SET threads = 2;")
        conn.execute("CREATE TABLE dataset AS SELECT * FROM read_parquet(?)", [parquet_path.replace("\\", "/")])
        conn.execute("SET enable_external_access = false;")

        if outcome_col and drivers:
            esc_y = f'"{outcome_col.replace(chr(34), chr(34) * 2)}"'
            y_type = str(cols_meta.get(outcome_col, {}).get("dtype", "")).lower()
            y_is_num = any(t in y_type for t in ["int", "float", "double", "decimal", "numeric"])

            sections.append(f"### Empirical Impact on `{outcome_col}`")
            for drv in drivers:
                esc_x = f'"{drv.replace(chr(34), chr(34) * 2)}"'
                x_type = str(cols_meta.get(drv, {}).get("dtype", "")).lower()
                x_is_num = any(t in x_type for t in ["int", "float", "double", "decimal", "numeric"])

                if x_is_num and y_is_num:
                    row = conn.execute(
                        f"SELECT corr({esc_x}, {esc_y}), avg({esc_x}), min({esc_x}), max({esc_x}) FROM dataset WHERE {esc_x} IS NOT NULL AND {esc_y} IS NOT NULL"  # noqa: S608
                    ).fetchone()
                    corr_val = round(float(row[0]), 3) if row and row[0] is not None else 0.0
                    avg_val = round(float(row[1]), 2) if row and row[1] is not None else 0.0
                    direction = "positively associated with higher" if corr_val > 0.03 else ("negatively associated with" if corr_val < -0.03 else "weakly correlated with")
                    # Also compare high vs low outcome groups if outcome has low cardinality
                    distinct_y = conn.execute(f"SELECT count(DISTINCT {esc_y}) FROM dataset").fetchone()[0]  # noqa: S608
                    group_note = ""
                    if 2 <= distinct_y <= 5:
                        grp_rows = conn.execute(
                            f"SELECT {esc_y}, round(avg({esc_x}), 2) FROM dataset WHERE {esc_y} IS NOT NULL GROUP BY {esc_y} ORDER BY {esc_y} LIMIT 5"  # noqa: S608
                        ).fetchall()
                        grp_str = ", ".join(f"`{outcome_col}={g[0]}` -> avg **{g[1]}**" for g in grp_rows)
                        group_note = f" ({grp_str})"
                    sections.append(
                        f"- **`{drv}`**: Correlation with `{outcome_col}` is **{corr_val:+.3f}** ({direction} `{outcome_col}`; overall mean={avg_val}){group_note}."
                    )
                elif y_is_num:
                    grp_rows = conn.execute(
                        f"SELECT CAST({esc_x} AS VARCHAR) AS cat, count(*) AS cnt, round(avg({esc_y}), 4) AS avg_y FROM dataset WHERE {esc_x} IS NOT NULL GROUP BY 1 ORDER BY cnt DESC LIMIT 5"  # noqa: S608
                    ).fetchall()
                    breakdown = "; ".join(f"**{r[0]}**: avg `{outcome_col}`={r[2]} ({r[1]:,} rows)" for r in grp_rows)
                    sections.append(f"- **`{drv}`**: {breakdown}")
                else:
                    cnt = conn.execute(f"SELECT count(DISTINCT {esc_x}) FROM dataset").fetchone()[0]  # noqa: S608
                    sections.append(f"- **`{drv}`**: {cnt:,} distinct values in dataset.")
        else:
            row_cnt = conn.execute("SELECT count(*) FROM dataset").fetchone()[0]
            sections.append(f"### Dataset Analysis Summary ({row_cnt:,} rows × {len(valid_cols)} columns)")
            for col in drivers:
                esc_c = f'"{col.replace(chr(34), chr(34) * 2)}"'
                c_type = str(cols_meta.get(col, {}).get("dtype", "")).lower()
                if any(t in c_type for t in ["int", "float", "double", "decimal", "numeric"]):
                    st = conn.execute(
                        f"SELECT round(min({esc_c}), 2), round(avg({esc_c}), 2), round(max({esc_c}), 2) FROM dataset"  # noqa: S608
                    ).fetchone()
                    sections.append(f"- **`{col}`**: min={st[0]}, mean={st[1]}, max={st[2]}")
                else:
                    top_vals = conn.execute(
                        f"SELECT CAST({esc_c} AS VARCHAR), count(*) FROM dataset GROUP BY 1 ORDER BY 2 DESC LIMIT 3"  # noqa: S608
                    ).fetchall()
                    top_s = ", ".join(f"{r[0]} ({r[1]:,})" for r in top_vals)
                    sections.append(f"- **`{col}`**: Top values -> {top_s}")
    except Exception as exc:
        logger.debug("Fallback DuckDB stats skipped: %s", exc)
        sections.append(
            f"Verified dataset columns: {', '.join(f'`{c}`' for c in drivers[:5])}."
        )
    finally:
        conn.close()

    if latest_pred and latest_pred.status == "completed" and isinstance(latest_pred.feature_importance_json, dict):
        top_w = list(latest_pred.feature_importance_json.items())[:4]
        if top_w:
            w_str = ", ".join(f"`{k}` ({round(float(v) * 100, 1)}%)" for k, v in top_w)
            sections.append(
                f"\n**AutoML Feature Importance (`{latest_pred.best_model_name}` predicting `{latest_pred.target_column}`)**: {w_str}."
            )

    return "\n".join(sections)


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

    latest_pred_stmt = (
        select(PredictionHistory)
        .where(
            PredictionHistory.user_file_id == user_file.id,
            PredictionHistory.user_id == current_user.id,
            PredictionHistory.status == "completed",
        )
        .order_by(PredictionHistory.created_at.desc())
        .limit(1)
    )
    latest_pred = await db.scalar(latest_pred_stmt)

    async def event_generator() -> AsyncGenerator[str, None]:
        full_response_text = ""
        lab_artifact = None

        # A. Emit Tier Detection Event
        yield _format_sse("tier_detected", {"tier": tier, "intent": intent})

        # B. Route execution based on tier & intent
        if intent == "help":
            yield _format_sse("agent_status", {"status": "Preparing DataMind guide...", "step": 1})
            full_response_text = _build_customer_help_response(
                request.query,
                user_file.display_name,
                schema_json,
                latest_pred,
            )
            yield _format_sse("token", full_response_text)

        elif tier == 1:
            yield _format_sse("agent_status", {"status": "Executing Tier 1 instant DuckDB computation...", "step": 1})
            cached = await query_cache.get(current_user.id, user_file.id, request.query)
            if cached and cached.get("text"):
                full_response_text = cached.get("text", "")
                yield _format_sse("token", full_response_text)
            else:
                instant_res = await asyncio.to_thread(
                    InstantResponder.execute, request.query, gf.parquet_path, schema_json
                )
                full_response_text = instant_res["result"]
                if not full_response_text.strip():
                    full_response_text = await asyncio.to_thread(
                        _build_data_aware_fallback,
                        request.query,
                        gf.parquet_path,
                        schema_json,
                        classification.get("target_columns", []),
                        latest_pred,
                    )
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
            if cached and cached.get("text"):
                full_response_text = cached.get("text", "")
                yield _format_sse("token", full_response_text)
            else:
                if not llm_client.is_chat_circuit_open():
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

                if not full_response_text.strip():
                    full_response_text = await asyncio.to_thread(
                        _build_data_aware_fallback,
                        request.query,
                        gf.parquet_path,
                        schema_json,
                        classification.get("target_columns", []),
                        latest_pred,
                    )
                    yield _format_sse("token", full_response_text)

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
            data_profile = await asyncio.to_thread(DuckDBManager.generate_data_profile, gf.parquet_path)
            initial_state = {
                "query": request.query,
                "user_id": str(current_user.id),
                "user_file_id": str(user_file.id),
                "parquet_path": gf.parquet_path,
                "schema_json": schema_json,
                "data_profile": data_profile,
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

            brief = final_state.get("brief_response", "").strip()
            detailed = final_state.get("detailed_narrative", "").strip()
            lab_artifact = final_state.get("lab_artifact")

            full_response_text = f"{brief}\n\n{detailed}" if detailed and brief else (detailed or brief)
            if not full_response_text.strip():
                full_response_text = await asyncio.to_thread(
                    _build_data_aware_fallback,
                    request.query,
                    gf.parquet_path,
                    schema_json,
                    classification.get("target_columns", []),
                    latest_pred,
                )
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
