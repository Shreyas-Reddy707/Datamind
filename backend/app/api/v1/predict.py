"""DataMind v2 Prediction & AutoML Router.

AutoML benchmark mission triggering, data readiness diagnosis, smart caching,
and polling endpoints for Taskiq background workers.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authorized_user_file, get_current_user
from app.db.session import get_db
from app.engine.ml_runner import UniversalMLRunner
from app.models.file import UserFile
from app.models.prediction import PredictionHistory
from app.models.user import User
from app.schemas.predict import (
    PredictDiagnoseRequest,
    PredictionHistoryResponse,
    PredictRunRequest,
)
from app.workers.tasks import run_ml_benchmark_task

logger = logging.getLogger("datamind.api.v1.predict")

router = APIRouter(prefix="/predict", tags=["Prediction & ML"])


@router.post("/{file_id}/diagnose")
async def diagnose_ml_viability_endpoint(
    file_id: uuid.UUID,
    request: PredictDiagnoseRequest,
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
):
    """Evaluate dataset feasibility for machine learning missions."""
    gf = user_file.global_file
    df = await asyncio.to_thread(pd.read_parquet, gf.parquet_path)
    res = await asyncio.to_thread(UniversalMLRunner.diagnose_data, df, request.target_col)
    return res


@router.post("/{file_id}/run", response_model=PredictionHistoryResponse)
async def run_prediction_mission_endpoint(
    file_id: uuid.UUID,
    request: PredictRunRequest,
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
    db: AsyncSession = Depends(get_db),
):
    """
    Launch an automated ML benchmark run.
    Checks smart cache for identical completed runs before enqueuing background Taskiq worker.
    """
    gf = user_file.global_file
    df = await asyncio.to_thread(pd.read_parquet, gf.parquet_path)

    # 1. Diagnose viability
    diag = await asyncio.to_thread(UniversalMLRunner.diagnose_data, df, request.target_col)
    if not diag["can_proceed"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "ML mission blocked by data quality constraints", "blockers": diag["blockers"]},
        )

    target_col = request.target_col or diag.get("suggested_target")
    task_type = request.task_type or await asyncio.to_thread(UniversalMLRunner.auto_select_task, df, target_col)

    # 2. Smart Cache Check (Avoid redundant re-training on static Parquet)
    cache_stmt = (
        select(PredictionHistory)
        .where(
            PredictionHistory.user_file_id == user_file.id,
            PredictionHistory.user_id == current_user.id,
            PredictionHistory.target_column == target_col,
            PredictionHistory.task_type == task_type,
            PredictionHistory.status.in_(["queued", "running", "completed"]),
        )
        .order_by(PredictionHistory.created_at.desc())
        .limit(1)
    )
    cached_run = await db.scalar(cache_stmt)
    if cached_run:
        logger.info("Reusing existing %s ML benchmark run %s", cached_run.status, cached_run.id)
        return cached_run

    # 3. Create Queued Record
    feature_candidates = [c for c in df.columns if c != target_col]
    record = PredictionHistory(
        user_id=current_user.id,
        user_file_id=user_file.id,
        task_type=task_type,
        target_column=target_col,
        feature_columns=feature_candidates,
        status="queued",
        diagnostics_json=diag,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    # 4. Enqueue Taskiq Background Task
    try:
        await run_ml_benchmark_task.kiq(
            str(record.id),
            str(user_file.id),
            target_col,
        )
    except Exception as e:
        logger.debug("Taskiq background queue dispatch skipped: %s", e)

    return record


@router.get("/{file_id}/jobs/{prediction_id}", response_model=PredictionHistoryResponse)
async def get_prediction_job_endpoint(
    file_id: uuid.UUID,
    prediction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
    db: AsyncSession = Depends(get_db),
):
    """Poll progress, leaderboard, and feature importance of an ML benchmark job."""
    stmt = select(PredictionHistory).where(
        PredictionHistory.id == prediction_id,
        PredictionHistory.user_file_id == user_file.id,
        PredictionHistory.user_id == current_user.id,
    )
    job = await db.scalar(stmt)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction job record not found.",
        )
    return job


@router.get("/{file_id}/history", response_model=list[PredictionHistoryResponse])
async def list_prediction_history_endpoint(
    file_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve historical ML benchmark mission runs for this dataset."""
    stmt = (
        select(PredictionHistory)
        .where(
            PredictionHistory.user_file_id == user_file.id,
            PredictionHistory.user_id == current_user.id,
        )
        .order_by(PredictionHistory.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    jobs = await db.scalars(stmt)
    return list(jobs.all())

