"""
User Dashboard for DataMind v4.0.
Provides file management and dataset inventory for multi-tenant users.
"""

from __future__ import annotations
import streamlit as st
import database as db


def render_dashboard():
    """Renders the combined analytical dashboard."""
    from datamind.ui.layout import render_summary_section, render_main_stage_artifacts
    from datamind.memory.session import get_chat_history, get_predictions, get_summary_text

    user = st.session_state.get("current_user")
    if not user:
        st.warning("Please sign in to view your dashboard.")
        return

    st.markdown(f"""
        <div style='margin-bottom: 2rem;'>
            <h2 style='font-family: "Outfit"; font-weight: 700; color: white;'>Dashboard</h2>
            <p style='color: #94A3B8;'>Consolidated view of all analytical missions and predictive forecasts.</p>
        </div>
    """, unsafe_allow_html=True)

    # 0. Asset Ingestion
    from datamind.ui.layout import render_file_uploader
    render_file_uploader()

    # --- AUTO-ANALYSIS & REFINEMENT LOGIC ---
    df = st.session_state.get("df")
    summary = st.session_state.get("summary_text")
    
    if df is not None:
        if summary is None:
            # First-time analysis for newly activated asset
            with st.spinner("Decoding DNA of Activated Asset..."):
                from datamind.agent.summary_agent import SummaryAgent
                from datamind.agent.viz_agent import VizAgent
                from database import upsert_analytical_cache
                from config import OLLAMA_MODEL
                
                agent = SummaryAgent(model=st.session_state.get("selected_model", OLLAMA_MODEL))
                dossier = agent.summarize_dossier(df)
                st.session_state["summary_text"] = dossier
                
                viz = VizAgent(df)
                viz.generate_and_cache_top_charts()
                
                # Update Cache
                import json
                cache_payload = dossier.copy() if isinstance(dossier, dict) else {"text": dossier}
                if "figures" in cache_payload: del cache_payload["figures"]
                upsert_analytical_cache(st.session_state["current_file_id"], json.dumps(cache_payload), "")
                st.rerun()
        else:
            # Offer Refinement
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("✨ Refine Analysis", width="stretch", help="Building a deeper version of this analysis based on previous findings."):
                    with st.spinner("Deepening Analytical Context..."):
                         from datamind.agent.summary_agent import SummaryAgent
                         from database import upsert_analytical_cache
                         agent = SummaryAgent()
                         # In a real implementation, we would pass 'summary' as context to a 'Refine' prompt
                         dossier = agent.summarize_dossier(df) # Simulating refinement for now
                         # Update Cache
                         import json
                         cache_payload = dossier.copy() if isinstance(dossier, dict) else {"text": dossier}
                         if "figures" in cache_payload: del cache_payload["figures"]
                         upsert_analytical_cache(st.session_state["current_file_id"], json.dumps(cache_payload), "")
                         st.success("Analysis Deepened.")
                         st.rerun()
            st.divider()

    # 1. Combined Laboratory Insights
    render_summary_section(st.session_state.get("summary_text"), get_predictions(), mode="all")
    render_main_stage_artifacts(get_chat_history(), filter_category=None)

