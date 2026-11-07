"""
Prediction Laboratory for DataMind SaaS.
Handles strategic forecasting and business impact simulations.
"""

from __future__ import annotations
import streamlit as st
from datamind.memory.session import get_chat_history, get_predictions
from datamind.ui.layout import render_summary_section, render_main_stage_artifacts, render_file_uploader
from datamind.ui.right_panel import render_right_panel

def render_prediction_lab():
    """Main rendering loop for Prediction Laboratory."""
    
    col_main, col_chat = st.columns([2.5, 1])
    
    with col_main:
        st.markdown("""
            <div style='margin-bottom: 2rem;'>
                <h2 style='margin: 0; font-family: "Outfit"; font-weight: 700; color: white;'>🔮 Strategic Forecasting Laboratory</h2>
                <p style='margin: 0.25rem 0 0 0; color: #94A3B8; font-size: 0.875rem;'>Deep-dive predictive simulations and business impact trajectories.</p>
            </div>
        """, unsafe_allow_html=True)
        
        # 0. Asset Ingestion
        render_file_uploader()
        
        # 1. Main Stage Content
        render_summary_section(None, get_predictions(), mode="prediction")
        render_main_stage_artifacts(get_chat_history(), filter_category="simulation")
        
    with col_chat:
        render_right_panel()
