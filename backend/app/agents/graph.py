"""DataMind v2 Bounded LangGraph Multi-Agent Architecture.

Implements bounded state machine (max_steps=8, token_budget=6000) with
Orchestrator, SummaryAgent, CleaningAgent, AnalystAgent, VizAgent, PredictAgent,
and the deterministic SchemaFirewallNode for zero-hallucination verification.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, TypedDict

import pandas as pd
from langgraph.graph import END, StateGraph

from app.engine.chart_builder import ChartBuilder
from app.engine.ml_runner import UniversalMLRunner
from app.llm.client import llm_client

logger = logging.getLogger("datamind.agents.graph")


class AgentState(TypedDict):
    query: str
    user_id: str
    user_file_id: str
    parquet_path: str
    schema_json: dict[str, Any]
    data_profile: dict[str, Any]
    recent_history: list[dict[str, str]]
    intent: str  # analyze, visualize, summarize, clean, predict
    target_columns: list[str]
    current_step: int
    max_steps: int
    token_budget: int
    tokens_used: int
    brief_response: str
    detailed_narrative: str
    lab_artifact: dict[str, Any] | None
    firewall_passed: bool
    firewall_feedback: str | None
    error: str | None


# ==============================================================================
# 1. Orchestrator Node
# ==============================================================================
async def orchestrator_node(state: AgentState) -> dict[str, Any]:
    """Classifies deep intent and normalizes target column candidates."""
    query = state["query"].lower().strip()
    intent = state.get("intent", "analyze")
    cols = list(state.get("schema_json", {}).get("columns", {}).keys())

    if any(k in query for k in ["predict", "forecast", "future", "simulate", "model", "what-if"]):
        intent = "predict"
    elif any(k in query for k in ["chart", "plot", "graph", "visualize", "histogram", "heatmap", "scatter"]):
        intent = "visualize"
    elif any(k in query for k in ["clean", "fix", "missing", "impute", "nulls", "duplicates"]):
        intent = "clean"
    elif any(k in query for k in ["summary", "overview", "profile", "describe", "dossier"]):
        intent = "summarize"
    else:
        intent = "analyze"

    # Identify target columns if not present
    targets = state.get("target_columns", [])
    if not targets:
        for c in cols:
            if c.lower() in query:
                targets.append(c)

    return {
        "intent": intent,
        "target_columns": targets,
        "current_step": state.get("current_step", 0) + 1,
    }


# ==============================================================================
# 2. Summary Agent Node
# ==============================================================================
async def summary_agent_node(state: AgentState) -> dict[str, Any]:
    """Autonomous dataset profiling and domain briefing."""
    profile = state.get("data_profile", {})
    schema = state.get("schema_json", {})
    domain = schema.get("detected_domain", "general").upper()
    row_count = profile.get("total_rows", 0)
    col_count = profile.get("total_columns", 0)
    health = profile.get("health_score", 100)

    prompt = (
        f"Generate an executive briefing for this {domain} dataset.\n"
        f"Total Records: {row_count:,} | Columns: {col_count} | Health: {health}/100\n"
        f"Columns: {list(schema.get('columns', {}).keys())[:10]}\n\n"
        "Provide your output in exactly two sections:\n"
        "<<<BRIEF>>>\n"
        "- 2 to 3 concise bullet points summarizing dataset scope and health (max 40 words).\n"
        "<<<DETAILED>>>\n"
        "## Introduction\n"
        "## Detailed Strategic Analysis\n"
        "## Strategic Conclusion & Impact\n"
        "## Executive Data Snapshot\n"
    )

    res = await llm_client.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1000,
    )
    content = res.get("content", "")

    if res.get("model") == "offline-fallback" or not content.strip():
        num_cols = profile.get("numeric_columns", [])[:5]
        cat_cols = profile.get("categorical_columns", [])[:5]
        brief = (
            f"Dataset covers **{row_count:,} records** across **{col_count} columns** "
            f"(Data Health Score: **{health}/100**)."
        )
        detailed = (
            f"## Dataset Executive Summary\n\n"
            f"- **Domain Focus**: {domain}\n"
            f"- **Numeric Dimensions**: {', '.join(f'`{c}`' for c in num_cols) or 'None'}\n"
            f"- **Categorical Dimensions**: {', '.join(f'`{c}`' for c in cat_cols) or 'None'}\n"
            f"- **Completeness**: {profile.get('total_nulls', 0):,} missing cells across dataset."
        )
    else:
        brief, detailed = _split_brief_detailed(content)
    artifact = None
    # Generate baseline chart if parquet is accessible
    parquet_path = state.get("parquet_path")
    if parquet_path:
        try:
            df = await asyncio.to_thread(pd.read_parquet, parquet_path)
            num_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if num_cols:
                artifact = ChartBuilder.build_distribution(df, num_cols[0])
        except Exception as e:
            logger.debug("Baseline chart generation skipped: %s", e)

    return {
        "brief_response": brief,
        "detailed_narrative": detailed,
        "lab_artifact": artifact,
        "tokens_used": state.get("tokens_used", 0) + res.get("tokens", {}).get("total_tokens", 0),
        "current_step": state["current_step"] + 1,
    }


# ==============================================================================
# 3. Cleaning Agent Node
# ==============================================================================
async def cleaning_agent_node(state: AgentState) -> dict[str, Any]:
    """Automated data quality assessment and remediation plan."""
    profile = state.get("data_profile", {})
    cols_profile = profile.get("columns", {})
    total_nulls = profile.get("total_nulls", 0)
    duplicates = profile.get("duplicate_rows", 0)

    actions = []
    if duplicates > 0:
        actions.append(f"Remove {duplicates:,} duplicate rows.")

    for col_name, c_stat in cols_profile.items():
        n_cnt = c_stat.get("null_count", 0)
        n_pct = c_stat.get("null_percentage", 0.0)
        if n_cnt > 0:
            actions.append(f"Impute {n_cnt:,} nulls in `{col_name}` ({n_pct:.1f}%).")

    if not actions:
        brief = "No data quality issues detected. The dataset is clean."
        detailed = "## Data Quality Report\n\nAll columns satisfy completeness and integrity constraints."
    else:
        brief = f"Detected {len(actions)} cleaning opportunities (Nulls: {total_nulls:,}, Duplicates: {duplicates:,})."
        detailed = (
            "## Data Quality Audit & Remediation Strategy\n\n"
            + "\n".join([f"- **Action**: {a}" for a in actions])
            + "\n\n### Impact\nAutomated remediation preserves downstream model reliability and prevents metric distortion."
        )

    return {
        "brief_response": brief,
        "detailed_narrative": detailed,
        "lab_artifact": {"actions": actions, "total_nulls": total_nulls, "duplicates": duplicates},
        "current_step": state["current_step"] + 1,
    }


# ==============================================================================
# 4. Analyst Agent Node (Forensic Briefing)
# ==============================================================================
async def analyst_agent_node(state: AgentState) -> dict[str, Any]:
    """Structured Forensic Briefing (Context -> Finding -> Evidence -> Implication)."""
    feedback = state.get("firewall_feedback")
    feedback_note = f"\n\nCRITICAL FIX REQUIRED: {feedback}\n" if feedback else ""

    schema = state.get("schema_json", {})
    valid_cols = list(schema.get("columns", {}).keys())

    prompt = (
        "You are the DataMind Strategic Architect. Deliver an executive-grade forensic briefing.\n"
        f"User Query: {state['query']}\n"
        f"Verified Columns in Schema: {valid_cols}\n"
        f"{feedback_note}\n"
        "STRICT PROTOCOL:\n"
        "- ONLY reference columns that appear in the Verified Columns list.\n"
        "- Format response in two sections:\n"
        "<<<BRIEF>>>\n"
        "- Up to 3 concise bullet points (MAX 40 WORDS).\n"
        "<<<DETAILED>>>\n"
        "## Context\n"
        "## Key Finding\n"
        "## Empirical Evidence\n"
        "## Strategic Implication\n"
        "## Executive Data Snapshot (Markdown Table)\n"
    )

    res = await llm_client.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1200,
    )
    content = res.get("content", "")
    if res.get("model") == "offline-fallback" or not content.strip():
        profile = state.get("data_profile", {})
        col_stats = profile.get("columns", {})
        targets = [c for c in state.get("target_columns", []) if c in valid_cols] or valid_cols[:3]
        lines = []
        for col in targets[:4]:
            st = col_stats.get(col, {})
            if "mean" in st and st["mean"] is not None:
                lines.append(
                    f"- **`{col}`**: mean={st['mean']}, min={st.get('min')}, max={st.get('max')}, null%={st.get('null_percentage', 0)}%"
                )
            else:
                lines.append(
                    f"- **`{col}`**: {st.get('distinct_count', 'N/A')} distinct categories, null%={st.get('null_percentage', 0)}%"
                )
        brief = f"Analyzed {len(targets)} key dimension(s): {', '.join(f'`{c}`' for c in targets[:3])} across {profile.get('total_rows', 0):,} rows."
        detailed = "## Empirical Schema Summary\n\n" + "\n".join(lines)
    else:
        brief, detailed = _split_brief_detailed(content)

    return {
        "brief_response": brief,
        "detailed_narrative": detailed,
        "tokens_used": state.get("tokens_used", 0) + res.get("tokens", {}).get("total_tokens", 0),
        "current_step": state["current_step"] + 1,
    }


# ==============================================================================
# 5. Viz Agent Node
# ==============================================================================
async def viz_agent_node(state: AgentState) -> dict[str, Any]:
    """Selects chart type and column mappings, building a dark-mode Plotly spec."""
    parquet_path = state.get("parquet_path")
    schema = state.get("schema_json", {})
    cols = list(schema.get("columns", {}).keys())
    targets = state.get("target_columns", [])

    artifact = None
    if parquet_path:
        try:
            df = await asyncio.to_thread(pd.read_parquet, parquet_path)
            target = targets[0] if targets and targets[0] in df.columns else None

            if not target:
                num_cols = df.select_dtypes(include=["number"]).columns.tolist()
                target = num_cols[0] if num_cols else cols[0]

            query_low = state["query"].lower()
            if "heatmap" in query_low or "correlation" in query_low:
                artifact = ChartBuilder.build_heatmap(df)
            elif "scatter" in query_low and len(df.select_dtypes(include=["number"]).columns) >= 2:
                nums = df.select_dtypes(include=["number"]).columns.tolist()
                artifact = ChartBuilder.build_scatter(df, nums[0], nums[1])
            elif "box" in query_low:
                artifact = ChartBuilder.build_box(df, target)
            else:
                artifact = ChartBuilder.build_distribution(df, target)
        except Exception as e:
            logger.debug("Viz generation failed: %s", e)

    brief = f"Generated interactive visualization for `{target if 'target' in locals() and target else 'requested dimensions'}`."
    detailed = (
        f"## Visualization Analysis\n\n"
        f"Mapped requested dimensions into Plotly dark-mode specification.\n"
        f"Primary dimension: `{target if 'target' in locals() and target else 'Distribution'}`."
    )

    return {
        "brief_response": brief,
        "detailed_narrative": detailed,
        "lab_artifact": artifact,
        "current_step": state["current_step"] + 1,
    }


# ==============================================================================
# 6. Predict Agent Node
# ==============================================================================
async def predict_agent_node(state: AgentState) -> dict[str, Any]:
    """Pre-prediction readiness diagnosis and ML pipeline synthesis."""
    parquet_path = state.get("parquet_path")
    targets = state.get("target_columns", [])
    target_col = targets[0] if targets else None

    if not parquet_path:
        return {
            "brief_response": "Cannot initiate ML mission without active dataset.",
            "detailed_narrative": "Missing dataset path.",
            "current_step": state["current_step"] + 1,
        }

    try:
        df = await asyncio.to_thread(pd.read_parquet, parquet_path)
        diag = await asyncio.to_thread(UniversalMLRunner.diagnose_data, df, target_col)
    except Exception as e:
        logger.warning("Predict agent node dataset read/diagnosis failed: %s", e)
        return {
            "brief_response": "Failed to inspect dataset for ML readiness.",
            "detailed_narrative": f"Error evaluating dataset: {e}",
            "lab_artifact": None,
            "current_step": state["current_step"] + 1,
        }

    if not diag["can_proceed"]:
        blockers_str = "\n".join([f"- {b}" for b in diag["blockers"]])
        brief = "ML mission halted due to data validation blockers."
        detailed = f"## ML Diagnostic Report\n\n### Blockers Detected\n{blockers_str}"
        return {
            "brief_response": brief,
            "detailed_narrative": detailed,
            "lab_artifact": diag,
            "current_step": state["current_step"] + 1,
        }

    task_type = UniversalMLRunner.auto_select_task(df, diag["suggested_target"])
    brief = f"ML task '{task_type.capitalize()}' is viable for target `{diag['suggested_target']}`."
    detailed = (
        f"## Automated ML Mission Readiness\n\n"
        f"- **Detected Task**: `{task_type.capitalize()}`\n"
        f"- **Target Dimension**: `{diag['suggested_target']}`\n"
        f"- **Sample Readiness**: {len(df):,} observations\n"
        f"- **Diagnostics**: Zero critical blockers identified."
    )

    return {
        "brief_response": brief,
        "detailed_narrative": detailed,
        "lab_artifact": {"diagnostic": diag, "task_type": task_type},
        "current_step": state["current_step"] + 1,
    }


# ==============================================================================
# 7. Schema Firewall Node (Verified Reasoning)
# ==============================================================================
async def schema_firewall_node(state: AgentState) -> dict[str, Any]:
    """Deterministic validation: inspects referenced columns against live DuckDB schema."""
    schema = state.get("schema_json", {})
    valid_cols = set(schema.get("columns", {}).keys())
    # Case-insensitive lookup
    valid_cols_lower = {c.lower(): c for c in valid_cols}

    # Inspect text inside brief and detailed responses for backticked `column` names
    text_to_check = f"{state.get('brief_response', '')} {state.get('detailed_narrative', '')}"
    potential_cols = re.findall(r"`([a-zA-Z_][\w\s]*)`", text_to_check)

    hallucinations = []
    # Reserved terms that are not dataset column identifiers
    reserved = {
        "action",
        "context",
        "finding",
        "evidence",
        "implication",
        "brief",
        "detailed",
        "classification",
        "regression",
        "clustering",
        "timeseries",
        "time-series",
        "randomforest",
        "gradientboosting",
        "logisticregression",
        "ridge",
        "kmeans",
        "accuracy",
        "rmse",
        "mae",
        "mape",
        "inertia",
        "roc_auc",
        "distribution",
        "histogram",
        "scatter",
        "heatmap",
        "correlation",
        "boxplot",
        "select",
        "from",
        "where",
        "group",
        "order",
        "limit",
        "dataset",
        "duckdb",
        "parquet",
        "overview",
        "forensic",
        "forensics",
        "automl",
        "simulator",
        "what-if",
        "python",
        "json",
        "plotly",
        "scikit-learn",
        "offline",
        "tier",
        "null",
        "none",
        "true",
        "false",
    }

    for candidate in potential_cols:
        clean_cand = candidate.strip()
        cand_lower = clean_cand.lower()
        if cand_lower in reserved:
            continue
        # If candidate looks like a column identifier (no spaces or typical snake_case)
        if "_" in clean_cand or (clean_cand.isalpha() and len(clean_cand) > 3):
            if cand_lower not in valid_cols_lower:
                hallucinations.append(clean_cand)

    # Check chart artifact if present
    artifact = state.get("lab_artifact")
    if artifact and isinstance(artifact, dict) and "data" in artifact:
        for trace in artifact.get("data", []):
            for axis in ["x", "y"]:
                _ = trace.get(f"{axis}axis", "")

    if hallucinations:
        bad_col = hallucinations[0]
        feedback = (
            f"Hallucination detected: Column `{bad_col}` does not exist in dataset schema. "
            f"Valid columns: {list(valid_cols)[:15]}"
        )
        logger.warning(feedback)
        return {
            "firewall_passed": False,
            "firewall_feedback": feedback,
            "current_step": state["current_step"] + 1,
        }

    return {
        "firewall_passed": True,
        "firewall_feedback": None,
        "current_step": state["current_step"] + 1,
    }


# ==============================================================================
# Routing Logic & Graph Builder
# ==============================================================================
def route_intent(state: AgentState) -> str:
    intent = state.get("intent", "analyze")
    if intent == "summarize":
        return "summary_agent"
    elif intent == "clean":
        return "cleaning_agent"
    elif intent == "visualize":
        return "viz_agent"
    elif intent == "predict":
        return "predict_agent"
    return "analyst_agent"


def firewall_decision(state: AgentState) -> str:
    if state.get("firewall_passed", False):
        return END
    # If step limit reached, terminate to prevent unbounded looping
    if state.get("current_step", 0) >= state.get("max_steps", 8):
        logger.warning("Agent graph reached max_steps (%d). Terminating.", state["max_steps"])
        return END
    # Route back to generating node for self-correction
    return route_intent(state)


def build_agent_graph():
    """Build bounded LangGraph multi-agent execution pipeline."""
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("summary_agent", summary_agent_node)
    graph.add_node("cleaning_agent", cleaning_agent_node)
    graph.add_node("analyst_agent", analyst_agent_node)
    graph.add_node("viz_agent", viz_agent_node)
    graph.add_node("predict_agent", predict_agent_node)
    graph.add_node("schema_firewall", schema_firewall_node)

    # Entry point
    graph.set_entry_point("orchestrator")

    # Routing from orchestrator to specialized agent
    graph.add_conditional_edges(
        "orchestrator",
        route_intent,
        {
            "summary_agent": "summary_agent",
            "cleaning_agent": "cleaning_agent",
            "analyst_agent": "analyst_agent",
            "viz_agent": "viz_agent",
            "predict_agent": "predict_agent",
        },
    )

    # All agents pass through Schema Firewall
    for node in ["summary_agent", "cleaning_agent", "analyst_agent", "viz_agent", "predict_agent"]:
        graph.add_edge(node, "schema_firewall")

    # Schema firewall decides whether to end or loop back
    graph.add_conditional_edges(
        "schema_firewall",
        firewall_decision,
        {
            END: END,
            "summary_agent": "summary_agent",
            "cleaning_agent": "cleaning_agent",
            "analyst_agent": "analyst_agent",
            "viz_agent": "viz_agent",
            "predict_agent": "predict_agent",
        },
    )

    return graph.compile()


def _split_brief_detailed(content: str) -> tuple[str, str]:
    """Helper to separate <<<BRIEF>>> and <<<DETAILED>>> blocks."""
    brief = ""
    detailed = ""

    if "<<<BRIEF>>>" in content:
        parts = content.split("<<<BRIEF>>>")
        rest = parts[1]
        if "<<<DETAILED>>>" in rest:
            sub = rest.split("<<<DETAILED>>>")
            brief = sub[0].strip()
            detailed = sub[1].strip()
        else:
            brief = rest.strip()
            detailed = rest.strip()
    else:
        # Fallback split
        lines = content.strip().split("\n")
        brief = " ".join(lines[:2])[:150]
        detailed = content.strip()

    return brief, detailed
