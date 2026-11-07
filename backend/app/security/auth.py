"""DataMind v2 Authentication & Cryptography Subsystem.

Implements Argon2id hashing via pwdlib, 15-minute JWT access tokens, rotating
SHA256-hashed refresh tokens, 5-attempt account lockouts, and guest provisioning.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.organization import Organization
from app.models.session import UserSession
from app.models.user import User

# Argon2id Password Hasher
pwd_context = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password in constant-time against Argon2id hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_token(raw_token: str) -> str:
    """Compute SHA-256 hash of high-entropy token for safe DB storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create short-lived JWT access token (15 mins default)."""
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"iat": now, "exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate signature & expiration of JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_refresh_token() -> tuple[str, str, datetime]:
    """Generate high-entropy refresh token, return (raw_token, token_hash, expires_at)."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return raw_token, token_hash, expires_at


def generate_password_reset_token() -> tuple[str, str, datetime]:
    """Generate reset token, return (raw_token, token_hash, expires_at)."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    return raw_token, token_hash, expires_at


async def check_lockout(user: User) -> tuple[bool, int]:
    """Check if user account is locked. Returns (is_locked, remaining_minutes)."""
    if user.locked_until:
        now = datetime.now(UTC)
        if user.locked_until > now:
            remaining = int((user.locked_until - now).total_seconds() / 60) + 1
            return True, remaining
    return False, 0


async def handle_failed_login(user: User, db: AsyncSession) -> tuple[bool, int]:
    """Increment failed login attempts and lock account if limit reached."""
    user.failed_login_attempts += 1
    locked = False
    minutes = 0
    if user.failed_login_attempts >= settings.LOCKOUT_MAX_ATTEMPTS:
        user.locked_until = datetime.now(UTC) + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
        locked = True
        minutes = settings.LOCKOUT_DURATION_MINUTES
    await db.commit()
    return locked, minutes


async def reset_failed_logins(user: User, db: AsyncSession) -> None:
    """Reset failed attempts on successful authentication."""
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()


async def provision_guest_user(db: AsyncSession) -> tuple[User, str, str]:
    """Provision a temporary guest account with isolated org and default permissions."""
    guest_uuid = uuid.uuid4().hex[:10]
    org_slug = f"guest-org-{guest_uuid}"
    org = Organization(name=f"Guest Org {guest_uuid}", slug=org_slug)
    db.add(org)
    await db.flush()

    guest_email = f"guest_{guest_uuid}@datamind.local"
    temp_password = secrets.token_urlsafe(16)
    hashed = hash_password(temp_password)

    user = User(
        org_id=org.id,
        email=guest_email,
        password_hash=hashed,
        role="guest",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Generate tokens
    access_token = create_access_token(
        {"sub": str(user.id), "org_id": str(user.org_id), "role": "guest"}
    )
    raw_refresh, refresh_hash, refresh_exp = generate_refresh_token()

    session = UserSession(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        expires_at=refresh_exp,
    )
    db.add(session)
    await db.commit()
    await db.refresh(user)

    return user, access_token, raw_refresh
