"""DataMind v2 Prediction & AutoML Schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PredictDiagnoseRequest(BaseModel):
    target_col: str | None = Field(default=None, max_length=128)


class PredictRunRequest(BaseModel):
    target_col: str | None = Field(default=None, max_length=128)
    task_type: Literal["classification", "regression", "clustering", "timeseries"] | None = Field(
        default=None,
        description="Override task mode: classification, regression, clustering, timeseries",
    )


class PredictionHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_file_id: uuid.UUID
    task_type: str
    target_column: str | None = None
    feature_columns: list[str]
    best_model_name: str | None = None
    leaderboard_json: dict[str, Any] | None = None
    feature_importance_json: dict[str, Any] | None = None
    diagnostics_json: dict[str, Any] | None = None
    status: str
    created_at: datetime

