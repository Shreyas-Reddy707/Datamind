"""
Account Page for DataMind SaaS.
Handles user profile and portfolio export.
"""

from __future__ import annotations
import streamlit as st
import datetime

def render_account():
    """Main rendering loop for Account."""
    user = st.session_state.get("current_user")
    if not user: return

    st.markdown("""
        <div style='margin-bottom: 2rem;'>
            <h2 style='margin: 0; font-family: "Outfit"; font-weight: 700; color: white;'>👤 User Profile</h2>
            <p style='margin: 0.25rem 0 0 0; color: #94A3B8; font-size: 0.875rem;'>Manage your identity and export your analytical dossiers.</p>
        </div>
    """, unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown(f"### Profile Details")
        st.write(f"**Username**: {user.get('username', 'Guest')}")
        st.write(f"**Email Partition**: {user.get('email', 'N/A')}")
        role = "ADMIN" if user.get('is_admin') else "GUEST" if user.get('is_guest') else "USER"
        st.write(f"**Security Role**: {role}")
        st.write(f"**Member Since**: April 2026")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown("### 📄 Data Export")
        st.write("Generate a comprehensive Markdown report of your current session's analytical findings.")
        
        if st.button("Generate Executive Dossier (.md)", type="primary"):
            from datamind.memory.session import get_chat_history
            history = get_chat_history()
            report = f"# DataMind Executive Dossier\n\nGenerated on {datetime.datetime.now()}\n\n"
            for msg in history:
                report += f"## {msg['role'].upper()}\n{msg['content']}\n\n"
            st.download_button("Download Report", report, file_name="datamind_dossier.md")
