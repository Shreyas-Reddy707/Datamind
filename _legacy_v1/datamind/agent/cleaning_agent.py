"""
Cleaning Agent for DataMind v4.0
Identifies and resolves data quality issues (nulls, duplicates, type mismatches).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import pandas as pd

from datamind.llm.ollama_client import OllamaClient
from datamind.tools.stats import DatasetStats, compute_fast_stats

logger = logging.getLogger(__name__)

class CleaningAgent:
    """Agent that performs autonomous data cleaning operations."""

    def __init__(self, df: pd.DataFrame, client: Optional[OllamaClient] = None):
        self.df = df
        self.client = client or OllamaClient()
        self.stats = compute_fast_stats(df)

    def suggest_cleaning_plan(self) -> str:
        """Analyze the dataset and return a markdown-formatted cleaning plan."""
        nulls = self.stats.null_counts
        dupes = self.df.duplicated().sum()
        
        plan = "### 🧹 Proposed Data Cleaning Plan\n\n"
        
        # 1. Duplicates
        if dupes > 0:
            plan += f"- **Duplicates**: Found {dupes} duplicate rows. *Action: Drop duplicates.*\n"
            
        # 2. Nulls
        has_nulls = False
        for col, count in nulls.items():
            if count > 0:
                has_nulls = True
                pct = (count / len(self.df)) * 100
                plan += f"- **Missing Values in '{col}'**: {count} rows ({pct:.1f}%). *Action: Fill with mean/median or drop.*\n"
        
        if not has_nulls and dupes == 0:
            plan += "✅ No major quality issues detected. Your dataset looks clean!\n"
        else:
            plan += "\n**Would you like me to apply these fixes automatically?**"
            
        return plan

    def apply_auto_clean(self) -> Dict[str, Any]:
        """Apply a standard set of cleaning operations to the DataFrame."""
        df_clean = self.df.copy()
        ops_performed = []

        # 1. Drop duplicates
        dupes = df_clean.duplicated().sum()
        if dupes > 0:
            df_clean = df_clean.drop_duplicates()
            ops_performed.append(f"Removed {dupes} duplicate rows.")

        # 2. Fill numeric nulls with median
        for col in self.stats.column_types["numeric"]:
            if df_clean[col].isna().any():
                df_clean[col] = df_clean[col].fillna(df_clean[col].median())
                ops_performed.append(f"Filled missing values in '{col}' with median.")

        # 3. Fill categorical nulls with 'Unknown'
        for col in self.stats.column_types["categorical"]:
            if df_clean[col].isna().any():
                df_clean[col] = df_clean[col].fillna("Unknown")
                ops_performed.append(f"Filled missing values in '{col}' with 'Unknown'.")

        return {
            "df": df_clean,
            "success": True,
            "ops": ops_performed,
            "response": "### ✅ Cleaning Complete\n\n" + "\n".join([f"- {opt}" for opt in ops_performed])
        }
