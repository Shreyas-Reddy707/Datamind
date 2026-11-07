"""
Data Manager for DataMind SaaS.
Handles universal file library management with a professional File Explorer UI.
"""

from __future__ import annotations
import streamlit as st
from database import get_user_files
from datamind.memory.session import activate_data_asset

def render_data_manager():
    """Renders a high-fidelity File Explorer for managing analytical assets."""
    user = st.session_state.get("current_user")
    if not user: return
    
    st.markdown("""
        <div style='margin-bottom: 2rem;'>
            <h2 style='margin: 0; font-family: "Outfit"; font-weight: 800; color: white; letter-spacing: -0.5px;'>Analytical Data Portfolio</h2>
            <p style='margin: 0.5rem 0 0 0; color: #94A3B8; font-size: 0.95rem;'>Universal asset management with instant context activation.</p>
        </div>
    """, unsafe_allow_html=True)
    
    files = get_user_files(user['id'])
    
    if not files:
        st.info("Your portfolio is currently empty. Ingest a dataset via the Dashboard or Laboratories to begin.")
        return

    # File Explorer Header
    st.markdown("""
        <div style='display: grid; grid-template-columns: 3.5rem 2fr 1fr 1fr 1fr 120px; padding: 0.75rem 1.5rem; background: rgba(255,255,255,0.05); border-radius: 12px; margin-bottom: 1rem; border: 1px solid rgba(255,255,255,0.08);'>
            <div style='color: #64748B; font-weight: 600; font-size: 0.8rem;'>ICON</div>
            <div style='color: #64748B; font-weight: 600; font-size: 0.8rem;'>NAME</div>
            <div style='color: #64748B; font-weight: 600; font-size: 0.8rem;'>ROWS</div>
            <div style='color: #64748B; font-weight: 600; font-size: 0.8rem;'>COLUMNS</div>
            <div style='color: #64748B; font-weight: 600; font-size: 0.8rem;'>SIZE</div>
            <div style='color: #64748B; font-weight: 600; font-size: 0.8rem; text-align: right;'>ACTION</div>
        </div>
    """, unsafe_allow_html=True)

    for f in files:
        file_id = f['global_file_id']
        is_active = st.session_state.get("current_file_id") == file_id
        ext = f['original_filename'].split('.')[-1].upper() if '.' in f['original_filename'] else 'FILE'
        
        # Color based on extension
        ext_colors = {"CSV": "#10B981", "XLSX": "#10B981", "JSON": "#F59E0B", "PARQUET": "#6366F1"}
        color = ext_colors.get(ext, "#94A3B8")
        
        card_bg = "rgba(99, 102, 241, 0.08)" if is_active else "rgba(255,255,255,0.02)"
        card_border = "1px solid rgba(99, 102, 241, 0.3)" if is_active else "1px solid rgba(255,255,255,0.06)"
        
        with st.container():
            c1, c2, c3, c4, c5, c6 = st.columns([0.4, 2, 1, 1, 1, 1])
            
            with c1:
                st.markdown(f"""
                    <div style='background: {color}22; color: {color}; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: 10px; font-size: 0.7rem; font-weight: 800; border: 1px solid {color}44;'>
                        {ext}
                    </div>
                """, unsafe_allow_html=True)
            
            with c2:
                name_style = "color: white; font-weight: 700;" if is_active else "color: #E2E8F0; font-weight: 500;"
                st.markdown(f"<div style='margin-top: 8px; {name_style} font-size: 1rem;'>{f['original_filename']}</div>", unsafe_allow_html=True)
            
            with c3:
                st.markdown(f"<div style='margin-top: 10px; color: #94A3B8; font-size: 0.9rem;'>{f['row_count']:,}</div>", unsafe_allow_html=True)
                
            with c4:
                st.markdown(f"<div style='margin-top: 10px; color: #94A3B8; font-size: 0.9rem;'>{f['col_count']:,}</div>", unsafe_allow_html=True)
            
            with c5:
                # Use default 0 if size is missing (new schema might not have it in global_files yet, but we'll adapt)
                file_size = f.get('file_size_bytes', 0)
                size_mb = file_size / (1024 * 1024)
                size_str = f"{size_mb:.2f} MB" if size_mb > 0.1 else f"{file_size/1024:.1f} KB"
                st.markdown(f"<div style='margin-top: 10px; color: #94A3B8; font-size: 0.9rem;'>{size_str}</div>", unsafe_allow_html=True)
            
            with c6:
                if is_active:
                    st.button("Active", key=f"active_{file_id}", disabled=True, width="stretch")
                else:
                    if st.button("Activate", key=f"activate_{file_id}", type="primary", width="stretch"):
                        # Trigger Activation and Redirection
                        success = activate_data_asset(file_id, user['id'])
                        if success:
                            st.session_state["main_nav"] = "Dashboard"
                            st.rerun()
                        else:
                            st.error("Failed to activate asset context.")
                            
            st.markdown("<div style='height: 1px; background: rgba(255,255,255,0.03); margin: 0.5rem 0;'></div>", unsafe_allow_html=True)
