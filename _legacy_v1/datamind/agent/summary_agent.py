"""
Summary Agent for DataMind v4.0
Fast dataset profiling using tools/stats.py for pre-computed statistics.
"""

from __future__ import annotations

import re
import json
import time
import logging
from typing import Any, Dict, Optional

import pandas as pd
from datamind.llm.ollama_client import OllamaClient
from config import SUMMARY_TIMEOUT, OLLAMA_BASE_URL, OLLAMA_MODEL
from datamind.agent.viz_agent import VizAgent
from datamind.tools.chart_builder import build_correlation_heatmap, build_distribution_chart
from datamind.tools.stats import compute_fast_stats, DatasetStats

logger = logging.getLogger(__name__)

class SummaryAgent:
    """Agent for fast dataset profiling and capability assessment."""

    def __init__(
        self,
        client: Optional[OllamaClient] = None,
        model: str = OLLAMA_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        timeout: int = SUMMARY_TIMEOUT,
    ):
        self.client = client or OllamaClient(model=model, base_url=base_url, timeout=timeout)
        self.timeout = timeout

    def summarize_dossier(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Step 1: Generate a visual and narrative briefing (Fast).
        Returns: { 'text': str, 'figures': List[Figure], 'captions': List[str] }
        """
        start_time = time.time()

        # Step 1: Compute stats (Fast)
        stats_obj: DatasetStats = compute_fast_stats(df)
        
        # Step 2: Generate Baseline Figures
        viz = VizAgent(df, stats_obj)
        figures = []
        
        if len(stats_obj.column_types["numeric"]) >= 2:
            figures.append(build_correlation_heatmap(df))
            
        if stats_obj.top_columns:
            noise_words = ["id", "index", "unnamed", "name", "email", "phone", "address", "contact", "street", "city", "state", "zip"]
            interesting_cols = [c for c in stats_obj.top_columns if not any(x in c.lower() for x in noise_words)]
            cat_cols = [c for c in stats_obj.column_types["categorical"] if 1 < df[c].nunique() < 20 and not any(x in c.lower() for x in noise_words)]
            
            final_visual_queue = list(dict.fromkeys(interesting_cols + cat_cols))
            for col in final_visual_queue[:4]:
                figures.append(build_distribution_chart(df, col))

        # Condensed Stats for LLM to avoid context overflow
        stats_for_llm = {
            "overview": {
                "rows": stats_obj.row_count,
                "cols": stats_obj.column_count,
                "memory_mb": stats_obj.memory_usage_mb,
                "duplicates": stats_obj.duplicate_rows
            },
            "column_types": { k: len(v) for k, v in stats_obj.column_types.items() if k != "all" },
            "key_columns": { col: stats_obj.column_details[col] for col in stats_obj.top_columns if col in stats_obj.column_details },
            "heuristics": {
                "ml_capabilities": stats_obj.ml_capabilities,
                "quality_warnings": stats_obj.data_quality_warnings
            }
        }
        
        stats_json = json.dumps(stats_for_llm, indent=2, default=str)
        full_dossier = self._call_llm(stats_json, stage="dossier")
        
        # Step 4: Split Response and Extract Captions
        result_parts = self._split_response(full_dossier)
        
        final_captions = result_parts.get("captions", [])[:len(figures)]
        while len(final_captions) < len(figures):
            final_captions.append("Discovering tactical patterns within this dimension.")

        elapsed = time.time() - start_time
        logger.info(f"Core Dossier generated in {elapsed:.2f}s")
        
        return {
            "response": result_parts["brief"],
            "lab_narrative": result_parts["detailed"],
            "figures": figures,
            "captions": final_captions
        }

    def generate_predictions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Step 2: Generate deep predictive forecasts (Intensive).
        Returns: { 'text': str, 'fig': Figure }
        """
        stats_obj = compute_fast_stats(df)
        
        # 1. Generate Narrative
        stats_json = json.dumps({
            "column_types": { k: len(v) for k, v in stats_obj.column_types.items() if k != "all" },
            "ml_readiness": stats_obj.ml_capabilities,
            "heuristics": stats_obj.top_columns
        }, indent=2, default=str)
        
        narrative = self._call_llm(stats_json, stage="prediction")

        # 2. Generate "Strategic Trajectory" Figure
        import plotly.graph_objects as go
        
        fig = go.Figure()
        
        # Best guess for a value column
        val_col = next((c for c in stats_obj.column_types["numeric"] if "sale" in c.lower() or "price" in c.lower() or "amount" in c.lower() or "total" in c.lower()), None)
        if not val_col and stats_obj.column_types["numeric"]:
            val_col = stats_obj.column_types["numeric"][0]
            
        if val_col:
            current_val = df[val_col].mean()
            # Simulate 12 month trajectory (Baseline vs Optimistic)
            months = ["Current", "M+1", "M+3", "M+6", "M+9", "M+12"]
            baseline = [current_val * (1 + 0.02 * i) for i in range(len(months))]
            optimistic = [current_val * (1 + 0.05 * i) for i in range(len(months))]
            
            fig.add_trace(go.Scatter(x=months, y=baseline, name="Baseline Trajectory", line=dict(color="#6366F1", width=3, dash='dot')))
            fig.add_trace(go.Scatter(x=months, y=optimistic, name="Strategic Growth (Optimistic)", line=dict(color="#10B981", width=4)))
            
            fig.update_layout(
                title=f"Strategic 12-Month Trajectory: {val_col}",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#E2E8F0"),
                margin=dict(l=20, r=20, t=40, b=20),
                height=350
            )

        # 3. Split Response
        result_parts = self._split_response(narrative)
        
        return {
            "response": result_parts["brief"],
            "lab_narrative": result_parts["detailed"],
            "fig": fig
        }

    def _call_llm(self, stats_json: str, stage: str = "dossier") -> str:
        """Call LLM for specific analysis stages."""
        if stage == "dossier":
            system_prompt = """You are the DataMind Strategic Architect. 
            Goal: Deliver a Forensic Dataset Briefing with high strategic fidelity.
            
            UNSUPERVISED PROTOCOL:
            Translate the raw schema fingerprint into a narrative that explains:
            - **Domain Essence**: What is this dataset's latent purpose?
            - **Forensic Truths**: What are the top numerical/categorical anomalies?
            - **Strategic Intelligence**: How can a user leverage these patterns immediately?

            STRICT FORMAT FOR DETAILED SECTION:
            ## Introduction
            ## Forensic Deep-Dive Analysis
            ## Strategic Conclusion & Impact
            ## Executive Data Snapshot (Markdown Table)

            STRICT PROTOCOL:
            - DO NOT repeat system instructions or headers like 'Response Structure Requirement'.
            - NO MARKDOWN CODE BLOCKS (except for the Markdown Table). No ```python blocks.
            - NARRATIVE ONLY for the first 3 sections. Commmunicate like a Senior Strategy Consultant.
            - Ensure the 'Detailed Analysis' is high-depth and multi-paragraph.

            ### Response Structure Requirement:
            You MUST provide your response in two distinct sections separated by tags:
            <<<BRIEF>>>: A point-to-point summary for the chat (MAX 3 BULLETS, MAX 40 WORDS). 
            <<<DETAILED>>>: The full, forensic narrative briefing (THE THEORY PART).
            
            START IMMEDIATELY WITH <<<BRIEF>>>. DO NOT ADD PREAMBLES.

            ---
            [GRAPH CAPTIONS]
            Provide sharp, impact-focused captions for the visual artifacts (one per artifact).
            Example:
            - Distribution of X shows...
            - High correlation between..."""
        else:
            system_prompt = """You are a Senior Strategic Forecaster & Simulation Architect.
            Goal: Generate a HIGH-DEPTH Predictive Impact & Simulation Dossier.
            
            STRICT FORMAT FOR DETAILED SECTION:
            ## Forecast Introduction
            ## Strategic Simulation Analysis
            ## Tactical Action Plan & Conclusion
            ## Predictive Impact Snapshot (Markdown Table)

            STRICT PROTOCOL:
            - NO MARKDOWN CODE BLOCKS (except for the Markdown Table).
            - NARRATIVE ONLY for the first 3 sections. Focus on 'How' and 'What-if' scenarios.
            - IT MUST BE A DEEP, MULTI-SECTION SIMULATION REPORT.
            - Provide exhaustive 'What-if' scenarios and mathematical trajectories.
            - Do not truncate. Be expansive and forensic.
            
            ### Response Structure Requirement:
            You MUST provide your response in two distinct sections separated by tags:
            <<<BRIEF>>>: A point-to-point, ultra-short summary for the chatbot interface (MAX 40 WORDS).
            <<<DETAILED>>>: The full, high-fidelity Predictive Impact & Simulation Dossier.
            
            START IMMEDIATELY WITH <<<BRIEF>>>. DO NOT ADD PREAMBLES."""

        user_prompt = f"Dataset Stats JSON: {stats_json}"

        try:
            # Use internal streaming for better connection stability
            response = self.client.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ], stream=True)
            
            # Validate response
            if not response or len(response) < 50:
                 logger.warning(f"LLM {stage} returned short response: {response}")
            
            return response.strip()
        except Exception as exc:
            logger.error(f"LLM {stage} call failure: {exc}")
            error_type = "Timeout" if "timeout" in str(exc).lower() else "Connection Error"
            return f"""### ⚠️ Forensic Engine Offline
The local AI node (Ollama: {self.client.model}) is currently unresponsive. 

**Error Type:** {error_type}
**Technical Details:** {str(exc)}
 
 *Tip: Ensure Ollama is running (`ollama serve`) and the model is fully loaded.*"""

    def _split_response(self, text: str) -> Dict[str, str]:
        """Splits LLM output into brief chat response and detailed lab narrative."""
        # 1. Clean common LLM-generated garbage
        text = re.sub(r'(Response Structure Requirement:|STRICT PROTOCOL:|STRICT FORMAT:).*?\n', '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # 2. Extract Captions if present and remove them from the body
        captions = []
        if "[GRAPH CAPTIONS]" in text:
            try:
                parts = text.split("[GRAPH CAPTIONS]")
                body = parts[0]
                caption_text = parts[1]
                lines = caption_text.strip().split("\n")
                captions = [l.strip("- ").strip().strip("💡 ") for l in lines if l.strip().startswith("-") or l.strip().startswith("💡")]
                text = body
            except:
                pass
            
        brief = ""
        detailed = text
        
        # 3. Handle tags
        if "<<<BRIEF>>>" in text and "<<<DETAILED>>>" in text:
            try:
                parts = text.split("<<<DETAILED>>>")
                detailed = parts[1].strip()
                brief = parts[0].replace("<<<BRIEF>>>", "").strip()
            except:
                pass
        elif "<<<BRIEF>>>" in text:
            brief = text.replace("<<<BRIEF>>>", "").strip()
        
        # 4. Final cleanup of any lingering tags in detailed
        detailed = re.sub(r'<<<BRIEF>>>|<<<DETAILED>>>', '', detailed).strip()
        
        # Fallback if splitting fails or returns empty
        if not brief:
            # Take first sentence or first 150 chars as brief
            paras = text.split("\n\n")
            brief = paras[0].strip() if paras else text
            if len(brief) > 150:
                brief = brief[:147] + "..."
            
        return {"brief": brief, "detailed": detailed, "captions": captions}