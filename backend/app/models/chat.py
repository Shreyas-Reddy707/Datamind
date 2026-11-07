"""Chat history model for multi-tier conversational agent interactions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.file import UserFile
    from app.models.user import User


class ChatHistory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "chat_history"

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
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user, assistant, system
    tier: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )  # 0: Instant, 1: SLM, 2/3: LangGraph
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lab_artifact_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("idx_chat_history_file_created", "user_file_id", "created_at"),)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="chat_messages")
    user_file: Mapped["UserFile"] = relationship("UserFile", back_populates="chat_messages")
