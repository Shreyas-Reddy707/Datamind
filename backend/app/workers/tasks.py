"""DataMind v2 Async Worker Tasks.

Background workers for AutoML model training and self-learning pattern extraction.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import pandas as pd
from sqlalchemy import select

from app.db.session import async_session_factory
from app.engine.ml_runner import UniversalMLRunner
from app.memory.learner import PatternLearner
from app.models.file import GlobalFile, UserFile
from app.models.prediction import PredictionHistory
from app.workers.broker import broker

logger = logging.getLogger("datamind.workers.tasks")


@broker.task
async def run_ml_benchmark_task(
    prediction_id: str,
    user_file_id: str,
    target_col: str | None = None,
) -> dict[str, Any]:
    """Execute asynchronous AutoML benchmark mission and persist results to prediction_history."""
    pred_uuid = uuid.UUID(prediction_id)
    _ = uuid.UUID(user_file_id)

    async with async_session_factory() as db:
        stmt = (
            select(PredictionHistory, UserFile, GlobalFile)
            .join(UserFile, PredictionHistory.user_file_id == UserFile.id)
            .join(GlobalFile, UserFile.global_file_id == GlobalFile.id)
            .where(PredictionHistory.id == pred_uuid)
        )
        row = (await db.execute(stmt)).first()
        if not row:
            logger.error("Prediction task aborted: Record %s not found", prediction_id)
            return {"status": "failed", "error": "Record not found"}

        pred_record, user_file, global_file = row
        pred_record.status = "running"
        await db.commit()

        try:
            # Load dataset from Parquet storage
            df = pd.read_parquet(global_file.parquet_path)

            # Auto-detect task
            task_type = UniversalMLRunner.auto_select_task(df, target_col)
            pred_record.task_type = task_type
            pred_record.target_column = target_col

            # Diagnose
            diag = UniversalMLRunner.diagnose_data(df, target_col)
            pred_record.diagnostics_json = diag
            if not diag["can_proceed"]:
                pred_record.status = "failed"
                await db.commit()
                return {"status": "failed", "blockers": diag["blockers"]}

            final_target = target_col or diag.get("suggested_target")
            prep = UniversalMLRunner.preprocess(df, final_target, task_type)
            pred_record.feature_columns = prep["feature_names"]

            if task_type == "classification":
                results = UniversalMLRunner.run_classification(
                    prep["X_train"],
                    prep["X_test"],
                    prep["y_train"],
                    prep["y_test"],
                    prep["feature_names"],
                )
            elif task_type == "regression":
                results = UniversalMLRunner.run_regression(
                    prep["X_train"],
                    prep["X_test"],
                    prep["y_train"],
                    prep["y_test"],
                    prep["feature_names"],
                )
            else:
                results = UniversalMLRunner.run_clustering(df, prep["feature_names"])

            pred_record.best_model_name = results.get("best_model_name")
            pred_record.leaderboard_json = {
                "leaderboard": results.get("leaderboard", []),
                "test_metric": results.get("test_metric_name"),
                "test_value": results.get("test_metric_value"),
            }
            pred_record.feature_importance_json = results.get("feature_importances", {})
            pred_record.status = "completed"
            await db.commit()

            return {
                "status": "completed",
                "prediction_id": prediction_id,
                "best_model": pred_record.best_model_name,
            }
        except Exception as e:
            logger.exception("ML Benchmark failed for prediction %s", prediction_id)
            pred_record.status = "failed"
            pred_record.diagnostics_json = {"error": str(e)}
            await db.commit()
            return {"status": "failed", "error": str(e)}


@broker.task
async def extract_learned_patterns_task(
    user_id: str,
    user_file_id: str,
    analysis_summary: str,
    query: str = "",
) -> dict[str, Any]:
    """Asynchronously extract and store statistical and semantic patterns."""
    u_uuid = uuid.UUID(user_id)
    uf_uuid = uuid.UUID(user_file_id)

    async with async_session_factory() as db:
        uf_stmt = (
            select(UserFile, GlobalFile)
            .join(GlobalFile, UserFile.global_file_id == GlobalFile.id)
            .where(UserFile.id == uf_uuid, UserFile.user_id == u_uuid)
        )
        row = (await db.execute(uf_stmt)).first()
        if not row:
            return {"status": "aborted", "reason": "file not found"}

        user_file, global_file = row
        # 1. Statistical patterns
        stat_patterns = await PatternLearner.extract_statistical_patterns(
            global_file.parquet_path, u_uuid, uf_uuid, db
        )

        # 2. Narrative insight
        narrative_pattern = None
        if analysis_summary and len(analysis_summary) > 100:
            narrative_pattern = await PatternLearner.extract_narrative_pattern(
                analysis_summary, query, u_uuid, uf_uuid, db
            )

        return {
            "status": "completed",
            "stat_patterns_count": len(stat_patterns),
            "narrative_extracted": narrative_pattern is not None,
        }
