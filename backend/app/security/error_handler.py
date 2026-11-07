"""DataMind v2 Standardized Error Envelope & PII Redactor.

Ensures zero stack trace leakage to the client and redacts sensitive credentials
from application logs.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("datamind.security")

# PII Redaction Regexes
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
BEARER_REGEX = re.compile(r"Bearer\s+[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_=]*")
SECRET_KEY_REGEX = re.compile(
    r"(password|token|secret|api_key)\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE
)


def redact_pii(message: str) -> str:
    """Mask emails, tokens, and credentials in log strings."""
    if not isinstance(message, str):
        message = str(message)
    redacted = EMAIL_REGEX.sub("[EMAIL_REDACTED]", message)
    redacted = BEARER_REGEX.sub("Bearer [TOKEN_REDACTED]", redacted)
    redacted = SECRET_KEY_REGEX.sub(r"\1: '[REDACTED]'", redacted)
    return redacted


class AppError(Exception):
    """Base application exception supporting standardized error envelopes."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


def build_error_response(
    status_code: int,
    error_code: str,
    message: str,
    request_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Construct an OWASP-compliant JSON error envelope."""
    req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
    content = {
        "error_code": error_code,
        "message": message,
        "request_id": req_id,
    }
    return JSONResponse(status_code=status_code, content=content, headers=headers)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all unhandled exception handler that redacts PII and suppresses traces."""
    req_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"

    if isinstance(exc, AppError):
        logger.warning(
            redact_pii(
                f"[{req_id}] Handled AppError {exc.error_code} ({exc.status_code}): {exc.message} "
                f"path={request.url.path}"
            )
        )
        return build_error_response(exc.status_code, exc.error_code, exc.message, req_id)

    # Unexpected internal exception
    logger.error(
        redact_pii(
            f"[{req_id}] Unhandled Exception: {type(exc).__name__}: {str(exc)} "
            f"path={request.url.path}"
        ),
        exc_info=False,  # Suppress traceback leaking into production console
    )
    return build_error_response(
        status_code=500,
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected internal error occurred. Please contact support with your request ID.",
        request_id=req_id,
    )
