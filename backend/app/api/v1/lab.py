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
        f"## Forensic Integrity Briefing: {user_file.display_name}\n\n"
        f"### Context\n"
        f"Vectorized ingestion completed for `{user_file.display_name}` ({gf.row_count:,} rows, {gf.col_count} dimensions). "
        f"Overall dataset integrity evaluated at {health_score}/100.\n\n"
        f"### Key Findings\n"
        + "\n".join(f"- **{f['title']}**: {f['description']}" for f in findings)
        + "\n\n"
        f"### Empirical Evidence\n"
        f"Total missing cells: {profile.get('total_nulls', 0):,} ({profile.get('null_percentage', 0)}% of dataset). "
        f"Memory footprint optimized in zero-copy Parquet.\n\n"
        f"### Strategic Implication\n"
        f"Dataset is structurally validated for automated feature selection, statistical hypothesis tests, and AutoML benchmarking."
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
    if ctype in ("distribution", "histogram", "bar"):
        col = request.column or (df.columns[0] if not df.empty else None)
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
        spec = ChartBuilder.build_scatter(df, x, y)
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
        col = request.column or (df.select_dtypes(include=["number"]).columns[0] if not df.empty else None)
        if col:
            spec = ChartBuilder.build_box(df, col, request.x_col)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported chart type '{request.chart_type}'. Choose distribution, scatter, line, heatmap, or box.",
        )

    if not spec:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to generate chart specification for the provided column dimensions.",
        )

    return spec


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
