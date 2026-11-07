"""DataMind v2 FastAPI Dependencies.

Implements JWT extraction and mandatory BOLA ownership checks with audit logging.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.file import UserFile
from app.models.user import User
from app.security.auth import decode_access_token
from app.security.error_handler import AppError


async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate JWT Bearer token, returning the authenticated User."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(
            message="Missing or invalid authentication header.",
            error_code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token = authorization[7:].strip()
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise AppError(
            message="Invalid or expired access token.",
            error_code="TOKEN_EXPIRED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        user_uuid = uuid.UUID(payload["sub"])
    except ValueError:
        raise AppError(
            message="Malformed subject identifier in token.",
            error_code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    stmt = select(User).where(User.id == user_uuid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise AppError(
            message="User account no longer exists.",
            error_code="USER_NOT_FOUND",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        raise AppError(
            message="User account is deactivated. Contact administration.",
            error_code="ACCOUNT_DEACTIVATED",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return user


async def get_authorized_user_file(
    file_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserFile:
    """
    Mandatory BOLA / IDOR defense:
    Verifies that the requested file belongs strictly to the authenticated user.
    Logs any cross-user access attempts to audit_log.
    """
    stmt = (
        select(UserFile)
        .options(selectinload(UserFile.global_file))
        .where(UserFile.id == file_id, UserFile.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    user_file = result.scalar_one_or_none()

    if not user_file:
        # Audit BOLA / unauthorized probing
        req_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
        client_ip = request.client.host if request.client else None
        audit = AuditLog(
            user_id=current_user.id,
            event_type="bola.blocked",
            resource_type="user_file",
            resource_id=str(file_id),
            status_code=status.HTTP_404_NOT_FOUND,
            request_id=req_id,
            ip_address=client_ip,
        )
        db.add(audit)
        await db.commit()

        raise AppError(
            message="File not found or access denied.",
            error_code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return user_file
