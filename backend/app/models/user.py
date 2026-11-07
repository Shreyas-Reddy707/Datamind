"""User identity and authorization model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.chat import ChatHistory
    from app.models.file import UserFile
    from app.models.memory import AnalysisMemory
    from app.models.organization import Organization
    from app.models.password_reset import PasswordResetToken
    from app.models.pattern import LearnedPattern
    from app.models.prediction import PredictionHistory
    from app.models.session import UserSession


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), default="member", nullable=False
    )  # owner, admin, member, guest
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    )
    files: Mapped[list["UserFile"]] = relationship(
        "UserFile", back_populates="user", cascade="all, delete-orphan"
    )
    analysis_memories: Mapped[list["AnalysisMemory"]] = relationship(
        "AnalysisMemory", back_populates="user", cascade="all, delete-orphan"
    )
    learned_patterns: Mapped[list["LearnedPattern"]] = relationship(
        "LearnedPattern", back_populates="user", cascade="all, delete-orphan"
    )
    predictions: Mapped[list["PredictionHistory"]] = relationship(
        "PredictionHistory", back_populates="user", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["ChatHistory"]] = relationship(
        "ChatHistory", back_populates="user", cascade="all, delete-orphan"
    )
