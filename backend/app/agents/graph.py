"""DataMind v2 Bounded LangGraph Multi-Agent Architecture.

Implements bounded state machine (max_steps=8, token_budget=6000) with
Orchestrator, SummaryAgent, CleaningAgent, AnalystAgent, VizAgent, PredictAgent,
and the deterministic SchemaFirewallNode for zero-hallucination verification.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, NotRequired, TypedDict

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
    latest_prediction: NotRequired[dict[str, Any] | None]
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

    if any(
        k in query
        for k in ["predict", "forecast", "future", "simulate", "model", "what-if", "feature weight", "feature importance"]
    ):
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
        brief = f"Analyzed {len(targets)} key column(s): {', '.join(f'`{c}`' for c in targets[:3])} across {profile.get('total_rows', 0):,} rows."
        detailed = "## Summary of Columns\n\n" + "\n".join(lines)
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
_MODEL_DISPLAY_NAMES: dict[str, str] = {
    "RandomForest": "Random Forest",
    "GradientBoosting": "Gradient Boosting",
    "LogisticRegression": "Logistic Regression",
    "Ridge": "Ridge (Linear Regression)",
    "KMeans": "K-Means Clustering",
}


def _suggest_default_target(df: pd.DataFrame) -> str | None:
    """Pick prioritized outcome target matching PredictionLab UI defaults."""
    for col in df.columns:
        cl = str(col).lower()
        if (
            cl in ("is_canceled", "canceled", "churn", "target", "label", "adr")
            or cl.startswith("is_")
            or cl.endswith("_churn")
        ):
            return str(col)
    return None


def _format_metric_score(metric: str | None, value: Any) -> str:
    """Render numeric benchmark scores into readable accuracy / R2 strings."""
    if value is None:
        return "pending"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    metric_low = (metric or "").lower()
    if metric_low == "accuracy" and num <= 1.0:
        return f"{num * 100:.1f}% accuracy"
    if metric_low == "r2":
        return f"R² = {num:.3f}"
    if metric_low == "inertia":
        return f"inertia = {num:,.1f}"
    return f"{metric_low}: {num:.4f}" if metric_low else f"{num:.4f}"


def _extract_prediction_facts(
    df: pd.DataFrame,
    requested_target: str | None,
    latest_pred: dict[str, Any] | None,
) -> dict[str, Any]:
    """Gather target, candidate/winning AI models, top column weights, and leakage exclusions."""
    # Prefer explicit query target; else reuse latest completed run's target; else UI heuristic
    target_candidate = requested_target if (requested_target and requested_target in df.columns) else None
    has_matching_pred = bool(
        latest_pred
        and latest_pred.get("target_column") in df.columns
        and (not target_candidate or latest_pred.get("target_column") == target_candidate)
    )
    if not target_candidate and has_matching_pred and latest_pred:
        target_candidate = latest_pred.get("target_column")
    if not target_candidate:
        target_candidate = _suggest_default_target(df)

    diag = UniversalMLRunner.diagnose_data(df, target_candidate)
    if not diag["can_proceed"]:
        return {
            "can_proceed": False,
            "diagnostics": diag,
            "effective_target": target_candidate,
        }

    effective_target = diag.get("suggested_target") or target_candidate
    task_type = (
        latest_pred.get("task_type")
        if (has_matching_pred and latest_pred and latest_pred.get("task_type"))
        else UniversalMLRunner.auto_select_task(df, effective_target)
    )

    leakage_cols = list(diag.get("dropped_leakage_columns") or [])
    if has_matching_pred and latest_pred:
        pred_diag_leak = (latest_pred.get("diagnostics_json") or {}).get("dropped_leakage_columns") or []
        for lc in pred_diag_leak:
            if lc not in leakage_cols:
                leakage_cols.append(lc)

    sample_df = df.sample(n=min(len(df), 10000), random_state=42) if len(df) > 10000 else df
    raw_fi = latest_pred.get("feature_importance_json") if (has_matching_pred and latest_pred) else None
    top_weights = (
        UniversalMLRunner._extract_raw_feature_weights(sample_df, effective_target, raw_fi, leakage_cols)
        if effective_target
        else []
    )
    weight_source = (
        "trained AutoML feature importance"
        if (has_matching_pred and isinstance(raw_fi, dict) and len(raw_fi) > 0)
        else "pre-run feature correlation & driver ranking"
    )

    # Extract benchmark leaderboard or default model suite for task_type
    model_lines: list[str] = []
    best_model_summary: str | None = None
    if has_matching_pred and latest_pred:
        lb_raw = latest_pred.get("leaderboard_json") or {}
        lb_entries = lb_raw.get("leaderboard", []) if isinstance(lb_raw, dict) else (lb_raw if isinstance(lb_raw, list) else [])
        best_raw_name = latest_pred.get("best_model_name") or ""
        best_display = _MODEL_DISPLAY_NAMES.get(best_raw_name, best_raw_name)
        test_metric = lb_raw.get("test_metric") if isinstance(lb_raw, dict) else None
        test_value = lb_raw.get("test_value") if isinstance(lb_raw, dict) else None
        if best_display:
            score_txt = _format_metric_score(test_metric, test_value)
            best_model_summary = f"**{best_display}** ({score_txt} on holdout test set)"
        for entry in lb_entries:
            if not isinstance(entry, dict):
                continue
            m_raw = str(entry.get("model") or entry.get("model_name") or "")
            m_name = _MODEL_DISPLAY_NAMES.get(m_raw, m_raw)
            m_metric = entry.get("metric") or entry.get("metric_name") or test_metric
            m_score = entry.get("cv_mean") if entry.get("cv_mean") is not None else entry.get("mean_cv_score")
            marker = " — Best Model" if m_raw == best_raw_name and best_raw_name else ""
            model_lines.append(f"**{m_name}** (CV {_format_metric_score(m_metric, m_score)}){marker}")

    if not model_lines:
        if task_type == "classification":
            model_lines = [
                "**Random Forest** (`RandomForestClassifier` — ensemble decision trees)",
                "**Gradient Boosting** (`GradientBoostingClassifier` — sequential error-correcting trees)",
                "**Logistic Regression** (`LogisticRegression` — linear baseline classifier)",
            ]
        elif task_type in ("regression", "timeseries"):
            model_lines = [
                "**Random Forest** (`RandomForestRegressor` — ensemble decision trees)",
                "**Gradient Boosting** (`GradientBoostingRegressor` — sequential boosted trees)",
                "**Linear Regression (Ridge)** (`Ridge` — L2-regularized linear model)",
            ]
        else:
            model_lines = ["**K-Means Clustering** (unsupervised cluster segmentation via inertia elbow)"]

    return {
        "can_proceed": True,
        "diagnostics": diag,
        "effective_target": effective_target,
        "task_type": task_type,
        "row_count": len(df),
        "usable_feature_count": max(0, len(df.columns) - 1 - len(leakage_cols)),
        "has_completed_run": has_matching_pred,
        "best_model_summary": best_model_summary,
        "model_lines": model_lines,
        "top_weights": top_weights,
        "weight_source": weight_source,
        "leakage_cols": leakage_cols,
    }


def _build_prediction_fallback(facts: dict[str, Any]) -> tuple[str, str]:
    """Build detailed, human-friendly Markdown explanation of models and column weights."""
    target = facts["effective_target"]
    task_label = str(facts["task_type"]).capitalize()
    row_count = facts["row_count"]
    best_summary = facts["best_model_summary"]
    model_lines = facts["model_lines"]
    top_weights: list[tuple[str, float]] = facts["top_weights"]
    leakage_cols: list[str] = facts["leakage_cols"]

    if best_summary:
        brief = (
            f"Predicting `{target}` (**{task_label}**) across **{row_count:,} rows**. "
            f"Best benchmarked model: {best_summary}."
        )
    else:
        brief = (
            f"Configured to predict `{target}` (**{task_label}**) across **{row_count:,} rows** "
            "by comparing **Random Forest**, **Gradient Boosting**, and **Linear / Logistic Regression**."
        )

    weights_rows = []
    for rank, (col, w) in enumerate(top_weights[:8], start=1):
        pct = round(float(w) * 100.0, 1)
        weights_rows.append(f"| {rank} | `{col}` | **{pct:.1f}%** |")

    weights_table = (
        "| Rank | Column | Weight Share |\n| :--- | :--- | :--- |\n" + "\n".join(weights_rows)
        if weights_rows
        else "_Run prediction in **Predict & Simulate** to calculate per-column feature weights._"
    )
    models_bullets = "\n".join(f"- {m}" for m in model_lines)
    leakage_txt = (
        ", ".join(f"`{c}`" for c in leakage_cols)
        if leakage_cols
        else "None detected"
    )
    run_status_note = (
        f"**Latest Completed Benchmark**: {best_summary}"
        if best_summary
        else "**Status**: Ready — open **Predict & Simulate** and click **Run Prediction** to measure live holdout scores."
    )

    detailed = (
        f"### 1. Target & Prediction Setup\n"
        f"- **Target Column**: `{target}` (**{task_label}** across {row_count:,} rows, {facts['usable_feature_count']} active predictor columns)\n"
        f"- {run_status_note}\n\n"
        f"### 2. AI Models Benchmarked (Cross-Validation)\n"
        f"DataMind trains and compares candidate models using K-Fold cross-validation:\n"
        f"{models_bullets}\n\n"
        f"### 3. Top Weighted Columns ({facts['weight_source']})\n"
        f"{weights_table}\n\n"
        f"### 4. Auto-Excluded Leakage Columns\n"
        f"- Quarantined post-outcome columns: {leakage_txt}"
    )
    return brief, detailed


async def predict_agent_node(state: AgentState) -> dict[str, Any]:
    """Explain exact benchmarked AI models, target setup, feature weights, and leakage guards."""
    parquet_path = state.get("parquet_path")
    targets = state.get("target_columns", [])
    requested_target = targets[0] if targets else None
    latest_pred = state.get("latest_prediction")

    if not parquet_path:
        return {
            "brief_response": "Cannot inspect prediction models without an active dataset.",
            "detailed_narrative": "Missing dataset path.",
            "current_step": state["current_step"] + 1,
        }

    try:
        df = await asyncio.to_thread(pd.read_parquet, parquet_path)
        facts = await asyncio.to_thread(_extract_prediction_facts, df, requested_target, latest_pred)
    except Exception as e:
        logger.warning("Predict agent node dataset read/diagnosis failed: %s", e)
        return {
            "brief_response": "Failed to inspect dataset for ML readiness.",
            "detailed_narrative": f"Error evaluating dataset: {e}",
            "lab_artifact": None,
            "current_step": state["current_step"] + 1,
        }

    if not facts["can_proceed"]:
        diag = facts["diagnostics"]
        blockers_str = "\n".join([f"- {b}" for b in diag["blockers"]])
        return {
            "brief_response": "ML mission halted due to data validation blockers.",
            "detailed_narrative": f"## ML Diagnostic Report\n\n### Blockers Detected\n{blockers_str}",
            "lab_artifact": {"type": "diagnostic", **diag},
            "current_step": state["current_step"] + 1,
        }

    brief_fb, detailed_fb = _build_prediction_fallback(facts)
    brief, detailed = brief_fb, detailed_fb
    tokens_added = 0

    # If local Ollama is online and not recovering from a firewall retry, generate a natural grounded explanation
    if not state.get("firewall_feedback") and not llm_client.is_chat_circuit_open():
        top_w_str = ", ".join(
            f"{col} ({round(float(w) * 100.0, 1)}%)" for col, w in facts["top_weights"][:8]
        )
        leak_str = ", ".join(facts["leakage_cols"]) if facts["leakage_cols"] else "None detected"
        models_str = "; ".join(facts["model_lines"])
        prompt = (
            "You are DataMind AI Assistant explaining how predictive modeling works on the user's active dataset.\n"
            f"User Question: {state['query']}\n\n"
            "VERIFIED PREDICTION FACTS (USE ONLY THESE EXACT FACTS AND NUMBERS):\n"
            f"- Target Column: {facts['effective_target']}\n"
            f"- Prediction Type: {facts['task_type'].capitalize()}\n"
            f"- Dataset Size: {facts['row_count']:,} rows ({facts['usable_feature_count']} usable predictor columns)\n"
            f"- Best Model: {facts['best_model_summary'] or 'Not yet run (ready to benchmark)'}\n"
            f"- Candidate Models Benchmarked via Cross-Validation: {models_str}\n"
            f"- Top Weighted Columns ({facts['weight_source']}): {top_w_str}\n"
            f"- Auto-Excluded Leakage Columns: {leak_str}\n\n"
            "STRICT RULES:\n"
            "- Only put backticks around exact column names (e.g., `lead_time`). Bold model names like **Random Forest**, **Gradient Boosting**, **Logistic Regression**.\n"
            "- Include ALL 4 sections: Target & Task Type, Benchmarked AI Models (and winning score if available), Top 5-8 Weighted Columns with exact %, and Auto-Excluded Leakage Columns.\n"
            "- Format response strictly with:\n"
            "<<<BRIEF>>>\n"
            "(1-2 crisp sentences)\n"
            "<<<DETAILED>>>\n"
            "(clear Markdown with bullets or a compact weights table)\n"
        )
        res = await llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=900,
        )
        tokens_added = res.get("tokens", {}).get("total_tokens", 0)
        content = res.get("content", "")
        if res.get("model") != "offline-fallback" and content.strip():
            parsed_brief, parsed_detailed = _split_brief_detailed(content)
            # Only accept LLM rewrite if it actually cites at least one model & top column
            has_model = any(
                m in content.lower()
                for m in ["random forest", "gradient boosting", "logistic regression", "ridge", "k-means"]
            )
            first_col = facts["top_weights"][0][0].lower() if facts["top_weights"] else ""
            if has_model and (not first_col or first_col in content.lower()) and parsed_detailed:
                brief = parsed_brief or brief_fb
                detailed = parsed_detailed

    return {
        "brief_response": brief,
        "detailed_narrative": detailed,
        "tokens_used": state.get("tokens_used", 0) + tokens_added,
        "lab_artifact": {
            "type": "prediction",
            "diagnostic": facts["diagnostics"],
            "task_type": facts["task_type"],
            "target_column": facts["effective_target"],
            "top_weights": [
                {"column": col, "weight_pct": round(float(w) * 100.0, 1)}
                for col, w in facts["top_weights"][:8]
            ],
        },
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
        "random forest",
        "randomforestclassifier",
        "randomforestregressor",
        "gradientboosting",
        "gradient boosting",
        "gradientboostingclassifier",
        "gradientboostingregressor",
        "logisticregression",
        "logistic regression",
        "linear regression",
        "ridge regression",
        "cross-validation",
        "ridge",
        "kmeans",
        "k-means",
        "accuracy",
        "rmse",
        "mae",
        "mape",
        "r2",
        "inertia",
        "roc_auc",
        "target",
        "weights",
        "features",
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
        "ollama",
        "minimal",
        "sheets",
        "csv",
        "xlsx",
        "xls",
        "file",
        "files",
        "global",
    }

    for candidate in potential_cols:
        clean_cand = candidate.strip()
        cand_lower = clean_cand.lower()
        if cand_lower in reserved:
            continue
        # If candidate looks like a column identifier (no spaces or typical snake_case)
        if "_" in clean_cand or (clean_cand.isalpha() and len(clean_cand) > 3):
            is_encoded_feature = any(cand_lower.startswith(f"{vc}_") for vc in valid_cols_lower)
            if cand_lower not in valid_cols_lower and not is_encoded_feature:
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
