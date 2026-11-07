"""DataMind v2 Feedback & Confidence Scoring.

Processes user ratings (thumbs up/down) on learned patterns and analytical memories,
updating helpful/unhelpful votes and adjusting confidence scores with Laplace smoothing.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pattern import LearnedPattern

logger = logging.getLogger("datamind.memory.feedback")


class FeedbackManager:
    """Manages explicit human feedback on system-learned intelligence."""

    @classmethod
    async def record_pattern_vote(
        cls,
        pattern_id: uuid.UUID,
        user_id: uuid.UUID,
        is_helpful: bool,
        db: AsyncSession,
    ) -> dict[str, Any] | None:
        """Record a vote on a learned pattern and recalculate its confidence score."""
        stmt = select(LearnedPattern).where(
            LearnedPattern.id == pattern_id,
            LearnedPattern.user_id == user_id,
        )
        pattern = await db.scalar(stmt)
        if not pattern:
            return None

        if is_helpful:
            pattern.helpful_votes += 1
        else:
            pattern.unhelpful_votes += 1

        # Laplace smoothed confidence score in range (0.0, 1.0)
        pos = pattern.helpful_votes
        neg = pattern.unhelpful_votes
        # Base confidence calculation: (positive + 1) / (total + 2)
        smoothed = (pos + 1.0) / (pos + neg + 2.0)
        pattern.confidence_score = round(smoothed, 3)

        await db.commit()
        await db.refresh(pattern)

        return {
            "pattern_id": str(pattern.id),
            "helpful_votes": pattern.helpful_votes,
            "unhelpful_votes": pattern.unhelpful_votes,
            "confidence_score": pattern.confidence_score,
        }
