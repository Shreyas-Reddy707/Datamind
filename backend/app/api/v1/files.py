"""DataMind v2 Dataset & OLAP Endpoints (/api/v1/files).

Implements file upload with SHA256 deduplication, paginated file list,
reference-counted deletion, DuckDB profiling, instant stats, and multi-file joins.
"""

from __future__ import annotations

import asyncio
import os
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_authorized_user_file, get_current_user
from app.db.session import get_db
from app.engine.duckdb_manager import DuckDBManager
from app.engine.instant_responder import InstantResponder
from app.engine.parquet_ingestor import ParquetIngestor
from app.models.audit import AuditLog
from app.models.file import GlobalFile, UserFile
from app.models.user import User
from app.schemas.files import (
    InstantQueryRequest,
    InstantQueryResponse,
    JoinPreviewRequest,
    UserFileListResponse,
    UserFileResponse,
)
from app.security.error_handler import AppError
from app.security.rate_limiter import RateLimiter

router = APIRouter(prefix="/files", tags=["Datasets & Files"])


@router.post("/upload", response_model=UserFileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    request: Request,
    idempotency_key: str | None = Header(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload and convert multi-format datasets into content-addressed Parquet files.
    Enforces rate limits, magic-byte checks, and transactional deduplication.
    """
    # 1. Rate limiting
    rate_res = await RateLimiter.check_file_upload(str(current_user.id))
    if not rate_res["allowed"]:
        raise AppError(
            message=rate_res["message"],
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # 2. Read bytes
    filename = file.filename or "uploaded_dataset.csv"
    try:
        content = await file.read()
    except Exception as e:
        raise AppError(
            message=f"Failed to read upload stream: {str(e)}",
            error_code="UPLOAD_STREAM_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # 3. Transactional Ingest
    try:
        user_file, global_file, is_dedup = await ParquetIngestor.ingest_file(
            file_bytes=content,
            original_filename=filename,
            user_id=current_user.id,
            org_id=current_user.org_id,
            db=db,
        )
    except ValueError as ve:
        raise AppError(
            message=str(ve),
            error_code="FILE_VALIDATION_FAILED",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # 4. Audit Log
    req_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
    audit = AuditLog(
        user_id=current_user.id,
        event_type="file.upload",
        resource_type="user_file",
        resource_id=str(user_file.id),
        status_code=status.HTTP_201_CREATED,
        request_id=req_id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    # Eager load global_file
    user_file.global_file = global_file
    return UserFileResponse.model_validate(user_file)


@router.get("", response_model=UserFileListResponse)
async def list_files(
    limit: int = Query(20, ge=1, le=100, description="Page limit max 100"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List datasets owned strictly by the authenticated user with pagination."""
    # Count total
    count_stmt = (
        select(func.count()).select_from(UserFile).where(UserFile.user_id == current_user.id)
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    # Query items
    stmt = (
        select(UserFile)
        .options(selectinload(UserFile.global_file))
        .where(UserFile.user_id == current_user.id)
        .order_by(UserFile.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    return UserFileListResponse(
        items=[UserFileResponse.model_validate(it) for it in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{file_id}", response_model=UserFileResponse)
async def get_file_detail(
    user_file: UserFile = Depends(get_authorized_user_file),
):
    """Retrieve metadata for a specific authorized file (BOLA enforced)."""
    return UserFileResponse.model_validate(user_file)


@router.get("/{file_id}/profile")
async def get_file_data_profile(
    user_file: UserFile = Depends(get_authorized_user_file),
):
    """Generate live DuckDB data quality and summary profile for the dataset."""
    parquet_path = user_file.global_file.parquet_path
    try:
        profile = await asyncio.to_thread(DuckDBManager.generate_data_profile, parquet_path)
        return profile
    except Exception as e:
        raise AppError(
            message=f"Failed to profile dataset: {str(e)}",
            error_code="PROFILE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.post("/{file_id}/instant", response_model=InstantQueryResponse)
async def run_instant_query(
    req: InstantQueryRequest,
    user_file: UserFile = Depends(get_authorized_user_file),
    current_user: User = Depends(get_current_user),
):
    """Execute sub-25ms deterministic Tier 0 statistical query against DuckDB."""
    # Rate limit check
    rate_res = await RateLimiter.check_instant_stats(str(current_user.id))
    if not rate_res["allowed"]:
        raise AppError(
            message=rate_res["message"],
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    parquet_path = user_file.global_file.parquet_path
    schema_info = user_file.global_file.schema_json

    res = InstantResponder.execute(req.query, parquet_path, schema_info)
    return InstantQueryResponse(**res)


@router.delete("/{file_id}")
async def delete_file(
    file_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Safely delete user file reference under SELECT ... FOR UPDATE.
    Decrements global_file.ref_count and deletes on-disk Parquet if ref_count reaches 0.
    """
    # 1. Fetch user file
    stmt = select(UserFile).where(UserFile.id == file_id, UserFile.user_id == current_user.id)
    user_file = (await db.execute(stmt)).scalar_one_or_none()
    if not user_file:
        raise AppError(
            message="File not found or access denied.",
            error_code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 2. Lock global_file row
    global_file_id = user_file.global_file_id
    gf_stmt = select(GlobalFile).where(GlobalFile.id == global_file_id).with_for_update()
    global_file = (await db.execute(gf_stmt)).scalar_one_or_none()

    # 3. Delete user file record
    await db.delete(user_file)

    # 4. Reference-counted cleanup
    if global_file:
        global_file.ref_count -= 1
        if global_file.ref_count <= 0:
            if os.path.exists(global_file.parquet_path):
                try:
                    os.remove(global_file.parquet_path)
                except OSError:
                    pass
            await db.delete(global_file)

    # 5. Audit log
    req_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
    audit = AuditLog(
        user_id=current_user.id,
        event_type="file.delete",
        resource_type="user_file",
        resource_id=str(file_id),
        status_code=status.HTTP_200_OK,
        request_id=req_id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    return {"message": "Dataset successfully deleted."}


@router.post("/join-preview")
async def join_preview(
    req: JoinPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Perform multi-file DuckDB SQL JOIN across multiple user-authorized datasets.
    Strictly verifies ownership of every input file before executing SQL.
    """
    named_paths: list[tuple[str, str]] = []

    for spec in req.files:
        stmt = (
            select(UserFile)
            .options(selectinload(UserFile.global_file))
            .where(UserFile.id == spec.file_id, UserFile.user_id == current_user.id)
        )
        uf = (await db.execute(stmt)).scalar_one_or_none()
        if not uf:
            raise AppError(
                message=f"Unauthorized access or file '{spec.file_id}' not found.",
                error_code="RESOURCE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        named_paths.append((spec.alias, uf.global_file.parquet_path))

    try:
        records = DuckDBManager.execute_multi_file_join(
            named_parquet_files=named_paths,
            join_sql=req.join_sql,
            limit=req.limit,
        )
        return {"rows": records, "count": len(records)}
    except ValueError as ve:
        raise AppError(
            message=str(ve),
            error_code="INVALID_JOIN_SQL",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        raise AppError(
            message=f"SQL join execution failed: {str(e)}",
            error_code="JOIN_EXECUTION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
