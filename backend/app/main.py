"""DataMind v2 Main FastAPI Application.

Configures strict security headers, CORS origin whitelisting, 1MB body cap,
global exception handling, health checks, and API v1 routers.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.files import router as files_router
from app.api.v1.lab import router as lab_router
from app.api.v1.predict import router as predict_router
from app.config import settings
from app.db.session import engine
from app.security.error_handler import AppError, build_error_response, global_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup verification
    yield
    # Shutdown cleanup
    await engine.dispose()


app = FastAPI(
    title="DataMind v2 API",
    description="Decoupled Multi-Agent Analytical Workspace & Intelligence Platform",
    version="2.0.0",
    lifespan=lifespan,
)

# 1. CORS Middleware (Strict Origin Whitelist)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


# 2. Security Headers & Request ID Middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    request.state.request_id = req_id

    # 1MB Body Limit check for JSON payloads (skip multipart file uploads which have 50MB limit)
    content_type = request.headers.get("content-type", "")
    content_length = request.headers.get("content-length")

    if not content_type.startswith("multipart/form-data") and content_length:
        try:
            if int(content_length) > 1 * 1024 * 1024:  # 1MB
                return build_error_response(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    error_code="PAYLOAD_TOO_LARGE",
                    message="JSON request body exceeds 1MB safety limit.",
                    request_id=req_id,
                )
        except ValueError:
            pass

    response: Response = await call_next(request)

    # Attach defensive headers
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Restrict file downloads to sandbox
    if request.url.path.startswith("/api/v1/files") and request.method == "GET":
        response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"

    return response


# 3. Exception Handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(AppError, global_exception_handler)


# 4. Observability / Health Checks
@app.get("/health/live", tags=["Observability"])
async def health_live():
    """Liveness probe: verifies process is alive."""
    return {"status": "alive", "version": "2.0.0"}


@app.get("/health/ready", tags=["Observability"])
async def health_ready():
    """Readiness probe: validates live connectivity to PostgreSQL and Redis."""
    errors = {}

    # Check PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        errors["database"] = f"Postgres unreachable: {str(e)}"

    # Check Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2.0)
        await r.ping()
        await r.aclose()
    except Exception as e:
        errors["redis"] = f"Redis unreachable: {str(e)}"

    if errors:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "errors": errors},
        )

    return {"status": "ready", "database": "connected", "redis": "connected"}


# 5. API v1 Routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(files_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(lab_router, prefix="/api/v1")
app.include_router(predict_router, prefix="/api/v1")
