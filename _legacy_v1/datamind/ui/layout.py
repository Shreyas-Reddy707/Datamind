# Force Refresh: Proactive UI v4.2
"""
DataMind v4.0 - Workspace Layout Utilities
Provides premium styling and fixed-drawer components.
"""

from __future__ import annotations
import streamlit as st
import re
import pandas as pd
from typing import List, Dict, Any, Optional
from plotly.graph_objects import Figure

from datamind.memory.session import (
    get_dataframe,
    get_summary_text,
)

def create_split_layout():
    """Deprecated: UI now uses a fixed-drawer approach."""
    return st.columns([1, 2.3])

def apply_custom_styles():
    """Inject premium SaaS-style CSS with glassmorphism and modern design principles."""
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Outfit:wght@500;600;700;800&display=swap');

        :root {
            --primary: #6366F1;
            --primary-hover: #4F46E5;
            --secondary: #10B981;
            --accent: #8B5CF6;
            --warning: #F59E0B;
            --bg-dark: #0F172A;
            --bg-card: rgba(30, 41, 59, 0.7);
            --card-glass: rgba(255, 255, 255, 0.05);
            --border-glass: rgba(255, 255, 255, 0.1);
            --border-glass-light: rgba(255, 255, 255, 0.06);
            --gradient-primary: linear-gradient(135deg, #6366F1 0%, #8B5CFD 50%, #EC4899 100%);
            --drawer-width: 320px;
        }

        .stApp {
            background: var(--bg-dark);
            color: #E2E8F0;
            font-family: 'Inter', sans-serif;
            overflow-x: hidden;
        }

        /* Sidebar styling - Premium Glassmorphism */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(15,23,42,0.95) 0%, rgba(15,23,42,0.85) 100%) !important;
            backdrop-filter: blur(20px) !important;
            -webkit-backdrop-filter: blur(20px) !important;
            border-right: 1px solid var(--border-glass) !important;
        }

        /* Sidebar Navigation Elements */
        [data-testid="stSidebar"] .radio-label {
            color: #CBD5E1 !important;
            font-weight: 500 !important;
            padding: 12px 16px !important;
            margin: 4px 0 !important;
            border-radius: 10px !important;
            transition: all 0.2s ease !important;
        }
        [data-testid="stSidebar"] .radio-label:hover {
            background: rgba(255, 255, 255, 0.05) !important;
        }
        [data-testid="stSidebar"] .radio-label[selected] {
            background: var(--gradient-primary) !important;
            color: white !important;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3) !important;
        }

        /* Target the Right Column in a 2-column layout - Premium Style */
        /* Specific only to main workspace to avoid affecting sidebar utilities */
        [data-testid="stMain"] [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:last-child {
            background: var(--bg-card) !important;
            backdrop-filter: blur(15px) !important;
            -webkit-backdrop-filter: blur(15px) !important;
            border-left: 1px solid var(--border-glass) !important;
            border-radius: 24px !important;
            padding: 1.25rem 1.5rem !important;
            box-shadow: -15px 0 50px rgba(0,0,0,0.3) !important;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
            margin-top: 0 !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: flex-start !important;
            align-items: stretch !important;
            align-self: flex-start !important;
        }

        /* Main Workspace Adjustment */
        .main-workspace {
            padding: 1.5rem 2rem 2rem 2rem;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            max-width: 100%;
            overflow-x: auto;
            word-wrap: break-word;
            background: linear-gradient(180deg, rgba(15,23,42,0) 0%, rgba(15,23,42,0.3) 100%);
            margin-top: 0 !important;
        }

        .main-workspace.expanded {
            padding: 1.5rem 2rem 2rem 2rem !important;
            max-width: 100%;
            overflow-x: auto;
            background: linear-gradient(180deg, rgba(15,23,42,0) 0%, rgba(15,23,42,0.5) 100%);
            margin-top: 0 !important;
        }

        /* Top-Alignment Fix for Streamlit Columns */
        [data-testid="stHorizontalBlock"] {
            align-items: flex-start !important;
        }
        
        div[data-testid="stVerticalBlock"] {
            justify-content: flex-start !important;
        }

        /* Premium Button Styling */
        .stButton button {
            background: var(--gradient-primary) !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 10px 20px !important;
            color: white !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3) !important;
        }
        .stButton button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 25px rgba(99, 102, 241, 0.4) !important;
        }
        .stButton button:active {
            transform: translateY(0) !important;
        }
        .stButton button[data-baseweb="button-secondary"] {
            background: rgba(255, 255, 255, 0.1) !important;
            box-shadow: none !important;
        }
        .stButton button[data-baseweb="button-secondary"]:hover {
            background: rgba(255, 255, 255, 0.15) !important;
        }

        /* Sidebar Specific Button Fix for Horizontal Alignment */
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] .stButton button {
            padding: 10px 4px !important; /* Reduced horizontal padding for auto-scaling */
            font-size: 13px !important;
            min-width: 0 !important;
            width: 100% !important;
            height: 40px !important; /* Slightly more compact */
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            white-space: nowrap !important;
            overflow: hidden !important;
        }

        /* Premium File Uploader */
        .stFileUploader {
            background: var(--card-glass) !important;
            border: 2px dashed var(--border-glass) !important;
            border-radius: 16px !important;
            padding: 2rem !important;
            transition: all 0.3s ease !important;
        }
        .stFileUploader:hover {
            border-color: var(--primary) !important;
            background: rgba(255, 255, 255, 0.08) !important;
        }

        /* Pinned Chat Input */
        .stChatInput {
            border-radius: 16px !important;
            border: 1px solid var(--border-glass) !important;
            background: rgba(15, 23, 42, 0.6) !important;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2) !important;
        }
        .stChatInput:focus-within {
            border-color: var(--primary) !important;
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2) !important;
        }

        /* Premium Summary Section Styling */
        .summary-box {
            background: var(--card-glass) !important;
            border: 1px solid var(--border-glass) !important;
            border-radius: 24px !important;
            padding: 2.5rem !important;
            margin: 1.5rem 0 !important;
            font-family: 'Inter', sans-serif !important;
            line-height: 1.8 !important;
            box-shadow: 0 15px 50px rgba(0,0,0,0.3) !important;
            backdrop-filter: blur(15px) !important;
            -webkit-backdrop-filter: blur(15px) !important;
            word-wrap: break-word !important;
            overflow-wrap: break-word !important;
            background: linear-gradient(180deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.03) 100%);
        }
        .summary-box h1, .summary-box h2, .summary-box h3 {
            font-family: 'Outfit', sans-serif !important;
            color: white !important;
            margin-top: 1.8rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.5px !important;
        }
        .summary-box h1 { color: var(--primary) !important; font-size: 2rem !important; }
        .summary-box h2 { color: #E2E8F0 !important; font-size: 1.5rem !important; margin-top: 2rem !important; }
        .summary-box h3 { color: #94A3B8 !important; font-size: 1.25rem !important; margin-top: 1.5rem !important; }
        .summary-box table {
            display: block !important;
            overflow-x: auto !important;
            width: 100% !important;
            border-collapse: collapse !important;
            margin: 1.5rem 0 !important;
            background: rgba(15,23,42,0.5) !important;
            border-radius: 16px !important;
            overflow: hidden !important;
        }
        .summary-box th {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(139, 92, 246, 0.15) 100%) !important;
            padding: 14px 16px !important;
            text-align: left !important;
            color: #fff !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            border-bottom: 1px solid var(--border-glass) !important;
        }
        .summary-box td {
            padding: 14px 16px !important;
            border-bottom: 1px solid var(--border-glass) !important;
            color: #CBD5E1 !important;
            font-size: 14px !important;
            border-top: 1px solid rgba(255,255,255,0.03) !important;
        }
        .summary-box tr:hover td {
            background: rgba(255,255,255,0.05) !important;
        }

        /* Premium Metrics Cards */
        .element-container .metric-card {
            background: var(--card-glass) !important;
            border: 1px solid var(--border-glass) !important;
            border-radius: 16px !important;
            padding: 1.5rem !important;
            text-align: center !important;
            transition: all 0.3s ease !important;
        }
        .element-container .metric-card:hover {
            background: rgba(255,255,255,0.08) !important;
            transform: translateY(-2px) !important;
        }
        .element-container .metric-card .metric-value {
            font-size: 2rem !important;
            font-weight: 700 !important;
            color: white !important;
            font-family: 'Outfit', sans-serif !important;
        }
        .element-container .metric-card .metric-label {
            color: #94A3B8 !important;
            font-size: 0.875rem !important;
            margin-top: 0.25rem !important;
        }

        /* Premium Info Box Styling */
        .stInfo {
            background: rgba(99, 102, 241, 0.1) !important;
            border: 1px solid rgba(99, 102, 241, 0.3) !important;
            border-radius: 12px !important;
            padding: 1rem !important;
        }
        .stWarning {
            background: rgba(245, 158, 11, 0.1) !important;
            border: 1px solid rgba(245, 158, 11, 0.3) !important;
            border-radius: 12px !important;
            padding: 1rem !important;
        }

        /* Premium Expander */
        details[data-testid="stExpander"] {
            background: var(--card-glass) !important;
            border: 1px solid var(--border-glass) !important;
            border-radius: 12px !important;
            margin: 1rem 0 !important;
        }
        details[data-testid="stExpander"] summary {
            color: var(--primary) !important;
            font-weight: 600 !important;
        }

        /* Premium Divider */
        hr {
            border: 0 !important;
            height: 1px !important;
            background: var(--border-glass) !important;
            margin: 2rem 0 !important;
        }

        /* Premium Caption */
        .stCaption {
            color: #94A3B8 !important;
            font-size: 0.875rem !important;
        }

        /* Premium Table Fix for Main Workspace */
        [data-testid="stMarkdownContainer"] table {
            display: block !important;
            overflow-x: auto !important;
            width: 100% !important;
            border-collapse: collapse !important;
            margin: 1rem 0 !important;
            background: rgba(15,23,42,0.5) !important;
            border-radius: 12px !important;
        }
        [data-testid="stMarkdownContainer"] table th,
        [data-testid="stMarkdownContainer"] table td {
            padding: 10px 12px !important;
            border: 1px solid rgba(255,255,255,0.05) !important;
        }
        [data-testid="stMarkdownContainer"] table th {
            background: rgba(99, 102, 241, 0.15) !important;
            color: white !important;
            font-weight: 600 !important;
        }

        /* Premium Data Manager Cards */
        .data-manager-card {
            background: var(--card-glass) !important;
            border: 1px solid var(--border-glass) !important;
            border-radius: 20px !important;
            padding: 1.25rem 2rem !important;
            transition: all 0.3s ease !important;
            background: linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%) !important;
            backdrop-filter: blur(10px) !important;
        }
        .data-manager-card:hover {
            background: rgba(255, 255, 255, 0.08) !important;
            border-color: rgba(99, 102, 241, 0.3) !important;
            transform: scale(1.005);
        }
        .file-icon-box {
            font-size: 2.2rem !important;
            background: rgba(255, 255, 255, 0.05);
            width: 60px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 14px;
            flex-shrink: 0;
        }
        .activate-button-container {
            width: 140px;
            flex-shrink: 0;
            display: flex;
            align-items: center;
        }
        .activate-button-container .stButton button {
            height: 48px !important;
            border-radius: 12px !important;
            background: var(--gradient-primary) !important;
            width: 100% !important;
        }

        /* Settings Dashboard Styles */
        .settings-section-card {
            background: var(--card-glass) !important;
            border: 1px solid var(--border-glass) !important;
            border-radius: 20px !important;
            padding: 2.5rem !important;
            margin-bottom: 2rem !important;
            backdrop-filter: blur(15px) !important;
            -webkit-backdrop-filter: blur(15px) !important;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2) !important;
        }
        .settings-header {
            font-family: "Outfit", sans-serif !important;
            color: white !important;
            font-size: 1.4rem !important;
            font-weight: 700 !important;
            margin-bottom: 0.5rem !important;
            display: flex !important;
            align-items: center !important;
            gap: 0.75rem !important;
        }
        .settings-label {
            color: #E2E8F0 !important;
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            margin-bottom: 0.25rem !important;
        }
        .settings-helper {
            color: #94A3B8 !important;
            font-size: 0.85rem !important;
            margin-bottom: 1rem !important;
        }
        .settings-divider {
            height: 1px;
            background: rgba(255,255,255,0.06);
            margin: 1.5rem 0;
        }

        /* Read-only Data Dashboard Styles */
        .dash-row {
            display: flex !important;
            justify-content: space-between !important;
            align-items: center !important;
            padding: 0.75rem 0 !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04) !important;
        }
        .dash-row:last-child {
            border-bottom: none !important;
        }
        .dash-label {
            color: #94A3B8 !important;
            font-size: 0.95rem !important;
            font-weight: 500 !important;
        }
        .dash-value {
            color: white !important;
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            font-family: 'Inter', monospace !important;
            background: rgba(99, 102, 241, 0.1) !important;
            padding: 4px 12px !important;
            border-radius: 6px !important;
            border: 1px solid rgba(99, 102, 241, 0.2) !important;
        }
        .dash-status-running {
            color: #10B981 !important;
            font-weight: 700 !important;
            display: flex !important;
            align-items: center !important;
            gap: 6px !important;
        }
        .dash-status-running::before {
            content: "" !important;
            width: 8px !important;
            height: 8px !important;
            background: #10B981 !important;
            border-radius: 50% !important;
            display: inline-block !important;
            box-shadow: 0 0 10px #10B981 !important;
        }
        </style>
    """, unsafe_allow_html=True)

from datamind.tools.stats import DatasetStats

def render_left_panel_metrics(stats: DatasetStats):
    """Render top metrics in a premium grid using pre-computed statistics."""
    st.markdown("""
        <div style='margin-bottom: 1.5rem;'>
            <h3 style='margin: 0; font-family: "Outfit"; font-weight: 700; color: white; letter-spacing: -0.5px;'>Dataset Essentials</h3>
            <p style='margin: 0.5rem 0 0 0; color: #94A3B8; font-size: 0.875rem;'>High-fidelity dataset profiling (Universal Unsupervised Model)</p>
        </div>
    """, unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
            <div style='background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 1.25rem; text-align: center; transition: all 0.3s ease;'>
                <div style='font-size: 2rem; font-weight: 700; color: white; font-family: "Outfit"; margin-bottom: 0.5rem;'>{stats.row_count:,}</div>
                <div style='color: #94A3B8; font-size: 0.875rem;'>Rows</div>
            </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
            <div style='background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 1.25rem; text-align: center; transition: all 0.3s ease;'>
                <div style='font-size: 2rem; font-weight: 700; color: white; font-family: "Outfit"; margin-bottom: 0.5rem;'>{stats.column_count:,}</div>
                <div style='color: #94A3B8; font-size: 0.875rem;'>Columns</div>
            </div>
        """, unsafe_allow_html=True)
    with c3:
        # Display memory usage from pre-computed stats
        st.markdown(f"""
            <div style='background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 1.25rem; text-align: center; transition: all 0.3s ease;'>
                <div style='font-size: 2rem; font-weight: 700; color: white; font-family: "Outfit"; margin-bottom: 0.5rem;'>{stats.memory_usage_mb:.1f}</div>
                <div style='color: #94A3B8; font-size: 0.875rem;'>MB Usage</div>
            </div>
        """, unsafe_allow_html=True)
    with c4:
        # Calculate overall clarity/quality score based on nulls and warnings
        quality_score = max(0, 100 - (len(stats.data_quality_warnings) * 10) - (sum(stats.null_percent.values()) / (len(stats.null_percent or [1]) * 2)))
        st.markdown(f"""
            <div style='background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 1.25rem; text-align: center; transition: all 0.3s ease;'>
                <div style='font-size: 2rem; font-weight: 700; color: #10B981; font-family: "Outfit"; margin-bottom: 0.5rem;'>{quality_score:.0f}%</div>
                <div style='color: #94A3B8; font-size: 0.875rem;'>Data Integrity</div>
            </div>
        """, unsafe_allow_html=True)


def _clean_md_block(t: str) -> str:
    if not isinstance(t, str): return ""
    t = re.sub(r'<<<BRIEF>>>|<<<DETAILED>>>|\[GRAPH CAPTIONS\]', '', t).strip()
    if t.startswith('```'):
        t = re.sub(r'^```[a-zA-Z]*\n?', '', t)
        t = re.sub(r'\n?```$', '', t)
    
    # Prevent multi-space indenting from triggering markdown code blocks
    lines = t.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.lstrip()
        if (line.startswith('    ') or line.startswith('\t')) and not (stripped.startswith('-') or stripped.startswith('*')):
            cleaned_lines.append(stripped)
        else:
            cleaned_lines.append(line)
            
    return '\n'.join(cleaned_lines).strip()

def render_summary_section(dossier: Any, predictions: dict = None, mode: str = "all"):
    """Render the dossier and/or predictions based on the current Lab mode."""
    # Guard: Only exit early if everything is missing AND we aren't specifically initializing projections
    if not dossier and not predictions and mode != "prediction":
        st.info("👋 Welcome! Upload a dataset to generate insights.")
        return

    # 1. CORE BRIEFING (Analysis Lab or All)
    if mode in ["all", "analysis"]:
        if isinstance(dossier, str):
            st.markdown(f'<div class="summary-box">{dossier}</div>', unsafe_allow_html=True)
        else:
            st.markdown("### 🔍 Automated Insight Briefing")
            with st.container(border=True):
                # Extract the narrative: Use lab_narrative (Theory) priority, fallback to response (Brief)
                text = dossier.get("lab_narrative", dossier.get("response", ""))
                
                # Cleanup: Strip any inadvertently leaked tags
                if isinstance(text, str):
                    text = _clean_md_block(text)

                # Ensure proper structure: Introduction, Explanation, Visuals
                if text:
                    # Clean up the text to prevent header overlap
                    if text.strip().startswith("#"):
                        st.markdown(text)
                    else:
                        # Add a default header ONLY if no major headers appear in the first 100 chars
                        if "## " not in text[:100] and "# " not in text[:100]:
                            st.markdown(f"## Introduction\n\n{text}")
                        else:
                            st.markdown(text)
                else:
                    st.warning("⚠️ Analytical narrative is being decoded. Refresh may be required.")

                if dossier.get("figures"):
                    st.divider()
                    st.markdown("#### 📐 Data Distributions & Evidence")
                    figs = dossier["figures"]
                    captions = dossier.get("captions", [])

                    # SINGLE COLUMN FEED for better vertical storytelling
                    for idx, fig in enumerate(figs):
                        st.plotly_chart(fig, width="stretch", key=f"summary_dossier_fig_{idx}_{id(fig)}")
                        if idx < len(captions):
                            # Premium Caption Styling
                            st.markdown(f"""
                            <div style="background: rgba(99, 102, 241, 0.05); border-left: 4px solid #6366F1; padding: 1rem; border-radius: 8px; margin-bottom: 2rem;">
                                <span style="color: #6366F1; font-weight: 600;">💡 TACTICAL INSIGHT:</span> {captions[idx]}
                            </div>
                            """, unsafe_allow_html=True)

    # 2. PREDICTIVE FORECAST (Prediction Lab or All)
    if mode in ["all", "prediction"]:
        if predictions:
            st.markdown("---")
            st.markdown("### 🔮 Strategic Forecasting Report")
            with st.container(border=True):
                if predictions.get("fig"):
                    st.plotly_chart(predictions["fig"], width="stretch")
                
                # Extract and cleanup the narrative
                pred_text = predictions.get("lab_narrative", predictions.get("response", ""))
                if isinstance(pred_text, str):
                    pred_text = _clean_md_block(pred_text)
                
                if pred_text:
                    st.markdown(pred_text)
        elif mode == "prediction" or (mode == "all" and not predictions):
            st.markdown("---")
            st.markdown("#### 🔮 Strategic Forecasting Lab")
            st.caption("Initialize the deep-dive predictive forecast to simulate business impact scenarios.")
            if st.button("🚀 Initialize Predictive Impact Forecast", width="stretch", type="primary"):
                from datamind.agent.summary_agent import SummaryAgent
                from datamind.memory.session import get_dataframe, set_predictions
                df = get_dataframe()
                if df is not None:
                    with st.spinner("Simulating Strategic \"What-If\" Scenarios..."):
                        agent = SummaryAgent()
                        preds = agent.generate_predictions(df)
                        set_predictions(preds)
                        st.rerun()

def render_chat_interface(chat_history: List[Dict[str, Any]], filter_category: Optional[str] = None):
    """Render tiered chat history with metadata badges."""
    # Anchor for CSS to find this container
    # Premium Header
    st.markdown("""
        <div class="chat-drawer-anchor" style='margin-bottom: 0.75rem; margin-top: -0.25rem; padding: 0; display: block !important;'>
            <h2 style='margin: 0; padding: 0; font-family: "Outfit", sans-serif; font-weight: 700; color: white; letter-spacing: -px; line-height: 1;'>Chatbot</h2>
            <p style='margin: 0.3rem 0 0 0; padding: 0; color: #94A3B8; font-size: 0.85rem;'>Dialogue history and reasoning</p>
        </div>
    """, unsafe_allow_html=True)

    # Render messages
    for i, msg in enumerate(chat_history):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        tier = msg.get("tier", 1)
        latency = msg.get("latency", 0)
        
        with st.chat_message(role):
            # Assistant Metadata Badge
            if role == "assistant" and not msg.get("is_status"):
                badge_color = "#10B981" if tier == 1 else "#3B82F6" if tier == 2 else "#8B5CF6"
                badge_text = "⚡ Instant" if tier == 1 else "💬 Quick" if tier == 2 else "🔬 Deep Analysis"
                
                st.markdown(f"""
                    <div style='display: flex; align-items: center; gap: 8px; margin-bottom: 4px;'>
                        <span style='background: {badge_color}22; color: {badge_color}; padding: 2px 8px; border-radius: 4px; font-size: 0.65rem; font-weight: 700; border: 1px solid {badge_color}44;'>{badge_text}</span>
                        <span style='color: #64748B; font-size: 0.65rem;'>{latency}ms</span>
                    </div>
                """, unsafe_allow_html=True)

            st.markdown(content)

            if "figures" in msg and msg["figures"]:
                target = msg.get("category", "analysis")
                if target == "simulation":
                    st.info("✅ Rendered to Simulation Lab ↑")
                else:
                    st.info("✅ Rendered to Analysis Lab ↑")

    # Space before input
    st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)
    return None

def render_main_stage_artifacts(chat_history: List[Dict[str, Any]], filter_category: Optional[str] = None):
    """Render large artifacts filtered by their scientific context (forensics vs simulation)."""
    artifacts_found = False
    
    # Only show if there's history
    if not chat_history:
        return

    # Pre-check for any visible artifacts to show global header
    # Ensure we only count messages with actual content (not empty Mission 0 messages)
    has_visible_artifacts = any(
        (m.get("figures") and len(m.get("figures")) > 0) or m.get("lab_narrative") 
        for m in chat_history 
        if not filter_category or m.get("category") == filter_category
    )
    
    if has_visible_artifacts:
        st.markdown("---")
        if not filter_category:
            st.markdown("### 🧪 Consolidated Laboratory Results")
        else:
            header_text = "🧪 Analysis Laboratory Results" if filter_category == "analysis" else "🔬 Prediction Laboratory Results"
            st.markdown(f"### {header_text}")

    for i, msg in enumerate(chat_history):
        # Apply filtering logic
        if filter_category and msg.get("category") != filter_category:
            continue
        
        # Only render if there's actual visual or narrative content
        if msg.get("figures") or msg.get("lab_narrative"):
            artifacts_found = True
            with st.container():
                session_type = "Analysis Laboratory" if msg.get("category") == "analysis" else "Prediction Laboratory"
                st.markdown(f"### {session_type} Results (Mission {i+1})")
                
                charts = msg.get("figures", [])
                captions = msg.get("captions", [])
                
                # 1. Render Visual Artifacts (Charts/Tables)
                for j, chart in enumerate(charts):
                    if isinstance(chart, Figure):
                        st.plotly_chart(chart, width="stretch", key=f"lab_artifact_fig_{i}_{j}_{id(chart)}")
                        if j < len(captions):
                            st.info(f"💡 {captions[j]}")
                
                # 2. Render Deep Analytical Narrative (Persistent Workspace)
                if msg.get("lab_narrative"):
                    with st.expander("📖 View Strategic Deep-Dive Narrative", expanded=True):
                        narrative = msg["lab_narrative"]
                        # Ensure proper header format
                        narrative = _clean_md_block(narrative)
                        if narrative and "## " not in narrative[:200]:
                            st.markdown(f"## Introduction\n\n{narrative}")
                        else:
                            st.markdown(narrative)
                
                st.markdown("---")
    
    if not artifacts_found:
        st.caption("Request a chart or table in chat to see it rendered here in high resolution.")

def render_file_uploader():
    """Unified file ingestion component for all analytical labs."""
    from datamind.memory.session import (
        get_dataframe, set_summary_text, handle_file_upload
    )
    from datamind.agent.summary_agent import SummaryAgent
    from datamind.agent.viz_agent import VizAgent
    from config import OLLAMA_MODEL

    user = st.session_state.get("current_user")
    if not user: return

    # Ingest New Analytical Asset
    with st.expander("📥 Ingest New Analytical Asset", expanded=(get_dataframe() is None)):
        uploaded_file = st.file_uploader(
            "Upload Asset (MAX 50MB per file • CSV, XLSX, XLS, JSON, PARQUET)", 
            type=["csv", "xlsx", "xls", "json", "parquet"], 
            label_visibility="visible",
            key=f"unified_uploader_{st.session_state.get('main_nav', 'dash')}"
        )
        
        if uploaded_file:
            # Check if processing is needed
            needs_processing = (
                st.session_state.get("current_file_name") != uploaded_file.name or 
                get_dataframe() is None
            )

            if needs_processing:
                with st.spinner("Decoding DNA of Asset..."):
                    df = handle_file_upload(uploaded_file, user['id'])
                    
                    if df is not None:
                        # Clear old state and trigger analysis
                        set_summary_text(None)
                        agent = SummaryAgent(model=st.session_state.get("selected_model", OLLAMA_MODEL))
                        dossier = agent.summarize_dossier(df)
                        set_summary_text(dossier)
                        
                        viz = VizAgent(df)
                        viz.generate_and_cache_top_charts()
                        
                        # Cache the results for instant recall later
                        from database import upsert_analytical_cache
                        import json
                        
                        # Remove non-serializable figures before caching
                        cache_payload = dossier.copy() if isinstance(dossier, dict) else {"text": dossier}
                        if "figures" in cache_payload: del cache_payload["figures"]
                        
                        upsert_analytical_cache(st.session_state["current_file_id"], json.dumps(cache_payload), "") 
                        
                        st.rerun()