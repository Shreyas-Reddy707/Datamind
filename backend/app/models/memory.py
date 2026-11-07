"""Analysis memory model storing agent forensic findings and visualizations."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.file import UserFile
    from app.models.user import User


class AnalysisMemory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "analysis_memory"

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
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    finding_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    implication_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    plotly_spec_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_analysis_memory_user_file", "user_id", "user_file_id", "created_at"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="analysis_memories")
    user_file: Mapped["UserFile"] = relationship("UserFile", back_populates="analysis_memories")
