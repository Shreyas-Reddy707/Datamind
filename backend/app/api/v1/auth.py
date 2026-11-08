"""DataMind v2 Authentication Endpoints (/api/v1/auth).

Implements OWASP-hardened user registration, Argon2id login, 5-attempt lockout,
rotating refresh cookies, guest provisioning, and password resets.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.db.session import get_db
from app.models.organization import Organization
from app.models.password_reset import PasswordResetToken
from app.models.session import UserSession
from app.models.user import User
from app.schemas.auth import (
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.security.auth import (
    check_lockout,
    create_access_token,
    generate_password_reset_token,
    generate_refresh_token,
    handle_failed_login,
    hash_password,
    hash_token,
    provision_guest_user,
    reset_failed_logins,
    verify_password,
)
from app.security.error_handler import AppError
from app.security.rate_limiter import RateLimiter
from app.security.sanitizer import InputSanitizer

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: UserRegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Register new organization and user with Argon2id password."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    rate_res = await RateLimiter.check_register(client_ip)
    if not rate_res["allowed"]:
        raise AppError(
            message=rate_res["message"],
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    clean_email = InputSanitizer.sanitize_auth_input(req.email, "email")
    clean_username = (
        InputSanitizer.sanitize_auth_input(req.username, "username")
        if req.username
        else clean_email.split("@")[0][:20]
    )

    # Check email uniqueness
    existing_user = (
        await db.execute(select(User).where(User.email == clean_email))
    ).scalar_one_or_none()
    if existing_user:
        raise AppError(
            message="An account with this email address already exists.",
            error_code="EMAIL_ALREADY_EXISTS",
            status_code=status.HTTP_409_CONFLICT,
        )

    # Create Organization
    org_name = req.org_name or f"{clean_username}'s Workspace"
    org_slug = f"org-{uuid.uuid4().hex[:8]}"
    org = Organization(name=org_name, slug=org_slug)
    db.add(org)
    await db.flush()

    # Create User
    user = User(
        org_id=org.id,
        email=clean_email,
        password_hash=hash_password(req.password),
        role="owner",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Create tokens
    access_token = create_access_token(
        {"sub": str(user.id), "org_id": str(org.id), "role": user.role}
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

    # Set rotating refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=(settings.ENVIRONMENT == "production"),
        samesite="lax",
        max_age=7 * 24 * 3600,
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    req: UserLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate credentials with Argon2id and 5-attempt lockout enforcement."""
    clean_email = InputSanitizer.sanitize_auth_input(req.email, "email")

    # Rate Limit
    rate_res = await RateLimiter.check_login(clean_email)
    if not rate_res["allowed"]:
        raise AppError(
            message=rate_res["message"],
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Fetch user
    user = (await db.execute(select(User).where(User.email == clean_email))).scalar_one_or_none()

    # Dummy hash to preserve constant-time verification on non-existent email
    dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$P9bQoM67vR4Jz1eO8fN5Yg"
    target_hash = user.password_hash if user else dummy_hash

    # Check Lockout
    if user:
        is_locked, remaining_mins = await check_lockout(user)
        if is_locked:
            raise AppError(
                message=f"Account temporarily locked due to multiple failed attempts. Try again in {remaining_mins} minutes.",
                error_code="ACCOUNT_LOCKED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    password_ok = verify_password(req.password, target_hash)

    if not user or not password_ok:
        if user:
            locked, mins = await handle_failed_login(user, db)
            if locked:
                raise AppError(
                    message=f"Account locked for {mins} minutes following 5 failed attempts.",
                    error_code="ACCOUNT_LOCKED",
                    status_code=status.HTTP_403_FORBIDDEN,
                )
        raise AppError(
            message="Invalid email or password.",
            error_code="INVALID_CREDENTIALS",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        raise AppError(
            message="Account is deactivated. Contact administration.",
            error_code="ACCOUNT_DEACTIVATED",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Success: reset failed logins
    await reset_failed_logins(user, db)

    # Issue tokens
    access_token = create_access_token(
        {"sub": str(user.id), "org_id": str(user.org_id), "role": user.role}
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

    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=(settings.ENVIRONMENT == "production"),
        samesite="lax",
        max_age=7 * 24 * 3600,
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Rotate refresh token and issue fresh 15-minute access token."""
    if not refresh_token:
        raise AppError(
            message="Refresh token missing from request cookies.",
            error_code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token_h = hash_token(refresh_token)
    stmt = select(UserSession).where(
        UserSession.refresh_token_hash == token_h,
        UserSession.revoked_at.is_(None),
    )
    session = (await db.execute(stmt)).scalar_one_or_none()

    now = datetime.now(UTC)
    if not session or session.expires_at < now:
        raise AppError(
            message="Invalid or expired session. Please login again.",
            error_code="INVALID_REFRESH_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # Fetch user
    user = (await db.execute(select(User).where(User.id == session.user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise AppError(
            message="User account inactive.",
            error_code="ACCOUNT_DEACTIVATED",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Revoke old session (Rotation)
    session.revoked_at = now

    # Issue new refresh token & access token
    new_raw_refresh, new_refresh_hash, new_refresh_exp = generate_refresh_token()
    new_session = UserSession(
        user_id=user.id,
        refresh_token_hash=new_refresh_hash,
        expires_at=new_refresh_exp,
    )
    db.add(new_session)
    await db.commit()

    access_token = create_access_token(
        {"sub": str(user.id), "org_id": str(user.org_id), "role": user.role}
    )

    response.set_cookie(
        key="refresh_token",
        value=new_raw_refresh,
        httponly=True,
        secure=(settings.ENVIRONMENT == "production"),
        samesite="lax",
        max_age=7 * 24 * 3600,
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Revoke active refresh token and delete cookie."""
    if refresh_token:
        token_h = hash_token(refresh_token)
        now = datetime.now(UTC)
        await db.execute(
            update(UserSession)
            .where(UserSession.refresh_token_hash == token_h)
            .values(revoked_at=now)
        )
        await db.commit()

    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=(settings.ENVIRONMENT == "production"),
        samesite="lax",
    )
    return {"message": "Successfully logged out."}


@router.post("/guest", response_model=TokenResponse)
async def guest_login(
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Provision instant guest session with isolated organization."""
    user, access_token, raw_refresh = await provision_guest_user(db)

    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=(settings.ENVIRONMENT == "production"),
        samesite="lax",
        max_age=24 * 3600,
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
):
    """Return profile for currently authenticated user."""
    return UserResponse.model_validate(current_user)


@router.post("/password-reset/request")
async def request_password_reset(
    req: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate high-entropy reset token with 1-hour expiry."""
    clean_email = InputSanitizer.sanitize_auth_input(req.email, "email")
    user = (await db.execute(select(User).where(User.email == clean_email))).scalar_one_or_none()

    # Avoid user enumeration: always return 200 generic message
    if user:
        raw_token, token_h, expires_at = generate_password_reset_token()
        reset_record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_h,
            expires_at=expires_at,
        )
        db.add(reset_record)
        await db.commit()

    return {"message": "If this email is registered, instructions have been generated."}


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    req: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Validate reset token and update password."""
    token_h = hash_token(req.token)
    stmt = select(PasswordResetToken).where(
        PasswordResetToken.token_hash == token_h,
        PasswordResetToken.used_at.is_(None),
    )
    record = (await db.execute(stmt)).scalar_one_or_none()

    now = datetime.now(UTC)
    if not record or record.expires_at < now:
        raise AppError(
            message="Password reset token is invalid or expired.",
            error_code="INVALID_RESET_TOKEN",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Update user password
    new_hashed = hash_password(req.password)
    await db.execute(
        update(User)
        .where(User.id == record.user_id)
        .values(password_hash=new_hashed, failed_login_attempts=0, locked_until=None)
    )
    record.used_at = now
    await db.commit()

    return {"message": "Password successfully updated. You may now login."}
