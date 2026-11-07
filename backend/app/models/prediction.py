"""Prediction history model for AutoML benchmark runs and metrics."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.file import UserFile
    from app.models.user import User


class PredictionHistory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "prediction_history"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # classification, regression, clustering, timeseries
    target_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    feature_columns: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    best_model_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    leaderboard_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    feature_importance_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    diagnostics_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="queued", nullable=False
    )  # queued, running, completed, failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_prediction_history_user_file", "user_id", "user_file_id", "created_at"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="predictions")
    user_file: Mapped["UserFile"] = relationship("UserFile", back_populates="predictions")
