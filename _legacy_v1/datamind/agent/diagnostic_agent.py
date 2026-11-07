"""
Diagnostic Agent for DataMind v4.0.
Performs data quality checks and predicts feasibility for ML missions.
"""

from __future__ import annotations
import logging
import difflib
from typing import Any, Dict, Optional, List
import pandas as pd
from datamind.tools.stats import compute_fast_stats, DatasetStats

logger = logging.getLogger(__name__)

class DiagnosticAgent:
    """Agent for validating ML mission viability."""

    def __init__(self, stats: Optional[DatasetStats] = None):
        self.stats = stats

    def validate_for_prediction(self, df: pd.DataFrame, target_col: Optional[str] = None) -> Dict[str, Any]:
        """
        Comprehensive validation of the dataset for an ML task.
        Returns: {can_proceed, blockers, warnings, suggested_target}
        """
        blockers = []
        warnings = []
        suggested_target = None
        
        # 1. Basic Stats
        if self.stats is None:
            self.stats = compute_fast_stats(df)
            
        row_count = len(df)
        
        # --- Blocker Level Checks ---
        
        # Row Count Check
        if row_count < 20:
            blockers.append(f"Insufficient data: {row_count} rows detected. Minimum 20 rows required for ML.")

        # Target Column Validation
        if target_col:
            if target_col not in df.columns:
                matches = difflib.get_close_matches(target_col, df.columns, n=1, cutoff=0.6)
                if matches:
                    blockers.append(f"Target column '{target_col}' not found. Did you mean '{matches[0]}'?")
                else:
                    blockers.append(f"Target column '{target_col}' not found in dataset.")
            else:
                # Variance check
                if df[target_col].nunique() < 2:
                    blockers.append(f"Target column '{target_col}' has zero variance (all values are the same). Cannot model constant data.")
        else:
            # Suggest a target if none provided
            # Numeric columns with high variance or Categorical with moderate unique values
            favored = [c for c in self.stats.column_types["numeric"] if "id" not in c.lower()]
            if favored:
                suggested_target = favored[0]
            elif self.stats.column_types["categorical"]:
                suggested_target = self.stats.column_types["categorical"][0]

        # Feature Check (usable columns after preprocessing)
        usable_features = [c for c in df.columns if c != target_col and df[c].isnull().mean() < 0.6]
        if len(usable_features) < 2:
            blockers.append("Fewer than 2 usable feature columns detected after null-filtering.")

        # --- Warning Level Checks ---
        
        # Small sample size
        if 20 <= row_count < 100:
            warnings.append("Low sample size (<100 rows). Model accuracy may be unreliable.")

        # Class Imbalance
        if target_col and target_col in df.columns:
            if df[target_col].nunique() <= 10: # Likely categorical/classification
                counts = df[target_col].value_counts()
                if not counts.empty:
                    ratio = counts.max() / counts.min()
                    if ratio > 10:
                        warnings.append(f"Class imbalance detected ({ratio:.1f}:1). Using StratifiedKFold and reporting F1 metrics.")

        # High Null rate in features
        high_null_features = [c for c in usable_features if df[c].isnull().mean() > 0.2]
        if len(high_null_features) > (len(usable_features) * 0.3):
            warnings.append(f">30% of feature columns have high missingness (>20%). Automated imputation will be applied.")

        return {
            "can_proceed": len(blockers) == 0,
            "blockers": blockers,
            "warnings": warnings,
            "suggested_target": suggested_target
        }

    def check_feasibility(self, mode: str, target: Optional[str] = None) -> Dict[str, Any]:
        """Legacy method maintained for compatibility with Orchestrator."""
        # Simple shim for existing logic if needed
        res = self.validate_for_prediction(pd.DataFrame(), target) # Stub
        if not res["can_proceed"]:
            return {"approved": False, "message": res["blockers"][0], "suggestion": "Try another column."}
        return {"approved": True, "message": "Ready", "suggestion": None}