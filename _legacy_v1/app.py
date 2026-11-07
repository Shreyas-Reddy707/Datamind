"""
DataMind SaaS - Master Entry Point
Hardened routing with session persistence and multi-user isolation.
"""

from __future__ import annotations
import streamlit as st
import logging

import database as db
from datamind.auth import auth
import datamind.ui.auth_page as auth_page
from datamind.ui.layout import apply_custom_styles
import datamind.ui.dashboard as d_ui_dash
import datamind.ui.prediction_lab as d_ui_pred
import datamind.ui.data_manager as d_ui_data
import datamind.ui.settings_page as d_ui_settings
import datamind.ui.account_page as d_ui_account
from datamind.ui.left_panel import render_left_panel
from datamind.ui.right_panel import render_right_panel
from datamind.memory import session
import base64

def get_logo_base64():
    try:
        with open("assets/logo.jpg", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

# Page Config (Must be first)
st.set_page_config(
    page_title="DataMind SaaS",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

def restore_session_from_token():
    """Restores user session from state or query params."""
    token = st.session_state.get("_session_token") or \
            st.query_params.get("st")
            
    if token:
        user = auth.validate_session(token)
        if user:
            st.session_state["current_user"] = user
            st.session_state["_session_token"] = token
            # Sync to query params if not there
            if st.query_params.get("st") != token:
                st.query_params["st"] = token
            return True
        else:
            # Token found but invalid/expired - Clear stale state
            st.session_state.pop("current_user", None)
            st.session_state.pop("_session_token", None)
            st.query_params.clear()
            return False
    
    # If no token, we do NOT clear current_user.
    # This allows memory-only guest sessions (which have current_user but no token)
    # to persist through reruns.
    return False

def handle_logout():
    """Revokes session and clears all state."""
    token = st.session_state.get("_session_token")
    if token:
        auth.logout_user(token)
    # Clear ALL session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    # Clear query params
    st.query_params.clear()
    st.rerun()

def check_session_expiry():
    """Validates session on every load (Middleware)."""
    token = st.session_state.get("_session_token")
    if not token:
        return  # guest or not logged in yet
    
    user = auth.validate_session(token)
    if not user:
        st.warning("Your session has expired. Please sign in again.")
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.query_params.clear()
        st.rerun()

def render_main_app(user):
    """Main application shell after successful authentication."""
    # Check session validity (Middleware)
    check_session_expiry()
    
    # Apply Premium Styles
    apply_custom_styles()
    
    # Sidebar Navigation
    with st.sidebar:
        user_name = user.get('username', 'Guest')
        role_label = "Guest" if user.get('is_guest') else "Pro"
        
        st.markdown(f"""
            <div style='padding: 1rem; background: rgba(99, 102, 241, 0.1); border-radius: 16px; border: 1px solid rgba(99, 102, 241, 0.2); margin-bottom: 2rem;'>
                <div style='color: #6366F1; font-weight: 700; font-size: 0.8rem; text-transform: uppercase;'>Signed in as</div>
                <div style='color: white; font-weight: 600; font-size: 1.1rem;'>{user_name}</div>
                <div style='color: #94A3B8; font-size: 0.8rem;'>{role_label} Account</div>
            </div>
        """, unsafe_allow_html=True)

        nav = st.radio(
            "Navigation",
            ["Dashboard", "Analysis Laboratory", "Prediction Laboratory", "Data Manager", "Settings", "Account"],
            label_visibility="collapsed",
            key="main_nav_radio"
        )
        st.session_state["main_nav"] = nav
        
        st.markdown("<div style='margin-top: auto; height: 10vh;'></div>", unsafe_allow_html=True)
        
        if st.button("🚪 Sign Out", width="stretch", type="secondary"):
            handle_logout()

    # Header Section
    img_b64 = get_logo_base64()
    logo_img = f'<img src="data:image/jpeg;base64,{img_b64}" style="width: 45px; height: 45px; border-radius: 12px; margin-right: 4px;" />' if img_b64 else ''
    
    st.markdown(f"""
    <div style='padding: 0.75rem 0 1.5rem 0; border-bottom: 1px solid rgba(255,255,255,0.08); margin-bottom: 2rem;'>
        <div style='display: flex; align-items: center; gap: 1rem;'>
            {logo_img}
            <h1 style='font-family: "Outfit"; font-weight: 800; color: white; margin: 0; font-size: 2.2rem; letter-spacing: -1px;'>
                DataMind <span style='color: #6366F1; font-size: 1.8rem;'>SaaS</span>
            </h1>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Routing
    if nav == "Dashboard":
        col_main, col_chat = st.columns([2.5, 1])
        with col_main:
            d_ui_dash.render_dashboard()
        with col_chat:
            render_right_panel()

    elif nav == "Analysis Laboratory":
        col_main, col_chat = st.columns([2.5, 1])
        with col_main:
            render_left_panel() 
        with col_chat:
            render_right_panel()

    elif nav == "Prediction Laboratory":
        d_ui_pred.render_prediction_lab()

    elif nav == "Data Manager":
        d_ui_data.render_data_manager()

    elif nav == "Settings":
        d_ui_settings.render_settings()

    elif nav == "Account":
        d_ui_account.render_account()

def main():
    # 1. Initialize DB (idempotent)
    db.initialize_database()
    
    # 2. Cleanup expired sessions
    db.cleanup_expired_sessions()
    
    # 3. Pattern decay check (throttled to 24h)
    db.update_pattern_decay()
    
    # 4. Try to restore session
    is_authenticated = restore_session_from_token()
    
    # 5. Route
    if not is_authenticated:
        # Check if we are in guest mode (session state only)
        if st.session_state.get("current_user", {}).get("is_guest"):
            pass # Continue to initialization
        else:
            auth_page.show_auth_page()
            st.stop()
            return

    # 6. Initialize per-user session state
    user = st.session_state["current_user"]
    if not st.session_state.get("session_initialized"):
        session.initialize_session_state()
        # Custom initialization for the user if needed can go here
        st.session_state["session_initialized"] = True

    # 7. Render main app
    from datamind.security.authorizer import SecurityError
    from datamind.security.error_handler import SafeErrorHandler
    
    try:
        render_main_app(user)
    except SecurityError as e:
        SafeErrorHandler.handle(e, 'permission', user.get("id"))
        st.stop()
    except Exception as e:
        SafeErrorHandler.handle(e, 'generic', user.get("id"))
        st.stop()

if __name__ == "__main__":
    main()