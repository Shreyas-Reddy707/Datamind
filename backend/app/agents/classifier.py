"""DataMind v2 Chat Classifier (3-Tier Query Routing Engine).

Categorizes incoming prompts into:
- Tier 1 (Instant <25ms deterministic DuckDB execution)
- Tier 2 (Quick <3s streamed LLM response)
- Tier 3 (Deep 5-15s multi-agent bounded reasoning pipeline)
"""

from __future__ import annotations

import difflib
import logging
import re
from typing import Any

logger = logging.getLogger("datamind.agents.classifier")

# Tier 1 Detection Regexes (Sub-25ms deterministic stats)
STAT_PATTERNS = [
    r"how many rows",
    r"row count",
    r"total rows",
    r"how many columns",
    r"list\s+columns",
    r"what columns",
    r"show\s+columns",
    r"(average|mean|max|min|sum|count|median|stddev)\s+(of\s+)?.+",
    r"which\s+.+\s+has\s+(the\s+)?(most|highest|largest|top|lowest|least|fewest)",
    r"how many nulls",
    r"missing values",
    r"null values",
    r"null.*in\s+.+",
    r"correlation\s+between\s+.+\s+and\s+.+",
]

# Explicit Tier 3 Triggers (Forces Deep Lab analysis)
RENDER_TRIGGERS = [
    "show in lab",
    "add to lab",
    "render this",
    "send to lab",
    "put in lab",
    "add to analysis",
    "show full",
    "detailed analysis",
    "full breakdown",
    "deep dive",
    "/lab",
    "/render",
]

PREDICT_KEYWORDS = [
    "predict",
    "forecast",
    "future",
    "model",
    "simulate",
    "impact",
    "scenario",
    "what-if",
    "what happens",
    "growth",
    "increase",
    "decrease",
    "trend",
    "feature weight",
    "feature importance",
]

VIZ_KEYWORDS = [
    "chart",
    "plot",
    "graph",
    "visualize",
    "histogram",
    "heatmap",
    "scatter",
    "distribution",
]

CLEANING_KEYWORDS = [
    "clean",
    "fix",
    "impute",
    "remove nulls",
    "drop duplicates",
    "quality check",
    "audit",
]

GREETING_REGEX = r"^(hi|hello|hey|yo|greetings|good\s+(morning|afternoon|evening)|thanks?|thank\s+you)[\s!?.,]*$"

PLATFORM_HELP_PATTERNS = [
    r"\b(auto\s*ml|automl|predict\s*&\s*simulate|predict\s+and\s+simulate|smart\s+tables?)\b.*\b(doing|work|use|is|explain|lab|tab)\b",
    r"\b(what|how)\b.*\b(auto\s*ml|automl|forensic|what-if|simulator|sql\s*sandbox|smart\s+tables?|predict\s*&\s*simulate|insights\s*&\s*charts|datamind)\b",
    r"\bhow\s+(do\s+i|to)\s+(use|predict|start|run|analyze)\b",
    r"\bwhat\s+can\s+you\s+do\b",
    r"^help[\s!?.,]*$",
]


class ChatClassifier:
    """Classifies user queries into Tier 1, Tier 2, or Tier 3 with target column extraction."""

    @classmethod
    def classify(cls, query: str, active_columns: list[str]) -> dict[str, Any]:
        """Classify query into tier and intent, extracting target columns via fuzzy matching."""
        q_lower = query.lower().strip()

        # 0. Customer Greetings & Platform Guide Questions
        is_greeting = bool(re.match(GREETING_REGEX, q_lower))
        is_platform_help = any(re.search(p, q_lower) for p in PLATFORM_HELP_PATTERNS)
        if is_greeting or is_platform_help:
            return {
                "tier": 1,
                "intent": "help",
                "target_columns": [],
                "render_to_lab": False,
                "lab_target": "analysis",
            }

        # 1. Tier 1 Check (Deterministic Math & Stats)
        is_tier1 = any(re.search(p, q_lower) for p in STAT_PATTERNS)

        # 2. Render to Lab Check
        render_to_lab = any(t in q_lower for t in RENDER_TRIGGERS)

        # 3. Intent Detection
        intent = "analysis"
        if any(k in q_lower for k in PREDICT_KEYWORDS):
            intent = "prediction"
        elif any(k in q_lower for k in VIZ_KEYWORDS):
            intent = "visualization"
        elif any(k in q_lower for k in CLEANING_KEYWORDS):
            intent = "cleaning"
        elif any(k in q_lower for k in ["summary", "overview", "profile", "describe", "tell me about"]):
            intent = "summary"
        elif is_tier1:
            intent = "stat"

        # 4. Tier Assignment
        # Tier 1: Pure deterministic query
        # Tier 3: Explicit lab render, prediction, viz, cleaning, summary, or complex prompt (>10 words)
        # Tier 2: Quick targeted conversational questions
        if is_tier1 and not render_to_lab:
            tier = 1
        elif render_to_lab or intent in ["prediction", "visualization", "cleaning", "summary"] or len(q_lower.split()) > 10:
            tier = 3
        else:
            tier = 2

        # 5. Extract and fuzzy-match target columns
        target_columns: list[str] = []
        clean_q = re.sub(r"[^\w\s]", " ", q_lower)
        words = clean_q.split()

        for word in words:
            if len(word) < 3:
                continue
            # Check exact match
            for col in active_columns:
                if col.lower() == word and col not in target_columns:
                    target_columns.append(col)
            # Check fuzzy match
            if not target_columns:
                matches = difflib.get_close_matches(word, [c.lower() for c in active_columns], n=1, cutoff=0.75)
                if matches:
                    matched_col = next(c for c in active_columns if c.lower() == matches[0])
                    if matched_col not in target_columns:
                        target_columns.append(matched_col)

        return {
            "tier": tier,
            "intent": intent,
            "target_columns": target_columns,
            "render_to_lab": render_to_lab,
            "lab_target": "simulation" if intent == "prediction" else "analysis",
        }
