"""DataMind v2 Analysis Laboratory Schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LabVisualizeRequest(BaseModel):
    chart_type: Literal[
        "distribution",
        "histogram",
        "bar",
        "scatter",
        "line",
        "heatmap",
        "correlation",
        "box",
    ] = Field(
        ...,
        description="Type of chart: distribution, scatter, line, heatmap, box",
    )
    column: str | None = Field(default=None, max_length=128)
    x_col: str | None = Field(default=None, max_length=128)
    y_col: str | None = Field(default=None, max_length=128)
    color_col: str | None = Field(default=None, max_length=128)


class BuilderMetricSpec(BaseModel):
    col: str = Field(..., min_length=1, max_length=128)
    agg: Literal["avg", "sum", "count", "min", "max", "median"] = "avg"


class BuilderFilterSpec(BaseModel):
    col: str = Field(..., min_length=1, max_length=128)
    op: Literal["eq", "neq", "gt", "gte", "lt", "lte", "contains", "not_null", "is_null"] = "eq"
    val: str | int | float | None = None


class BuilderJoinSpec(BaseModel):
    right_file_id: uuid.UUID
    left_col: str = Field(..., min_length=1, max_length=128)
    right_col: str = Field(..., min_length=1, max_length=128)
    join_type: Literal["inner", "left"] = "inner"


class LabQueryRequest(BaseModel):
    mode: Literal["auto", "builder", "question", "natural_language", "sql"] = "auto"
    sql: str | None = Field(default=None, max_length=10000)
    query: str | None = Field(default=None, max_length=10000)
    question: str | None = Field(default=None, max_length=1000)
    natural_language: str | None = Field(default=None, max_length=1000)
    group_by: list[str] = Field(default_factory=list, max_length=5)
    metrics: list[BuilderMetricSpec] = Field(default_factory=list, max_length=10)
    filters: list[BuilderFilterSpec] = Field(default_factory=list, max_length=15)
    sort_by: str | None = Field(default=None, max_length=128)
    sort_dir: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=50, ge=1, le=100)
    join_config: BuilderJoinSpec | None = None
    join_file_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)


class LabAnalyzeRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Analytical mission or forensic hypothesis to evaluate",
    )


class AnalysisMemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_file_id: uuid.UUID
    agent_type: str
    query_text: str
    context_text: str | None = None
    finding_text: str
    evidence_json: dict[str, Any] | None = None
    implication_text: str | None = None
    plotly_spec_json: dict[str, Any] | None = None
    created_at: datetime
