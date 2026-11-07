"""DataMind v2 Chat Schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatStreamRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="User analytical question")


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_file_id: uuid.UUID
    role: str
    tier: int | None = None
    message_text: str
    latency_ms: int | None = None
    lab_artifact_json: dict[str, Any] | None = None
    created_at: datetime


class PatternFeedbackRequest(BaseModel):
    is_helpful: bool

