"""Learned patterns model for self-learning analytical memory with pgvector."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.file import UserFile
    from app.models.user import User


class LearnedPattern(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "learned_patterns"

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
    pattern_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # correlation, outlier, llm_insight
    insight_text: Mapped[str] = mapped_column(Text, nullable=False)
    stat_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    embedding = mapped_column(Vector(768), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    helpful_votes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unhelpful_votes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_learned_patterns_user_file", "user_id", "user_file_id"),
        Index(
            "idx_learned_patterns_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="learned_patterns")
    user_file: Mapped["UserFile"] = relationship("UserFile", back_populates="learned_patterns")
