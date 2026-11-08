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

