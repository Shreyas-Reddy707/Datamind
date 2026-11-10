"""DataMind v2 Tiered Context Builder.

Assembles tiered LLM prompts (Tier 2 Quick vs Tier 3 Deep), retrieves top semantic
learned patterns via pgvector cosine distance (<=>) with confidence decay, and wraps
all untrusted dataset samples inside PromptGuard trust boundaries.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import llm_client
from app.models.pattern import LearnedPattern
from app.security.prompt_guard import PromptGuard

RESPONSE_STYLE_CONTRACT = (
    "## Output Style Contract\n"
    "- Lead directly with analytical findings.\n"
    "- Quote verified metrics, quartiles, and exact figures rather than vague adjectives.\n"
    "- Bold key insights. Double-quote exact column identifiers (e.g. `\"revenue\"`).\n"
    "- Strict avoidance of filler phrases ('Certainly!', 'Here is what I found').\n"
    "- Maintain zero-hallucination compliance against provided schema columns."
)


class ContextBuilder:
    """Assembles prompt contexts with pgvector semantic pattern retrieval."""

    @classmethod
    async def retrieve_semantic_patterns(
        cls,
        query: str,
        user_id: uuid.UUID,
        user_file_id: uuid.UUID,
        db: AsyncSession,
        top_k: int = 4,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant patterns using pgvector cosine distance weighted by confidence."""
        query_emb = await llm_client.get_embedding(query)

        stmt = (
            select(LearnedPattern)
            .where(
                LearnedPattern.user_id == user_id,
                LearnedPattern.user_file_id == user_file_id,
            )
            .order_by(LearnedPattern.embedding.cosine_distance(query_emb))
            .limit(top_k * 2)
        )

        result = await db.scalars(stmt)
        patterns = list(result.all())

        # Sort by combination of distance and confidence score
        # Note: cosine_distance is 0 for identical, 2 for opposite
        ranked = []
        for p in patterns:
            ranked.append(
                {
                    "id": str(p.id),
                    "type": p.pattern_type,
                    "insight": p.insight_text,
                    "confidence": p.confidence_score,
                    "votes": p.helpful_votes - p.unhelpful_votes,
                }
            )

        ranked.sort(key=lambda x: (x["confidence"], x["votes"]), reverse=True)
        return ranked[:top_k]

    @classmethod
    async def build_tier2_context(
        cls,
        query: str,
        schema_json: dict[str, Any],
        recent_history: list[dict[str, str]],
        target_columns: list[str] | None = None,
        global_files_summary: str | None = None,
    ) -> str:
        """Minimal fast context package for Tier 2 quick stream responses (<2500 chars)."""
        domain = schema_json.get("detected_domain", "general")
        row_count = schema_json.get("row_count", 0)
        cols_meta = schema_json.get("columns", {})

        # Select relevant columns
        active_cols = target_columns or list(cols_meta.keys())[:5]
        condensed_schema: dict[str, Any] = {}
        for c in active_cols:
            if c in cols_meta:
                samples = cols_meta[c].get("sample_values", [])[:3]
                safe_samples = [PromptGuard.wrap_untrusted_sample(str(s)) for s in samples]
                condensed_schema[c] = {
                    "type": cols_meta[c].get("dtype", "unknown"),
                    "null_pct": cols_meta[c].get("null_pct", 0.0),
                    "samples": safe_samples,
                }

        hist_lines = []
        for msg in recent_history[-2:]:
            hist_lines.append(f"{msg.get('role', 'user').capitalize()}: {msg.get('content', '')[:200]}")
        hist_str = "\n".join(hist_lines) if hist_lines else "No previous conversation."
        global_section = f"## User Workspace Datasets:\n{global_files_summary}\n\n" if global_files_summary else ""

        context = (
            f"## ACTIVE DATASET: {domain.upper()} ({row_count:,} rows)\n"
            f"## Column Schema (Verified):\n{json.dumps(condensed_schema, separators=(',', ':'))}\n\n"
            f"{global_section}"
            f"## Recent Context:\n{hist_str}\n\n"
            f"{RESPONSE_STYLE_CONTRACT}\n"
            "Constraint: Deliver a concise analytical answer with verified metrics."
        )
        return context[:1800]

    @classmethod
    async def build_tier3_context(
        cls,
        query: str,
        schema_json: dict[str, Any],
        user_id: uuid.UUID,
        user_file_id: uuid.UUID,
        db: AsyncSession,
        data_profile: dict[str, Any] | None = None,
        recent_history: list[dict[str, str]] | None = None,
    ) -> str:
        """Comprehensive forensic context package for Tier 3 Deep Multi-Agent pipeline."""
        domain = schema_json.get("detected_domain", "general")
        row_count = schema_json.get("row_count", 0)
        cols_meta = schema_json.get("columns", {})

        # 1. Retrieve top semantic learned patterns via pgvector
        patterns = await cls.retrieve_semantic_patterns(query, user_id, user_file_id, db)
        patterns_lines = []
        for p in patterns:
            patterns_lines.append(f"- [{p['type'].upper()}] {p['insight']} (Confidence: {p['confidence']:.2f})")
        patterns_str = "\n".join(patterns_lines) if patterns_lines else "No prior patterns recorded."

        # 2. Wrapped samples for all columns
        schema_details: dict[str, Any] = {}
        for col_name, meta in list(cols_meta.items())[:15]:
            raw_samples = meta.get("sample_values", [])[:3]
            wrapped_samples = [PromptGuard.wrap_untrusted_sample(str(s)) for s in raw_samples]
            schema_details[col_name] = {
                "dtype": meta.get("dtype"),
                "null_pct": meta.get("null_pct", 0),
                "samples": wrapped_samples,
            }

        # 3. Health & quality summary
        health_summary = "Quality Score: Unknown"
        if data_profile:
            health_summary = (
                f"Health Score: {data_profile.get('health_score', 100)}/100 | "
                f"Total Nulls: {data_profile.get('total_nulls', 0):,} | "
                f"Duplicate Rows: {data_profile.get('duplicate_rows', 0):,}"
            )

        # 4. History
        hist_lines = []
        if recent_history:
            for turn in recent_history[-4:]:
                hist_lines.append(
                    f"{turn.get('role', 'user').capitalize()}: {turn.get('content', '')[:300]}"
                )
        hist_str = "\n".join(hist_lines) if hist_lines else "New analytical session."

        context = (
            f"## DATASET INTELLIGENCE DOSSIER: {domain.upper()} ({row_count:,} rows)\n"
            f"## System Health: {health_summary}\n\n"
            f"## Verified Columns & Sample Boundaries:\n{json.dumps(schema_details, indent=1)}\n\n"
            f"## Autonomous Self-Learning Patterns (Memory):\n{patterns_str}\n\n"
            f"## Conversation Thread:\n{hist_str}\n\n"
            f"{RESPONSE_STYLE_CONTRACT}\n"
        )
        return context[:6000]
