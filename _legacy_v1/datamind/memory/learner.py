"""
Autonomous Pattern Learner for DataMind v4.0.
Extracts and persists analytical patterns from data and agent responses.
"""

from __future__ import annotations
import logging
import re
import json
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

import database as db
from datamind.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

class PatternLearner:
    """Self-learning loop for analytical pattern discovery (user+file scoped)."""

    def __init__(self, client: Optional[OllamaClient] = None):
        self.client = client or OllamaClient()

    def extract_statistical_patterns(self, df: pd.DataFrame, file_id: int, user_id: int):
        """Discovers statistical patterns in the dataset autonomously."""
        patterns = []
        
        # 1. High Correlations
        numeric_df = df.select_dtypes(include=[np.number])
        if len(numeric_df.columns) >= 2:
            corr_matrix = numeric_df.corr().abs()
            for i in range(len(corr_matrix.columns)):
                for j in range(i + 1, len(corr_matrix.columns)):
                    corr = corr_matrix.iloc[i, j]
                    if corr > 0.85:
                        col1, col2 = corr_matrix.columns[i], corr_matrix.columns[j]
                        patterns.append({
                            "type": "correlation",
                            "desc": f"Strong statistical link detected between '{col1}' and '{col2}' (r={corr:.2f}).",
                            "cols": json.dumps([col1, col2])
                        })

        # 2. Outliers
        for col in numeric_df.columns:
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            outliers = df[(df[col] < (q1 - 1.5 * iqr)) | (df[col] > (q3 + 1.5 * iqr))]
            if len(outliers) > 0 and len(outliers) < (len(df) * 0.05): # Only if < 5% are outliers
                patterns.append({
                    "type": "outlier",
                    "desc": f"Significant volumetric outliers identified in '{col}' beyond standard deviation.",
                    "cols": json.dumps([col])
                })

        # Persist
        for p in patterns:
            db.upsert_pattern(
                user_id=user_id,
                global_file_id=file_id,
                pattern_type=p["type"],
                description=p["desc"],
                columns_json=p.get("cols", "[]"),
                confidence=0.8
            )
            
        logger.info(f"Statically discovered {len(patterns)} patterns for user {user_id} on file {file_id}.")

    def validate_response_quality(self, response: str) -> bool:
        """Determines if an agent response is high-quality enough to learn from."""
        if len(response) < 300: return False
        if "## Finding" not in response and "**Finding**" not in response: return False
        
        error_terms = ["error", "sorry", "cannot", "don't know", "hallucination", "failed"]
        if any(term in response.lower()[:100] for term in error_terms):
            return False
            
        return True

    def extract_narrative_patterns(self, response: str, query: str, file_id: int, user_id: int):
        """Uses LLM to extract a reusable analytical insight from a response."""
        prompt = f"""You are an Intelligence Extraction Core.
Extract exactly ONE high-value analytical pattern from this agent response.
A pattern should be a one-sentence rule or insight that would be useful for future analysts looking at this same data.

Agent Query: {query}
Agent Response: {response[:1000]}

Format: Start with the column(s) name. Be precise.
Example: 'Revenue shows a strong cyclical peak every 3rd quarter.'
Output only the pattern string, no intro."""

        try:
            pattern_desc = self.client.chat([{"role": "user", "content": prompt}]).strip()
            pattern_desc = re.sub(r'^Pattern:\s*', '', pattern_desc, flags=re.IGNORECASE)
            
            if len(pattern_desc) > 10 and len(pattern_desc) < 200:
                db.upsert_pattern(
                    user_id=user_id,
                    global_file_id=file_id,
                    pattern_type="domain_rule",
                    description=pattern_desc,
                    columns_json="[]", # Could be parsed from pattern_desc if needed
                    confidence=0.7
                )
                logger.info(f"Narratively extracted pattern for user {user_id} on file {file_id}: {pattern_desc}")
        except Exception as e:
            logger.warning(f"Narrative extraction failed: {e}")
