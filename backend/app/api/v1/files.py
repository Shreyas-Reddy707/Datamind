"""DataMind v2 Dataset & OLAP Endpoints (/api/v1/files).

Implements file upload with SHA256 deduplication, paginated file list,
reference-counted deletion, DuckDB profiling, instant stats, and multi-file joins.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

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
    SwitchSheetRequest,
    UserFileListResponse,
    UserFileResponse,
)
from app.security.error_handler import AppError
from app.security.rate_limiter import RateLimiter
from app.workers.tasks import extract_learned_patterns_task

logger = logging.getLogger("datamind.api.v1.files")

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

    # 5. Auto-trigger background PatternLearner pattern extraction
    try:
        await extract_learned_patterns_task.kiq(
            str(current_user.id),
            str(user_file.id),
            analysis_summary=f"Dataset uploaded: {filename}",
            query="",
        )
    except Exception as e:
        logger.warning("Could not dispatch background pattern extraction task: %s", e)

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
            paths_to_remove = {global_file.parquet_path}
            for sh in (global_file.schema_json or {}).get("sheets", []):
                if isinstance(sh, dict) and sh.get("parquet_path"):
                    paths_to_remove.add(sh["parquet_path"])
            for p_rem in paths_to_remove:
                if p_rem and os.path.exists(p_rem):
                    try:
                        os.remove(p_rem)
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

    authorized_files: list[UserFile] = []
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
        authorized_files.append(uf)

    try:
        # Power SQL fallback mode (backward compatibility)
        if req.join_sql and req.join_sql.strip():
            records = await asyncio.to_thread(
                DuckDBManager.execute_multi_file_join,
                named_parquet_files=named_paths,
                join_sql=req.join_sql,
                limit=req.limit,
            )
            cols = list(records[0].keys()) if records else []
            return {
                "rows": records,
                "count": len(records),
                "columns": cols,
                "generated_sql": req.join_sql.strip(),
                "explanation": f"Combined {len(authorized_files)} dataset(s) returning {len(records)} joined row(s).",
            }

        # No-Code Visual Join Builder / Question Mode across first two files
        left_uf, right_uf = authorized_files[0], authorized_files[1]
        left_cols, left_num, left_cat = await asyncio.to_thread(
            DuckDBManager.inspect_parquet_columns, left_uf.global_file.parquet_path
        )
        right_cols, _, _ = await asyncio.to_thread(
            DuckDBManager.inspect_parquet_columns, right_uf.global_file.parquet_path
        )

        # Auto-detect matching shared column if left_col / right_col omitted
        shared_cols = [c for c in left_cols if c in set(right_cols)]
        left_col = req.left_col or (shared_cols[0] if shared_cols else left_cols[0])
        right_col = req.right_col or (shared_cols[0] if shared_cols else right_cols[0])

        group_by = req.group_by
        metrics = req.metrics
        filters = req.filters
        sort_by = req.sort_by
        sort_dir = req.sort_dir
        limit = req.limit

        if req.question and req.question.strip() and not group_by and not metrics:
            combined_cols = left_cols + [c for c in right_cols if c not in set(left_cols)]
            parsed = DuckDBManager.parse_natural_language_query(
                req.question, combined_cols, left_num, left_cat
            )
            group_by = parsed["group_by"]
            metrics = parsed["metrics"]
            filters = parsed["filters"]
            sort_by = parsed["sort_by"]
            sort_dir = parsed["sort_dir"]
            limit = parsed["limit"]

        exec_sql, params, display_sql, explanation = DuckDBManager.compile_builder_sql(
            valid_cols=left_cols,
            group_by=group_by,
            metrics=metrics,
            filters=filters,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            join_info={
                "right_cols": right_cols,
                "left_col": left_col,
                "right_col": right_col,
                "join_type": req.join_type,
                "right_alias": right_uf.display_name,
            },
        )
        res = await asyncio.to_thread(
            DuckDBManager.execute_compiled_query,
            left_uf.global_file.parquet_path,
            exec_sql,
            params,
            display_sql,
            explanation,
            right_uf.global_file.parquet_path,
        )
        dict_rows = [dict(zip(res["columns"], r, strict=False)) for r in res["rows"]]
        return {
            "rows": dict_rows,
            "count": res["row_count"],
            "columns": res["columns"],
            "table_rows": res["rows"],
            "execution_time_ms": res["execution_time_ms"],
            "generated_sql": res["generated_sql"],
            "explanation": res["explanation"],
        }
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


@router.get("/{file_id}/sheets")
async def list_file_sheets(
    user_file: UserFile = Depends(get_authorized_user_file),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return available Excel sheets (if multi-sheet workbook) and related user datasets."""
    gf = user_file.global_file
    schema_json = gf.schema_json or {}
    raw_sheets = schema_json.get("sheets", [])
    sheets_public = [
        {
            "name": s.get("name", f"Sheet {i + 1}"),
            "row_count": s.get("row_count", gf.row_count),
            "col_count": s.get("col_count", gf.col_count),
        }
        for i, s in enumerate(raw_sheets)
        if isinstance(s, dict)
    ]
    active_sheet = schema_json.get("active_sheet") or (sheets_public[0]["name"] if sheets_public else None)

    related_stmt = (
        select(UserFile)
        .options(selectinload(UserFile.global_file))
        .where(UserFile.user_id == current_user.id)
        .order_by(UserFile.created_at.desc())
        .limit(20)
    )
    related_files = (await db.scalars(related_stmt)).all()
    related_public = [
        {
            "id": str(rf.id),
            "display_name": rf.display_name,
            "row_count": rf.global_file.row_count if rf.global_file else 0,
            "col_count": rf.global_file.col_count if rf.global_file else 0,
            "detected_domain": rf.global_file.detected_domain if rf.global_file else "generic",
        }
        for rf in related_files
    ]

    return {
        "file_id": str(user_file.id),
        "active_sheet": active_sheet,
        "sheets": sheets_public,
        "related_datasets": related_public,
    }


@router.post("/{file_id}/switch-sheet", response_model=UserFileResponse)
async def switch_file_sheet(
    req: SwitchSheetRequest,
    user_file: UserFile = Depends(get_authorized_user_file),
    db: AsyncSession = Depends(get_db),
):
    """Switch the active Excel sheet for a multi-sheet workbook."""
    gf = user_file.global_file
    schema_json = dict(gf.schema_json or {})
    raw_sheets = schema_json.get("sheets", [])
    target_sheet = next(
        (s for s in raw_sheets if isinstance(s, dict) and s.get("name") == req.sheet_name),
        None,
    )
    if not target_sheet:
        raise AppError(
            message=f"Sheet '{req.sheet_name}' not found in workbook.",
            error_code="SHEET_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    sheet_schema = dict(target_sheet.get("schema_json") or {})
    sheet_schema["active_sheet"] = target_sheet["name"]
    sheet_schema["sheets"] = raw_sheets

    gf.parquet_path = target_sheet["parquet_path"]
    gf.row_count = int(target_sheet.get("row_count", gf.row_count))
    gf.col_count = int(target_sheet.get("col_count", gf.col_count))
    gf.detected_domain = sheet_schema.get("detected_domain", gf.detected_domain)
    gf.schema_json = sheet_schema
    flag_modified(gf, "schema_json")

    await db.commit()
    await db.refresh(user_file)
    await db.refresh(gf)
    user_file.global_file = gf
    return UserFileResponse.model_validate(user_file)
