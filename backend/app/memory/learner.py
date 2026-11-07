"""DataMind v2 Autonomous Pattern Learner.

Discovers statistical patterns (correlations |r| > 0.7, outliers > 3σ) and extracts
1-sentence narrative insights, persisting them in learned_patterns with Vector(768).
"""

from __future__ import annotations

import logging
import uuid

import duckdb
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import llm_client
from app.models.pattern import LearnedPattern

logger = logging.getLogger("datamind.memory.learner")


def escape_identifier(ident: str) -> str:
    """Strict double-quoting for SQL identifiers with internal quotes escaped."""
    escaped = ident.replace('"', '""')
    return f'"{escaped}"'


class PatternLearner:
    """Extracts and persists statistical and semantic insights with Vector(768) embeddings."""

    @classmethod
    async def extract_statistical_patterns(
        cls,
        parquet_path: str,
        user_id: uuid.UUID,
        user_file_id: uuid.UUID,
        db: AsyncSession,
    ) -> list[LearnedPattern]:
        """Discovers correlation (|r| > 0.7) and outlier (> 3σ) patterns from Parquet storage."""
        norm_path = parquet_path.replace("\\", "/")
        conn = duckdb.connect(database=":memory:", read_only=False)
        patterns_created: list[LearnedPattern] = []

        try:
            conn.execute("SET memory_limit = '512MB'; SET threads = 2;")
            conn.execute("CREATE TABLE dataset AS SELECT * FROM read_parquet(?)", [norm_path])
            conn.execute("SET enable_external_access = false;")

            col_info = conn.execute("DESCRIBE dataset").fetchall()
            numeric_cols: list[str] = []
            for col_name, col_type, *_ in col_info:
                col_type_str = str(col_type).upper()
                if any(t in col_type_str for t in ["INT", "DOUBLE", "FLOAT", "DECIMAL", "HUGEINT"]):
                    numeric_cols.append(col_name)

            # 1. Pearson Correlations (|r| > 0.7)
            if len(numeric_cols) >= 2:
                for i in range(len(numeric_cols)):
                    for j in range(i + 1, len(numeric_cols)):
                        c1, c2 = numeric_cols[i], numeric_cols[j]
                        esc_c1 = escape_identifier(c1)
                        esc_c2 = escape_identifier(c2)
                        corr_val = conn.execute(
                            f"SELECT corr({esc_c1}, {esc_c2}) FROM dataset"  # noqa: S608
                        ).fetchone()[0]

                        if corr_val is not None and abs(corr_val) >= 0.70:
                            insight = (
                                f"Strong correlation between '{c1}' and '{c2}' "
                                f"(r = {corr_val:.2f})."
                            )
                            # Check if pattern already exists
                            existing = await db.scalar(
                                select(LearnedPattern).where(
                                    LearnedPattern.user_id == user_id,
                                    LearnedPattern.user_file_id == user_file_id,
                                    LearnedPattern.insight_text == insight,
                                )
                            )
                            if not existing:
                                emb = await llm_client.get_embedding(insight)
                                pattern = LearnedPattern(
                                    user_id=user_id,
                                    user_file_id=user_file_id,
                                    pattern_type="correlation",
                                    insight_text=insight,
                                    stat_metadata={"col1": c1, "col2": c2, "r": round(float(corr_val), 4)},
                                    embedding=emb,
                                    confidence_score=round(min(0.99, abs(corr_val)), 2),
                                )
                                db.add(pattern)
                                patterns_created.append(pattern)

            # 2. Outliers (Z-score > 3σ)
            for c in numeric_cols:
                esc_c = escape_identifier(c)
                stats = conn.execute(
                    f"SELECT avg({esc_c}), stddev({esc_c}), count({esc_c}) FROM dataset"  # noqa: S608
                ).fetchone()

                avg_val, std_val, count_val = stats
                if avg_val is not None and std_val is not None and std_val > 0 and count_val > 20:
                    upper_bound = avg_val + 3 * std_val
                    lower_bound = avg_val - 3 * std_val
                    outlier_count = conn.execute(
                        f"SELECT count(*) FROM dataset WHERE {esc_c} > {upper_bound} OR {esc_c} < {lower_bound}"  # noqa: S608
                    ).fetchone()[0]

                    if outlier_count > 0 and (outlier_count / count_val) < 0.05:
                        insight = (
                            f"Volumetric outliers detected in '{c}': "
                            f"{outlier_count} observations exceed 3σ deviation."
                        )
                        existing = await db.scalar(
                            select(LearnedPattern).where(
                                LearnedPattern.user_id == user_id,
                                LearnedPattern.user_file_id == user_file_id,
                                LearnedPattern.insight_text == insight,
                            )
                        )
                        if not existing:
                            emb = await llm_client.get_embedding(insight)
                            pattern = LearnedPattern(
                                user_id=user_id,
                                user_file_id=user_file_id,
                                pattern_type="outlier",
                                insight_text=insight,
                                stat_metadata={
                                    "column": c,
                                    "outlier_count": outlier_count,
                                    "pct": round(outlier_count / count_val * 100, 2),
                                },
                                embedding=emb,
                                confidence_score=0.80,
                            )
                            db.add(pattern)
                            patterns_created.append(pattern)

            if patterns_created:
                await db.commit()
                for p in patterns_created:
                    await db.refresh(p)
            return patterns_created
        finally:
            conn.close()

    @classmethod
    async def extract_narrative_pattern(
        cls,
        response_text: str,
        query: str,
        user_id: uuid.UUID,
        user_file_id: uuid.UUID,
        db: AsyncSession,
    ) -> LearnedPattern | None:
        """Extract a single high-value, reusable insight sentence from an agent response."""
        if len(response_text) < 150:
            return None

        prompt = (
            "You are an Intelligence Extraction Core.\n"
            "Extract exactly ONE high-value analytical pattern from this agent response.\n"
            "A pattern should be a one-sentence rule or insight that would be useful for future analysts.\n"
            f"Agent Query: {query}\n"
            f"Agent Response: {response_text[:1000]}\n\n"
            "Format: Start with the column(s) name. Be concise and precise.\n"
            "Example: 'Revenue displays cyclical expansion in Q4 driven by promotional discounts.'\n"
            "Output ONLY the pattern string, no preamble."
        )

        res = await llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100,
        )

        raw_insight = res.get("content", "").strip()
        cleaned = raw_insight.strip('"').strip("'").strip()
        if len(cleaned) < 15 or len(cleaned) > 250:
            return None

        emb = await llm_client.get_embedding(cleaned)
        pattern = LearnedPattern(
            user_id=user_id,
            user_file_id=user_file_id,
            pattern_type="llm_insight",
            insight_text=cleaned,
            stat_metadata={"source_query": query},
            embedding=emb,
            confidence_score=0.75,
        )
        db.add(pattern)
        await db.commit()
        await db.refresh(pattern)
        return pattern
