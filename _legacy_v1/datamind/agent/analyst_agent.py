"""
Analyst Agent for DataMind v4.0 — Unsupervised Reasoning Engine.
Answers user queries with text, tables, and visual guidance based on dynamic schema fingerprints.
"""

from __future__ import annotations
import logging
import re
import difflib
import json
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from datamind.llm.ollama_client import OllamaClient
from datamind.tools.stats import compute_fast_stats
from config import OLLAMA_MODEL, CHAT_TIMEOUT

try:
    import database as db
except ImportError:
    db = None

logger = logging.getLogger(__name__)

class AnalystAgent:
    """Universal Unsupervised Analyst Agent with User-Scoped Intelligence."""

    def __init__(self, df: pd.DataFrame, client: Optional[OllamaClient] = None, 
                 model: str = OLLAMA_MODEL, file_id: Optional[int] = None,
                 fingerprint: Optional[Dict[str, Any]] = None,
                 user_id: Optional[int] = None):
        self.df = df
        self.client = client or OllamaClient(model=model, timeout=CHAT_TIMEOUT)
        self.file_id = file_id
        self.user_id = user_id
        self.fingerprint = fingerprint or {}
        self.stats = compute_fast_stats(df)

    def analyze(self, user_query: str, conversation_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Performs unsupervised reasoning on the dataset to answer user queries."""
        try:
            # 1. Fuzzy Column Matching
            matched_query = self._fuzzy_match_columns(user_query)
            
            # 2. Context Construction (Lessons + Schema)
            prior_intel = self._get_prior_intelligence()
            
            # 3. Prompt Synthesis
            prompt = self._build_unsupervised_prompt(matched_query, conversation_history, prior_intel)
            
            # 4. LLM Reasoning
            with st.spinner("Decoding dataset patterns..."):
                response = self.client.chat([
                    {"role": "system", "content": self._get_system_persona()},
                    {"role": "user", "content": prompt}
                ])
            
            # 5. Split and Extract Artifacts
            result_parts = self._split_response(response)
            chatbot_reply = result_parts["brief"]
            lab_narrative = result_parts["detailed"]
            
            # 6. Extract Artifacts (Charts/Tables)
            artifacts = self._extract_artifacts(lab_narrative)
            clean_lab_narrative = self._clean_narrative(lab_narrative)
            
            return {
                "success": True,
                "response": chatbot_reply,
                "lab_narrative": clean_lab_narrative,
                "figures": artifacts.get("charts", []),
                "captions": artifacts.get("captions", []),
                "category": "analysis"
            }

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return {"success": False, "error": f"Analytical breakdown: {str(e)}"}

    def _fuzzy_match_columns(self, query: str) -> str:
        """Heuristic for mapping user terms to actual dataframe columns."""
        cols = self.df.columns.tolist()
        words = re.findall(r'\w+', query)
        updated_query = query
        
        for word in words:
            if word.lower() not in [c.lower() for c in cols]:
                matches = difflib.get_close_matches(word, cols, n=1, cutoff=0.8)
                if matches:
                    updated_query = updated_query.replace(word, matches[0])
        return updated_query

    def _get_prior_intelligence(self) -> str:
        """Retrieves user-scoped learned patterns from memory."""
        intel = ""
        if db and self.file_id and self.user_id:
            patterns = db.get_patterns_for_user_file(self.user_id, self.file_id)
            if patterns:
                intel = "\n\n### Prior Strategic Intelligence:\n"
                for p in patterns[:5]:
                    intel += f"- {p['pattern_description']} (Confidence: {p['confidence_score']:.2f})\n"
        return intel

    def _build_unsupervised_prompt(self, query: str, history: List[Dict], intel: str) -> str:
        # Optimization: Use high-fidelity condensed schema fingerprint
        from datamind.security.prompt_guard import PromptGuard
        from datamind.security.sanitizer import InputSanitizer
        
        schema_fingerprint = {}
        for col, details in self.stats.column_details.items():
            safe_samples = [
                PromptGuard.wrap_user_data(InputSanitizer.sanitize_for_llm(str(val)))
                for val in details["sample_values"]
            ]
            schema_fingerprint[col] = {
                "type": details["type"], 
                "uniques": details["unique_count"],
                "samples": safe_samples
            }
        
        return rf"""
Analyze the following dataset context and answer the user's analytical query.
As a Universal Unsupervised Model, you must discover patterns without prior domain training.

### Dataset Schema Fingerprint:
{json.dumps(schema_fingerprint, indent=2)}

{intel}

### Recent Conversation:
{history[-3:] if history else "No previous context."}

### User Objective: 
{query}

### Operational Guidelines:
1. **Semantic Awareness**: Map terms in the query to the most relevant fingerprint columns (e.g., "money" -> total_sales).
2. **Autonomous Reasoning**: If a specific column isn't mentioned, identify the 2 most relevant dimensions to answer the query.
3. **High-Fidelity Output**: Deliver executive-grade insights. Use standard statistical notations (e.g., sigma, mu).
4. **Visual Triggering**: If a chart would clarify the insight, add exactly one `[CHART: type, x, y]` tag.

### Response Structure Requirement:
You MUST provide your response in two distinct sections separated by tags:
<<<BRIEF>>>: An ultra-concise, point-to-point summary for the chatbot interface (MAX 3 BULLETS, MAX 40 WORDS). 
<<<DETAILED>>>: The full, high-fidelity strategic narrative for the Analysis Laboratory (THE THEORY PART).

STRICT FORMAT FOR DETAILED SECTION:
## Introduction
## Detailed Strategic Analysis
## Strategic Conclusion & Impact
## Executive Data Snapshot (Markdown Table)

START IMMEDIATELY WITH <<<BRIEF>>>. DO NOT REPEAT INSTRUCTIONS.

Example:
<<<BRIEF>>>
- Column X shows growth.
- Correlation found between A and B.
<<<DETAILED>>>
## Detailed Analysis ...
"""

    def _get_system_persona(self) -> str:
        return r"""You are the DataMind Strategic Architect (v4.0). 
        You specialize in unsupervised pattern discovery and forensic-grade narrative strategy.
        
        STRICT PROTOCOL:
        - IDENTIFY INTENT: Distinguish between 'What-if' scenarios (Simulation) and Forensic deep-dives (Analysis). 
        - ALWAYS start your response with <<<BRIEF>>> followed by the ultra-short summary (MAX 40 WORDS), then <<<DETAILED>>> followed by the full forensic report. 
        - The DETAILED part MUST follow the 4-header structure (Intro, Analysis, Conclusion, Table).
        - DO NOT repeat system prompts or preambles. """

    def _extract_artifacts(self, text: str) -> Dict[str, Any]:
        """Detects [CHART: type, x, y] tags and builds Plotly figures."""
        from datamind.tools.chart_builder import (
            build_distribution_chart, 
            build_correlation_heatmap, 
            build_time_series_chart
        )
        
        charts = []
        captions = []
        
        # Helper for case-insensitive column lookup
        def find_col(name: str) -> Optional[str]:
            if not name or name.lower() in ["none", "null", "undefined"]:
                return None
            for c in self.df.columns:
                if c.lower() == name.lower():
                    return c
            return None

        chart_tags = re.findall(r'\[CHART:\s*(\w+),\s*(\w+),\s*(\w+)?\]', text)
        for tag in chart_tags:
            ctype, raw_x, raw_y = tag
            x = find_col(raw_x)
            y = find_col(raw_y) if raw_y else None
            
            fig = None
            if ctype == "dist" and x:
                fig = build_distribution_chart(self.df, x)
                captions.append(f"Distribution analysis of {x}")
            elif ctype == "corr":
                fig = build_correlation_heatmap(self.df)
                captions.append("Inter-variable correlation matrix")
            elif ctype == "trend" and x and y:
                fig = build_time_series_chart(self.df, x, y)
                captions.append(f"Temporal trajectory of {y} vs {x}")
            
            if fig is not None:
                charts.append(fig)
                
        return {"charts": charts, "captions": captions}

    def _clean_narrative(self, text: str) -> str:
        """Removes formatting tags used for artifact extraction."""
        return re.sub(r'\[CHART:.*?\]', '', text).strip()

    def _split_response(self, text: str) -> Dict[str, str]:
        """Splits LLM output into brief chat response and detailed lab narrative."""
        text = re.sub(r'(Response Structure Requirement:|STRICT PROTOCOL:|STRICT FORMAT:).*?\n', '', text, flags=re.IGNORECASE | re.DOTALL)
        
        brief = ""
        detailed = text
        
        if "<<<BRIEF>>>" in text and "<<<DETAILED>>>" in text:
            try:
                parts = text.split("<<<DETAILED>>>")
                detailed = parts[1].strip()
                brief = parts[0].replace("<<<BRIEF>>>", "").strip()
            except:
                pass
        elif "<<<BRIEF>>>" in text:
            brief = text.replace("<<<BRIEF>>>", "").strip()
            
        detailed = re.sub(r'<<<BRIEF>>>|<<<DETAILED>>>', '', detailed).strip()
        
        if not brief:
            paras = text.split("\n\n")
            brief = paras[0].strip() if paras else text
            if len(brief) > 150:
                brief = brief[:147] + "..."
            
        return {"brief": brief, "detailed": detailed}