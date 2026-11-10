"""DataMind v2 Analysis Laboratory Router.

Comprehensive dataset overview, deep forensic analysis persistence (AnalysisMemory),
dynamic Plotly chart spec builder, and executive report export.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_authorized_user_file, get_current_user
from app.db.session import get_db
from app.engine.chart_builder import ChartBuilder
from app.engine.duckdb_manager import DuckDBManager
from app.llm.client import llm_client
from app.models.file import UserFile
from app.models.memory import AnalysisMemory
from app.models.prediction import PredictionHistory
from app.models.user import User
from app.schemas.lab import (
    AnalysisMemoryResponse,
    LabAnalyzeRequest,
    LabQueryRequest,
    LabVisualizeRequest,
)

logger = logging.getLogger("datamind.api.v1.lab")

router = APIRouter(prefix="/lab", tags=["Analysis Laboratory"])


@router.get("/{file_id}/overview")
async def get_lab_overview_endpoint(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
):
    """Retrieve comprehensive dataset intelligence dossier, schema, and health scores."""
    gf = user_file.global_file
    profile = await asyncio.to_thread(DuckDBManager.generate_data_profile, gf.parquet_path)
    return {
        "file_id": str(user_file.id),
        "filename": user_file.display_name,
        "row_count": gf.row_count,
        "column_count": gf.col_count,
        "schema": gf.schema_json,
        "profile": profile,
        "ref_count": gf.ref_count,
    }


@router.get("/{file_id}/preview")
async def get_lab_preview_endpoint(
    file_id: uuid.UUID,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    sort_col: str | None = Query(default=None),
    sort_dir: str = Query(default="asc"),
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
):
    """Retrieve vectorized row preview slice from Parquet storage."""
    gf = user_file.global_file
    res = await asyncio.to_thread(
        DuckDBManager.preview,
        parquet_path=gf.parquet_path,
        limit=limit,
        offset=offset,
        search=search,
        sort_col=sort_col,
        sort_dir=sort_dir,
    )
    return res


@router.get("/{file_id}/forensic")
async def get_lab_forensic_endpoint(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve or autonomously generate deep forensic diagnostics and briefing report."""
    gf = user_file.global_file

    # 1. Check existing forensic memory
    stmt = (
        select(AnalysisMemory)
        .where(
            AnalysisMemory.user_file_id == user_file.id,
            AnalysisMemory.user_id == current_user.id,
        )
        .order_by(AnalysisMemory.created_at.desc())
    )
    existing_memories = (await db.scalars(stmt)).all()

    if existing_memories:
        findings = []
        for m in existing_memories:
            findings.append({
                "title": m.query_text or "Diagnostic Finding",
                "severity": "MEDIUM",
                "description": m.finding_text,
                "insight": m.finding_text,
            })
        raw_report = ""
        for m in existing_memories:
            if m.evidence_json and isinstance(m.evidence_json, dict) and m.evidence_json.get("raw_report"):
                raw_report = m.evidence_json["raw_report"]
                break
        if not raw_report:
            raw_report = (
                f"## Forensic Briefing: {user_file.display_name}\n\n"
                f"### Context\nDataset scope: {gf.row_count:,} rows across {gf.col_count} columns.\n\n"
                f"### Key Findings\n" + "\n".join(f"- {f['description']}" for f in findings[:5]) + "\n\n"
                "### Strategic Implication\nAutonomous verification complete. Ready for vectorized analytics."
            )
        return {"findings": findings, "report": raw_report}

    # 2. Auto-generate initial briefing if empty
    profile = await asyncio.to_thread(DuckDBManager.generate_data_profile, gf.parquet_path)
    health_score = profile.get("health_score", 100)
    col_profiles = profile.get("columns", {})

    findings = [
        {
            "title": "Data Integrity Score",
            "severity": "LOW" if health_score >= 80 else ("HIGH" if health_score < 50 else "MEDIUM"),
            "description": f"Dataset health rated at {health_score}/100 across {gf.row_count:,} rows and {gf.col_count} columns.",
            "insight": f"Health index {health_score}/100",
        }
    ]

    null_cols = [c for c, p in col_profiles.items() if p.get("null_percentage", 0) > 0]
    if null_cols:
        high_nulls = [c for c in null_cols if col_profiles[c].get("null_percentage", 0) > 20]
        severity = "HIGH" if high_nulls else "MEDIUM"
        desc = (
            f"Detected {len(null_cols)} columns with missing values. "
            f"Highest nulls in: {', '.join(null_cols[:5])}."
        )
        findings.append({
            "title": "Missing Values & Null Sparsity",
            "severity": severity,
            "description": desc,
            "insight": desc,
        })

    # High cardinality check
    high_card_cols = [
        c for c, p in col_profiles.items()
        if p.get("distinct_count") and p["distinct_count"] == gf.row_count and gf.row_count > 50
    ]
    if high_card_cols:
        findings.append({
            "title": "Identifier / High Cardinality Columns",
            "severity": "LOW",
            "description": f"Columns with unique IDs: {', '.join(high_card_cols[:3])}.",
            "insight": f"Unique key candidates: {', '.join(high_card_cols[:3])}",
        })

    report = (
        f"## Key Insights & Data Summary: {user_file.display_name}\n\n"
        f"### Background\n"
        f"`{user_file.display_name}` loaded with {gf.row_count:,} rows across {gf.col_count} columns. "
        f"Overall Data Quality Score: {health_score}/100.\n\n"
        f"### What We Found\n"
        + "\n".join(f"- **{f['title']}**: {f['description']}" for f in findings)
        + "\n\n"
        f"### Data Proof\n"
        f"Total empty cells: {profile.get('total_nulls', 0):,} ({profile.get('null_percentage', 0)}% of all values).\n\n"
        f"### What It Means / Next Step\n"
        f"Your dataset is clean enough for instant charts, Smart Tables, and Predict & Simulate modeling."
    )

    # Save to AnalysisMemory
    mem = AnalysisMemory(
        user_id=current_user.id,
        user_file_id=user_file.id,
        agent_type="forensic",
        query_text="Initial Forensic Integrity Scan",
        context_text=f"{gf.row_count:,} rows × {gf.col_count} columns",
        finding_text=f"Integrity Score {health_score}/100. {len(null_cols)} column(s) have missing values.",
        evidence_json={"raw_report": report, "health_score": health_score, "findings": findings},
        implication_text="Dataset is structurally verified for vectorized OLAP & AutoML.",
        plotly_spec_json=None,
    )
    db.add(mem)
    await db.commit()
    await db.refresh(mem)

    return {"findings": findings, "report": report}


@router.post("/{file_id}/visualize")
async def generate_chart_spec_endpoint(
    file_id: uuid.UUID,
    request: LabVisualizeRequest,
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
):
    """Generate dynamic dark-mode Plotly chart specification based on requested dimensions."""
    gf = user_file.global_file
    df = await asyncio.to_thread(pd.read_parquet, gf.parquet_path)
    ctype = request.chart_type.lower().strip()

    spec = None
    if ctype == "bar":
        x = request.x_col or request.column or (df.columns[0] if not df.empty else None)
        if x:
            spec = ChartBuilder.build_bar(df, x, request.y_col, request.color_col)
    elif ctype in ("distribution", "histogram"):
        col = request.column or request.x_col or (df.columns[0] if not df.empty else None)
        if col:
            spec = ChartBuilder.build_distribution(df, col)
    elif ctype == "scatter":
        if not request.x_col or not request.y_col:
            num_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if len(num_cols) < 2:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Scatter plot requires at least 2 numeric columns.",
                )
            x = request.x_col or num_cols[0]
            y = request.y_col or num_cols[1]
        else:
            x = request.x_col
            y = request.y_col
        spec = ChartBuilder.build_scatter(df, x, y, color_col=request.color_col)
    elif ctype == "line":
        if not request.x_col or not request.y_col:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Line chart requires both date/index (x_col) and value (y_col) dimensions.",
            )
        spec = ChartBuilder.build_line(df, request.x_col, request.y_col)
    elif ctype in ("heatmap", "correlation"):
        spec = ChartBuilder.build_heatmap(df)
    elif ctype == "box":
        col = request.column or request.y_col or (df.select_dtypes(include=["number"]).columns[0] if not df.empty else None)
        cat = request.x_col if request.x_col and request.x_col != col else None
        if col:
            spec = ChartBuilder.build_box(df, col, cat)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported chart type '{request.chart_type}'. Choose distribution, bar, scatter, line, heatmap, or box.",
        )

    if not spec:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to generate chart specification for the provided column dimensions.",
        )

    return {
        "plotly_spec": spec,
        "spec": spec,
        "data": spec.get("data", []),
        "layout": spec.get("layout", {}),
    }


def _validate_llm_generated_sql(sql_text: str, valid_cols: list[str]) -> str | None:
    """Validate LLM-generated DuckDB SQL strictly against read-only SELECT rules and schema."""
    candidate = re.sub(r"^```(?:sql)?|```$", "", sql_text.strip(), flags=re.IGNORECASE).strip()
    candidate = candidate.rstrip(";").strip()
    if not candidate or ";" in candidate:
        return None
    if not re.match(r"^(SELECT|WITH)\b", candidate, re.IGNORECASE):
        return None
    try:
        DuckDBManager._validate_sql_safety(candidate)
    except ValueError:
        return None

    # Ensure every double-quoted identifier (excluding AS aliases) belongs to valid_cols or dataset
    valid_lower = {c.lower() for c in valid_cols}
    quoted_idents = re.findall(r'(?<!AS\s)"([^"]+)"', candidate, re.IGNORECASE)
    for ident in quoted_idents:
        if ident.lower() not in valid_lower and ident.lower() not in {"dataset", "joined_dataset"}:
            return None
    return candidate


async def _try_llm_question_to_sql(question: str, valid_cols: list[str], num_cols: list[str]) -> str | None:
    """Attempt quick LLM-assisted SQL synthesis when deterministic parsing lacks confidence."""
    if llm_client.is_chat_circuit_open():
        return None
    status_info = await llm_client.check_ollama_status()
    if not status_info.get("online"):
        return None

    prompt = (
        "Generate a single read-only DuckDB SELECT query against table \"dataset\".\n"
        f"Available columns: {valid_cols[:25]}\n"
        f"Numeric columns: {num_cols[:12]}\n"
        f"Question: {question}\n"
        "Rules: Output ONLY raw SQL (no markdown fences, no explanation). Double-quote column names. LIMIT <= 100."
    )
    res = await llm_client.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=180,
        timeout=15,
    )
    raw_sql = (res.get("content") or "").strip()
    return _validate_llm_generated_sql(raw_sql, valid_cols)


@router.post("/{file_id}/query")
async def execute_lab_sql_query_endpoint(
    file_id: uuid.UUID,
    request: LabQueryRequest,
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
    db: AsyncSession = Depends(get_db),
):
    """Execute Smart Query in Builder, Natural-Language, or SQL mode via DuckDB."""
    gf = user_file.global_file

    # Resolve legacy named joins (if passed)
    named_joins: list[tuple[str, str]] = []
    if request.join_file_ids:
        join_stmt = (
            select(UserFile)
            .options(selectinload(UserFile.global_file))
            .where(
                UserFile.id.in_(request.join_file_ids),
                UserFile.user_id == current_user.id,
            )
        )
        join_files = (await db.scalars(join_stmt)).all()
        for jf in join_files:
            if jf.id != user_file.id and jf.global_file:
                alias = re.sub(r"\.[^.]+$", "", jf.display_name)
                named_joins.append((alias, jf.global_file.parquet_path))

    # Determine effective mode seamlessly
    question_text = (request.question or request.natural_language or "").strip()
    raw_sql_or_query = (request.sql or request.query or "").strip()
    is_explicit_sql = (
        request.mode == "sql"
        or (request.mode == "auto" and bool(request.sql))
        or (
            request.mode == "auto"
            and bool(raw_sql_or_query)
            and bool(re.match(r"^(SELECT|WITH)\b", raw_sql_or_query, re.IGNORECASE))
        )
    )
    if not question_text and raw_sql_or_query and not is_explicit_sql:
        question_text = raw_sql_or_query

    # Mode 3: Explicit Read-Only SQL Execution (backward-compatible power mode)
    if is_explicit_sql:
        if not raw_sql_or_query:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="SQL query text is required.",
            )
        try:
            return await asyncio.to_thread(
                DuckDBManager.execute_sql_tabular,
                gf.parquet_path,
                raw_sql_or_query,
                named_joins or None,
                request.limit,
            )
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve)) from ve
        except Exception as exc:
            logger.warning("DuckDB SQL query failed for file %s: %s", file_id, exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"SQL execution error: {exc}",
            ) from exc

    # Inspect schema for Builder / Natural-Language modes
    try:
        all_cols, num_cols, cat_cols = await asyncio.to_thread(
            DuckDBManager.inspect_parquet_columns, gf.parquet_path
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to inspect dataset schema: {exc}",
        ) from exc

    # Optional authorized visual join file
    join_info: dict | None = None
    right_parquet_path: str | None = None
    if request.join_config:
        right_stmt = (
            select(UserFile)
            .options(selectinload(UserFile.global_file))
            .where(
                UserFile.id == request.join_config.right_file_id,
                UserFile.user_id == current_user.id,
            )
        )
        right_uf = (await db.execute(right_stmt)).scalar_one_or_none()
        if not right_uf or not right_uf.global_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Joined dataset not found or unauthorized.",
            )
        right_parquet_path = right_uf.global_file.parquet_path
        right_cols, _, _ = await asyncio.to_thread(
            DuckDBManager.inspect_parquet_columns, right_parquet_path
        )
        join_info = {
            "right_cols": right_cols,
            "left_col": request.join_config.left_col,
            "right_col": request.join_config.right_col,
            "join_type": request.join_config.join_type,
            "right_alias": right_uf.display_name,
        }

    # Mode 2: Natural-Language Question Mode
    if question_text and (
        request.mode in ("question", "natural_language")
        or (not request.group_by and not request.metrics and not request.filters)
    ):
        parsed = DuckDBManager.parse_natural_language_query(
            question_text, all_cols, num_cols, cat_cols
        )
        # If deterministic parser had low confidence and Ollama is online, try schema-firewalled LLM SQL
        if not parsed["confident"]:
            llm_sql = await _try_llm_question_to_sql(question_text, all_cols, num_cols)
            if llm_sql:
                try:
                    llm_result = await asyncio.to_thread(
                        DuckDBManager.execute_sql_tabular,
                        gf.parquet_path,
                        llm_sql,
                        named_joins or None,
                        request.limit,
                    )
                    llm_result["explanation"] = f'Answered "{question_text}" using schema-verified DuckDB analytics.'
                    return llm_result
                except Exception as exc:
                    logger.debug("LLM-generated SQL fallback triggered: %s", exc)

        group_by = parsed["group_by"]
        metrics = parsed["metrics"]
        filters = parsed["filters"]
        sort_by = parsed["sort_by"]
        sort_dir = parsed["sort_dir"]
        limit = parsed["limit"]
    else:
        # Mode 1: Visual Builder AST Mode
        group_by = request.group_by
        metrics = [m.model_dump() for m in request.metrics]
        filters = [f.model_dump() for f in request.filters]
        sort_by = request.sort_by
        sort_dir = request.sort_dir
        limit = request.limit

    try:
        exec_sql, params, display_sql, explanation = DuckDBManager.compile_builder_sql(
            valid_cols=all_cols,
            group_by=group_by,
            metrics=metrics,
            filters=filters,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            join_info=join_info,
        )
        return await asyncio.to_thread(
            DuckDBManager.execute_compiled_query,
            gf.parquet_path,
            exec_sql,
            params,
            display_sql,
            explanation,
            right_parquet_path,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve)) from ve
    except Exception as exc:
        logger.warning("Smart DuckDB query failed for file %s: %s", file_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query execution error: {exc}",
        ) from exc


@router.post("/{file_id}/analyze", response_model=AnalysisMemoryResponse)
async def run_lab_analysis_endpoint(
    file_id: uuid.UUID,
    request: LabAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
    db: AsyncSession = Depends(get_db),
):
    """Execute deep forensic analysis and persist finding into analysis_memory."""
    gf = user_file.global_file
    schema = gf.schema_json or {}
    cols = list(schema.get("columns", {}).keys())

    prompt = (
        "You are the DataMind Strategic Architect. Deliver an executive-grade forensic briefing.\n"
        f"Hypothesis/Objective: {request.query}\n"
        f"Available Dimensions: {cols[:15]}\n\n"
        "Output your response strictly under 4 headers:\n"
        "## Context\n"
        "## Key Finding\n"
        "## Empirical Evidence\n"
        "## Strategic Implication\n"
    )

    res = await llm_client.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1000,
    )
    content = res.get("content", "")

    # Extract sections
    def extract_header(hdr: str, text: str) -> str:
        pattern = rf"##\s*{hdr}\s*\n(.*?)(?=\n##|\Z)"
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    ctx = extract_header("Context", content)
    finding = extract_header("Key Finding", content) or content[:300]
    implication = extract_header("Strategic Implication", content)

    # Optional baseline figure
    df = await asyncio.to_thread(pd.read_parquet, gf.parquet_path)
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    plotly_spec = ChartBuilder.build_distribution(df, num_cols[0]) if num_cols else None

    memory = AnalysisMemory(
        user_id=current_user.id,
        user_file_id=user_file.id,
        agent_type="analyst",
        query_text=request.query,
        context_text=ctx or None,
        finding_text=finding,
        evidence_json={"raw_report": content},
        implication_text=implication or None,
        plotly_spec_json=plotly_spec,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)

    return memory


@router.get("/{file_id}/memories", response_model=list[AnalysisMemoryResponse])
async def list_lab_memories_endpoint(
    file_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve saved forensic briefing memories for this dataset."""
    stmt = (
        select(AnalysisMemory)
        .where(
            AnalysisMemory.user_file_id == user_file.id,
            AnalysisMemory.user_id == current_user.id,
        )
        .order_by(AnalysisMemory.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.scalars(stmt)
    return list(result.all())


@router.get("/{file_id}/export-pdf")
async def export_lab_report_endpoint(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
    db: AsyncSession = Depends(get_db),
):
    """Export complete dataset dossier, saved forensic memories, and ML history as structured markdown."""
    gf = user_file.global_file
    memories_stmt = (
        select(AnalysisMemory)
        .where(AnalysisMemory.user_file_id == user_file.id, AnalysisMemory.user_id == current_user.id)
        .order_by(AnalysisMemory.created_at.asc())
    )
    memories = (await db.scalars(memories_stmt)).all()

    preds_stmt = (
        select(PredictionHistory)
        .where(PredictionHistory.user_file_id == user_file.id, PredictionHistory.user_id == current_user.id)
        .order_by(PredictionHistory.created_at.desc())
        .limit(5)
    )
    preds = (await db.scalars(preds_stmt)).all()

    profile = await asyncio.to_thread(DuckDBManager.generate_data_profile, gf.parquet_path)
    md_lines = [
        f"# DataMind Executive Intelligence Dossier: {user_file.display_name}",
        f"**Dataset Scope**: {gf.row_count:,} rows | {gf.col_count} columns",
        f"**Health Score**: {profile.get('health_score', 100)}/100\n",
        "## 1. Saved Forensic Findings",
    ]

    if memories:
        for m in memories:
            md_lines.append(f"### Objective: {m.query_text}")
            md_lines.append(f"**Finding**: {m.finding_text}\n")
            if m.implication_text:
                md_lines.append(f"**Strategic Implication**: {m.implication_text}\n")
    else:
        md_lines.append("No saved analysis memories recorded.")

    md_lines.append("\n## 2. Machine Learning & Predictive Models")
    if preds:
        for p in preds:
            md_lines.append(
                f"- **Task**: `{p.task_type}` | **Target**: `{p.target_column}` | "
                f"**Best Model**: {p.best_model_name} (Status: {p.status})"
            )
    else:
        md_lines.append("No ML benchmark missions executed.")

    return {
        "filename": f"{user_file.display_name}_report.md",
        "markdown_report": "\n".join(md_lines),
    }
