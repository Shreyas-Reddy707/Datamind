"""
Chat Classifier for DataMind v4.0.
Categorizes queries into Tier 1 (Instant), Tier 2 (Quick), or Tier 3 (Deep Analysis).
"""

import re
import difflib
from typing import Dict, List, Any

# Tier 1 Detection Patterns
STAT_PATTERNS = [
    r"how many rows", r"row count", r"how many columns",
    r"list.*columns", r"what columns", r"show.*columns",
    r"average of (.+)", r"mean of (.+)", r"max of (.+)",
    r"min of (.+)", r"sum of (.+)", r"count of (.+)",
    r"how many nulls", r"missing values", r"null.*in (.+)"
]

# Tier 3 Render Triggers
RENDER_TRIGGERS = [
    "show in lab", "add to lab", "render this", "send to lab",
    "put in lab", "add to analysis", "show full", "detailed analysis",
    "full breakdown", "deep dive", "/lab", "/render"
]

# Intent Keywords
PREDICT_KEYWORDS = ["predict", "forecast", "future", "model", "simulate", "impact", "scenario", "what-if", "what happens", "growth", "increase", "decrease"]
VIZ_KEYWORDS = ["chart", "plot", "graph", "visualize", "histogram", "heatmap"]

def classify_tier(query: str, active_df_columns: List[str]) -> Dict[str, Any]:
    """
    Classifies a user query into one of three tiers based on complexity and triggers.
    """
    q_lower = query.lower().strip()
    
    # --- Tier 1 Detection (Regex) ---
    is_tier1 = False
    for pattern in STAT_PATTERNS:
        if re.search(pattern, q_lower):
            is_tier1 = True
            break
            
    # --- Render Trigger Detection (Forms Tier 3) ---
    render_to_lab = False
    for trigger in RENDER_TRIGGERS:
        if trigger in q_lower:
            render_to_lab = True
            break
            
    # --- Intent Classification ---
    intent = "stat"
    if any(k in q_lower for k in PREDICT_KEYWORDS):
        intent = "prediction"
    elif any(k in q_lower for k in VIZ_KEYWORDS):
        intent = "visualization"
    elif render_to_lab:
        intent = "render_request"
    elif not is_tier1:
        # If not Tier 1 and no specific ML/Viz keywords, check if it's a simple comparison/why (Tier 2)
        if any(k in q_lower for k in ["why", "compare", "difference", "vs"]):
            intent = "comparison"
        else:
            intent = "analysis"

    # --- Tier Assignment ---
    tier = 2 # Default to Fast Analysis
    if is_tier1:
        tier = 1
    elif render_to_lab or intent in ["prediction", "visualization"]:
        tier = 3
    # If the query is complex (many words) and not Tier 1/Viz/Predict, it's likely Tier 3
    elif len(q_lower.split()) > 10:
        tier = 3

    # --- Target Column Extraction (Fuzzy Match) ---
    target_columns = []
    # Clean query for matching (remove punctuation)
    clean_q = re.sub(r'[^\w\s]', ' ', q_lower)
    words = clean_q.split()
    
    for word in words:
        if len(word) < 3: continue
        # Find exact or close matches in df columns
        matches = difflib.get_close_matches(word, active_df_columns, n=1, cutoff=0.7)
        if matches and matches[0] not in target_columns:
            target_columns.append(matches[0])

    # --- Lab Target Logic ---
    lab_target = "analysis"
    if intent == "prediction" or "predict" in q_lower:
        lab_target = "simulation"

    return {
        "tier": tier,
        "intent": intent,
        "target_columns": target_columns,
        "render_to_lab": render_to_lab,
        "lab_target": lab_target if tier == 3 else None
    }

def find_possible_target_columns(query: str, fingerprint: Dict[str, Any]) -> List[str]:
    """Fallback for disambiguation if no target columns were confidently found."""
    cols = list(fingerprint.get("columns", {}).keys())
    q_lower = query.lower()
    possible = []
    for col in cols:
        if col.lower() in q_lower or any(word in q_lower for word in col.lower().split()):
            possible.append(col)
    return possible
