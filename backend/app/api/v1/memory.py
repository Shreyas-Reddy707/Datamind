"""DataMind v2 Episodic & Learned Pattern Memory Router.

Manages self-learning analytical memory, pattern retrieval with pgvector,
and memory deletion with strict BOLA authorization checks.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authorized_user_file, get_current_user
from app.db.session import get_db
from app.memory.learner import PatternLearner
from app.models.file import UserFile
from app.models.memory import AnalysisMemory
from app.models.pattern import LearnedPattern
from app.models.user import User
from app.schemas.lab import AnalysisMemoryResponse

logger = logging.getLogger("datamind.api.v1.memory")

router = APIRouter(prefix="/memory", tags=["Episodic Memory"])


@router.get("/{file_id}", response_model=list[AnalysisMemoryResponse])
async def list_file_memories_endpoint(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieve episodic and statistical memories for a dataset.

    If empty, autonomously triggers PatternLearner to discover initial statistical patterns.
    """
    stmt = (
        select(AnalysisMemory)
        .where(
            AnalysisMemory.user_file_id == user_file.id,
            AnalysisMemory.user_id == current_user.id,
        )
        .order_by(AnalysisMemory.created_at.desc())
    )
    memories = list((await db.scalars(stmt)).all())
    if memories:
        return memories

    # If no analysis memories, check existing learned patterns or extract them
    p_stmt = (
        select(LearnedPattern)
        .where(
            LearnedPattern.user_file_id == user_file.id,
            LearnedPattern.user_id == current_user.id,
        )
        .order_by(LearnedPattern.created_at.desc())
    )
    patterns = list((await db.scalars(p_stmt)).all())

    if not patterns:
        try:
            gf = user_file.global_file
            patterns = await PatternLearner.extract_statistical_patterns(
                parquet_path=gf.parquet_path,
                user_id=current_user.id,
                user_file_id=user_file.id,
                db=db,
            )
        except Exception as e:
            logger.warning("PatternLearner initial extraction failed for file %s: %s", file_id, e)
            patterns = []

    # Persist or synthesize corresponding AnalysisMemory entries for UI display
    for p in patterns:
        mem = AnalysisMemory(
            id=p.id,
            user_id=current_user.id,
            user_file_id=user_file.id,
            agent_type="pattern",
            query_text=f"Statistical {p.pattern_type.capitalize()} Discovery",
            context_text=f"Confidence: {p.confidence_score}",
            finding_text=p.insight_text,
            evidence_json=p.stat_metadata,
            implication_text=None,
            plotly_spec_json=None,
        )
        db.add(mem)
        memories.append(mem)

    if memories:
        try:
            await db.commit()
            for m in memories:
                await db.refresh(m)
        except Exception as e:
            logger.warning("Could not persist initial memory items: %s", e)
            await db.rollback()

    return memories


@router.delete("/{memory_id}")
async def delete_memory_endpoint(
    memory_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Delete an episodic memory or learned pattern with strict user BOLA ownership check."""
    # Try deleting from AnalysisMemory
    stmt = delete(AnalysisMemory).where(
        AnalysisMemory.id == memory_id,
        AnalysisMemory.user_id == current_user.id,
    )
    res = await db.execute(stmt)

    # Also attempt delete from LearnedPattern if present
    p_stmt = delete(LearnedPattern).where(
        LearnedPattern.id == memory_id,
        LearnedPattern.user_id == current_user.id,
    )
    p_res = await db.execute(p_stmt)

    if res.rowcount == 0 and p_res.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory record not found or access denied.",
        )

    await db.commit()
    return {"ok": True}

