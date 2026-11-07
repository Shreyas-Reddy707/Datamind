"""
Left Panel for DataMind SaaS - Analysis Laboratory View.
Handles forensic data ingestion and automated breakdown generation.
"""

from __future__ import annotations
import streamlit as st
from datamind.memory.session import (
    get_dataframe, get_summary_text, set_summary_text, get_chat_history,
    get_predictions, handle_file_upload
)
from datamind.agent.summary_agent import SummaryAgent
from datamind.agent.viz_agent import VizAgent
from datamind.ui.layout import render_left_panel_metrics, render_summary_section, render_main_stage_artifacts
from config import OLLAMA_MODEL

def render_left_panel():
    """Main rendering loop for Analysis Laboratory."""
    user = st.session_state.get("current_user")
    
    # Lab Header
    st.markdown("""
        <div style='margin-bottom: 2rem;'>
            <h2 style='margin: 0; font-family: "Outfit"; font-weight: 700; color: white;'>🧪 Analysis Laboratory</h2>
            <p style='margin: 0.25rem 0 0 0; color: #94A3B8; font-size: 0.875rem;'>Deep forensic breakdown and autonomous dataset profiling.</p>
        </div>
    """, unsafe_allow_html=True)

    # 1. Forensic Asset Ingestion (Uploader)
    from datamind.ui.layout import render_file_uploader
    render_file_uploader()

    # 2. Main Laboratory Stage
    df = get_dataframe()
    if df is not None:
        # Optimization: Pre-compute stats once for the entire view
        from datamind.tools.stats import compute_fast_stats
        stats = compute_fast_stats(df)
        
        # Metrics are now tucked away in an "Essentials" expander to avoid "Dashboard Behavior"
        with st.expander("📊 Dataset Essentials & Statistics", expanded=False):
            render_left_panel_metrics(stats)
            st.divider()
            st.markdown("#### Column Profiling")
            st.dataframe(df.dtypes.astype(str).to_frame("Type").T, width="stretch")

        # Forensic Results Area
        st.markdown("### 🔍 Forensic Breakdown")
        
        # This renders the detailed AI narrative (Introduction, Explained, Visuals)
        render_summary_section(get_summary_text(), mode="analysis")
        
        # This renders any deeper analysis artifacts generated via chat
        render_main_stage_artifacts(get_chat_history(), filter_category="analysis")
        
    else:
        st.markdown("""
            <div style='padding: 3rem; text-align: center; background: rgba(255,255,255,0.03); border: 1px dashed rgba(255,255,255,0.1); border-radius: 20px;'>
                <div style='font-size: 3rem; margin-bottom: 1rem;'>👋</div>
                <h4 style='color: white;'>Laboratory Idle</h4>
                <p style='color: #94A3B8;'>Inject a dataset above or activate an existing lab from the <b>Executive Dashboard</b> to begin analysis.</p>
            </div>
        """, unsafe_allow_html=True)