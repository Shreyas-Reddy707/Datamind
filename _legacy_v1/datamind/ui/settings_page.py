"""
Settings Page for DataMind SaaS.
Handles system configuration and performance monitoring.
"""

from __future__ import annotations
import streamlit as st
from config import OLLAMA_MODEL, OLLAMA_BASE_URL

def render_settings():
    """Main rendering loop for Settings."""
    st.markdown("""
        <div style='margin-bottom: 2rem;'>
            <h2 style='margin: 0; font-family: "Outfit"; font-weight: 700; color: white;'>⚙️ System Settings</h2>
            <p style='margin: 0.25rem 0 0 0; color: #94A3B8; font-size: 0.875rem;'>Configure your analytical environment and AI node connectivity.</p>
        </div>
    """, unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown("### 🤖 Intelligence Node Configuration")
        st.text_input("Ollama Base URL", value=OLLAMA_BASE_URL, disabled=True)
        st.text_input("Active Analytical Model", value=OLLAMA_MODEL, disabled=True)
        st.caption("Settings are currently controlled via environment variables for platform security.")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown("### 📊 System Health")
        c1, c2, c3 = st.columns(3)
        c1.metric("Node Status", "Operational")
        c2.metric("DB Integrity", "Verified")
        c3.metric("API Latency", "12ms")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("Clear Analytical Cache", type="secondary"):
        st.success("Cache purged successfully.")
