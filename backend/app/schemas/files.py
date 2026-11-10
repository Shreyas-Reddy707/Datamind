"""DataMind v2 File & OLAP Pydantic Schemas."""

from __future__ import annotations

import uuid
import warnings
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message=r'.*Field name "schema_json" in "GlobalFileResponse" shadows an attribute.*',
)


class GlobalFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: uuid.UUID
    sha256_hash: str
    original_format: str
    file_size_bytes: int
    row_count: int
    col_count: int
    detected_domain: str
    ref_count: int
    schema_json: dict[str, Any]
    created_at: datetime


class UserFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    org_id: uuid.UUID
    global_file_id: uuid.UUID
    display_name: str
    created_at: datetime
    updated_at: datetime
    global_file: GlobalFileResponse | None = None


class UserFileListResponse(BaseModel):
    items: list[UserFileResponse]
    total: int
    limit: int
    offset: int


class InstantQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)


class InstantQueryResponse(BaseModel):
    result: str
    latency_ms: int
    tier: int
    intent: str


class JoinFileSpec(BaseModel):
    file_id: uuid.UUID
    alias: str = Field(..., pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class JoinPreviewRequest(BaseModel):
    files: list[JoinFileSpec] = Field(..., min_length=2, max_length=5)
    join_sql: str = Field(..., min_length=5, max_length=2000)
    limit: int = Field(default=50, ge=1, le=100)


class SwitchSheetRequest(BaseModel):
    sheet_name: str = Field(..., min_length=1, max_length=128)
