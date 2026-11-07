"""
Orchestrator for DataMind v4.0.
Master router for multi-agent intelligence routing and intent classification.
"""

from __future__ import annotations
import logging
import re
import difflib
from typing import Any, Dict, Optional, List, Tuple

import pandas as pd
import streamlit as st

from datamind.agent.summary_agent import SummaryAgent
from datamind.agent.diagnostic_agent import DiagnosticAgent
from datamind.agent.viz_agent import VizAgent
from datamind.agent.predict_agent import PredictAgent
from datamind.agent.analyst_agent import AnalystAgent
from datamind.agent.cleaning_agent import CleaningAgent
from datamind.memory.session import get_dataframe, get_summary_text, get_chat_history
from datamind.tools.stats import compute_fast_stats, DatasetStats
from datamind.llm.ollama_client import OllamaClient
from config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)

class Orchestrator:
    """Master Intelligence Router."""

    def __init__(self, client: Optional[OllamaClient] = None):
        self.client = client or OllamaClient()
        self.df = get_dataframe()
        self.stats = compute_fast_stats(self.df) if self.df is not None else None

    def route_query(self, query: str, fingerprint: Dict[str, Any] = None, file_id: Optional[int] = None, intent_override: Optional[str] = None) -> Dict[str, Any]:
        """Classifies intent and routes to the optimal specialized agent."""
        if self.df is None:
            return {"success": False, "response": "No data active. Please upload a dataset first."}

        # 1. Intent Classification (Keyword Based with Override)
        intent = intent_override.upper() if intent_override else self._classify_intent(query)
        
        # 2. Query Normalization (Fuzzy Column Mapping)
        normalized_query, target_col = self._normalize_and_extract_target(query)
        
        # 3. Context Package Construction
        history = get_chat_history()
        
        # 4. Routing
        if intent == "VISUALIZATION":
            agent = VizAgent(self.df, self.stats)
            viz_type = "correlation" if "correlation" in normalized_query or "heatmap" in normalized_query else "distribution"
            fig = agent.handle_request(viz_type, column=target_col)
            
            if fig:
                return {
                    "success": True, 
                    "response": f"Generated {viz_type} visualization for {target_col if target_col else 'the request'}.", 
                    "figures": [fig],
                    "category": "analysis"
                }
            else:
                return {
                    "success": True, # Still success as the agent processed it
                    "response": f"I analyzed the data but couldn't identify the right numeric column to build a {viz_type} chart. Could you specify the column name?",
                    "figures": [],
                    "category": "analysis"
                }

        elif intent == "PREDICTION":
            # 1. Distinguish between 'Hard ML' and 'Strategic Simulation'
            simulation_keywords = [
                "how", "increase", "decrease", "what-if", "what happens", "should", "simulate", 
                "if we", "growth", "scenario", "loss", "months", "years", "days", "impact", 
                "change", "effect", "reduction", "drop", "surge", "%"
            ]
            normalized_q_low = normalized_query.lower()
            is_simulation = any(x in normalized_q_low for x in simulation_keywords)
            
            # Heuristic for scenario modeling: (e.g. "predict 10% change")
            if not is_simulation:
                # Detect percentage patterns or temporal units
                if re.search(r'\d+%', normalized_q_low) or any(x in normalized_q_low for x in ["month", "year", "day", "week"]):
                    is_simulation = True
            
            if is_simulation:
                # Route to SummaryAgent's Strategic Forecasting Engine
                agent = SummaryAgent(client=self.client)
                res = agent.generate_predictions(self.df)
                return {
                    "success": True,
                    "response": res["response"],
                    "lab_narrative": res["lab_narrative"],
                    "category": "simulation",
                    "figures": res.get("figures", []) or ([res["fig"]] if res.get("fig") else [])
                }
            
            # 2. Hard ML Mission
            agent = PredictAgent(self.df, self.stats)
            # Determine mode based on keywords
            mode = "auto"
            if "cluster" in normalized_query: mode = "clustering"
            elif "forecast" in normalized_query: mode = "timeseries"
            elif "classify" in normalized_query or "classification" in normalized_query: mode = "classification"
            elif "regress" in normalized_query or "price" in normalized_query: mode = "regression"
            
            return agent.run_prediction_mission(target_col=target_col, mode=mode)

        elif intent == "SUMMARY":
            agent = SummaryAgent(client=self.client)
            dossier = agent.summarize_dossier(self.df)
            return {
                "success": True, 
                "response": dossier["response"], 
                "lab_narrative": dossier["lab_narrative"],
                "figures": dossier.get("figures", []),
                "category": "analysis"
            }

        elif intent == "CLEANING":
            agent = CleaningAgent(self.df, self.client)
            if any(x in normalized_query for x in ["fix", "apply", "automatic"]):
                res = agent.apply_auto_clean()
                return {"success": True, "response": res["response"], "category": "analysis"}
            return {"success": True, "response": agent.suggest_cleaning_plan(), "category": "analysis"}

        # DEFAULT: Analysis (Universal Reasoning)
        agent = AnalystAgent(
            df=self.df, 
            client=self.client, 
            file_id=file_id, 
            fingerprint=fingerprint
        )
        return agent.analyze(query, conversation_history=history)

    def _classify_intent(self, query: str) -> str:
        """Determines the primary analytical intent."""
        q = query.upper()
        if any(x in q for x in ["CHART", "PLOT", "GRAPH", "VISUALIZ", "HISTOGRAM", "HEATMAP", "SCATTER", "MAP"]):
            return "VISUALIZATION"
        if any(x in q for x in ["PREDICT", "FORECAST", "SIMULAT", "FUTURE", "MODEL", "CLUSTER", "KMEANS", "REGRESSION", "ML", "MACHINE LEARNING", "TRAIN", "TEST", "WHAT-IF", "WHAT HAPPENS", "INCREASE", "DECREASE", "GROWTH", "IMPACT"]):
            return "PREDICTION"
        if any(x in q for x in ["SUMMARY", "OVERVIEW", "PROFILE", "TELL ME ABOUT", "DESCRIBE", "EXPLAIN"]):
            return "SUMMARY"
        if any(x in q for x in ["CLEAN", "FIX", "NULL", "MISSING", "DUPLICATE", "AUDIT", "WASH"]):
            return "CLEANING"
        return "ANALYSIS"

    def _normalize_and_extract_target(self, query: str) -> Tuple[str, Optional[str]]:
        """Finds the most likely target column and normalizes the query."""
        if self.df is None: return query, None
        
        words = re.findall(r'\w+', query.lower())
        target = None
        normalized_query = query
        
        # Priority 1: Exact Match
        for col in self.df.columns:
            if col.lower() in words:
                target = col
                break
        
        # Priority 2: Fuzzy Match
        if not target:
            for word in words:
                if len(word) < 4: continue
                matches = difflib.get_close_matches(word, self.df.columns, n=1, cutoff=0.7)
                if matches:
                    target = matches[0]
                    normalized_query = normalized_query.replace(word, target)
                    break
        
        return normalized_query, target