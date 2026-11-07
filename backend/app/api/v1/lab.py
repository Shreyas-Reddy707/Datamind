"""DataMind v2 Analysis Laboratory Router.

Comprehensive dataset overview, deep forensic analysis persistence (AnalysisMemory),
dynamic Plotly chart spec builder, and executive report export.
"""

from __future__ import annotations

import logging
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
    return {
        "file_id": str(user_file.id),
        "filename": user_file.display_name,
        "row_count": gf.row_count,
        "column_count": gf.col_count,
        "schema": gf.schema_json,
        "profile": DuckDBManager.generate_data_profile(gf.parquet_path),
        "ref_count": gf.ref_count,
    }


@router.post("/{file_id}/visualize")
async def generate_chart_spec_endpoint(
    file_id: uuid.UUID,
    request: LabVisualizeRequest,
    current_user: User = Depends(get_current_user),
    user_file: UserFile = Depends(get_authorized_user_file),
):
    """Generate dynamic dark-mode Plotly chart specification based on requested dimensions."""
    gf = user_file.global_file
    df = pd.read_parquet(gf.parquet_path)
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

    import re

    ctx = extract_header("Context", content)
    finding = extract_header("Key Finding", content) or content[:300]
    implication = extract_header("Strategic Implication", content)

    # Optional baseline figure
    df = pd.read_parquet(gf.parquet_path)
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

    profile = DuckDBManager.generate_data_profile(gf.parquet_path)
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
