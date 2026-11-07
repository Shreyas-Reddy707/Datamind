"""Global deduplicated files and user-scoped file records."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.chat import ChatHistory
    from app.models.memory import AnalysisMemory
    from app.models.organization import Organization
    from app.models.pattern import LearnedPattern
    from app.models.prediction import PredictionHistory
    from app.models.user import User


class GlobalFile(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "global_files"

    sha256_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    parquet_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_format: Mapped[str] = mapped_column(String(16), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    col_count: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    detected_domain: Mapped[str] = mapped_column(String(64), default="generic", nullable=False)
    ref_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user_files: Mapped[list["UserFile"]] = relationship("UserFile", back_populates="global_file")


class UserFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_files"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    global_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("global_files.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cleaning_report_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    summary_profile_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Table constraints and indexes
    __table_args__ = (
        Index("idx_user_files_user_created", "user_id", "created_at"),
        UniqueConstraint(
            "user_id", "global_file_id", "display_name", name="uq_user_files_user_global_display"
        ),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="files")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="user_files")
    global_file: Mapped["GlobalFile"] = relationship("GlobalFile", back_populates="user_files")
    analysis_memories: Mapped[list["AnalysisMemory"]] = relationship(
        "AnalysisMemory", back_populates="user_file", cascade="all, delete-orphan"
    )
    learned_patterns: Mapped[list["LearnedPattern"]] = relationship(
        "LearnedPattern", back_populates="user_file", cascade="all, delete-orphan"
    )
    predictions: Mapped[list["PredictionHistory"]] = relationship(
        "PredictionHistory", back_populates="user_file", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["ChatHistory"]] = relationship(
        "ChatHistory", back_populates="user_file", cascade="all, delete-orphan"
    )
