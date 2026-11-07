"""
DataMind SaaS - Authentication Page
Premium, glassmorphic UI for user login, registration, and guest access.
"""

import streamlit as st
import uuid
import logging
from datamind.auth import auth

import base64

def get_logo_base64():
    try:
        with open("assets/logo.jpg", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

def show_auth_page():
    """Centered auth portal with tabbed navigation."""
    
    # Custom CSS for the centered auth card & premium aesthetics
    st.markdown("""
        <style>
        .auth-container {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 80vh;
        }
        .auth-card {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 3rem;
            width: 450px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            margin: auto;
        }
        .auth-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        .auth-logo {
            font-family: 'Outfit', sans-serif;
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #6366F1 0%, #8B5CFD 50%, #EC4899 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        .auth-subtitle {
            color: #94A3B8;
            font-size: 0.875rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # Use a container to center
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        img_b64 = get_logo_base64()
        logo_img = f'<img src="data:image/jpeg;base64,{img_b64}" style="width: 50px; height: 50px; border-radius: 12px; vertical-align: middle; margin-right: 12px; margin-bottom: 8px;" />' if img_b64 else ''
        
        st.markdown(f"""
            <div class="auth-header">
                <div class="auth-logo">{logo_img}DataMind SaaS</div>
                <div class="auth-subtitle">Autonomous Intelligence for Modern Enterprises</div>
            </div>
        """, unsafe_allow_html=True)

        # Tab state
        if "auth_tab" not in st.session_state:
            st.session_state["auth_tab"] = "signin"

        # Tab selector (3 styled buttons)
        c1, c2, c3 = st.columns(3)
        if c1.button("Sign In", type="primary" if st.session_state["auth_tab"]=="signin" else "secondary", width="stretch"):
            st.session_state["auth_tab"] = "signin"
            st.rerun()
        if c2.button("Register", type="primary" if st.session_state["auth_tab"]=="register" else "secondary", width="stretch"):
            st.session_state["auth_tab"] = "register"
            st.rerun()
        if c3.button("Guest", type="primary" if st.session_state["auth_tab"]=="guest" else "secondary", width="stretch"):
            st.session_state["auth_tab"] = "guest"
            st.rerun()

        st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)

        # Render selected tab
        if st.session_state["auth_tab"] == "signin":
            _render_signin_tab()
        elif st.session_state["auth_tab"] == "register":
            _render_register_tab()
        else:
            _render_guest_tab()

def _apply_auth_result(result, identifier):
    """Shared success handler for login + register."""
    if "user" in result:
        st.session_state["current_user"] = result["user"]
    else:
        st.session_state["current_user"] = {
            "id": result["user_id"],
            "username": result["username"],
            "email": result["email"],
            "is_admin": False
        }
    
    st.session_state["_session_token"] = result["session_token"]
    st.query_params["st"] = result["session_token"]
    
    # Clear any auth error state
    for key in list(st.session_state.keys()):
        if key.startswith("auth_error_"):
            del st.session_state[key]
    
    st.rerun()

def _render_signin_tab():
    with st.form("signin_form", border=False):
        email = st.text_input("Email", key="signin_email", placeholder="you@example.com")
        password = st.text_input("Password", type="password", key="signin_password", placeholder="Your password")

        # Show stored error if any
        if st.session_state.get("auth_error_signin"):
            st.error(st.session_state["auth_error_signin"])

        # Disable button while in-flight
        btn_disabled = st.session_state.get("auth_in_flight", False)
        submitted = st.form_submit_button("Sign In", disabled=btn_disabled, use_container_width=True)

    if submitted:
        if not email or not password:
            st.session_state["auth_error_signin"] = "Please enter both email and password"
            st.rerun()

        st.session_state["auth_in_flight"] = True
        
        from datamind.security.rate_limiter import RateLimiter
        rate_result = RateLimiter.check_login(email)
        if not rate_result["allowed"]:
            st.session_state["auth_in_flight"] = False
            st.error(rate_result["message"])
            st.stop()
            
        with st.spinner("Signing in..."):
            result = auth.login_user(email, password)
        st.session_state["auth_in_flight"] = False

        if result["success"]:
            _apply_auth_result(result, email)
        else:
            st.session_state["auth_error_signin"] = result["error"]
            st.rerun()

    # Forgot password expander
    with st.expander("Forgot your password?"):
        reset_email = st.text_input("Enter your email", key="reset_email_input")
        if st.button("Get Reset Token"):
            if reset_email:
                result = auth.request_password_reset(reset_email)
                if result.get("reset_token"):
                    st.code(result["reset_token"])
                    st.caption("Copy this token. It expires in 1 hour.")
                else:
                    st.info("If an account exists for that email, a reset token was generated.")

        new_pass = st.text_input("New Password", type="password", key="reset_new_pass")
        reset_tok = st.text_input("Reset Token", key="reset_tok_input")
        if st.button("Reset Password"):
            if new_pass and reset_tok:
                res = auth.reset_password(reset_tok.strip(), new_pass)
                if res["success"]:
                    st.success("Password reset. Please sign in.")
                else:
                    st.error(res["error"])

def _render_register_tab():
    with st.form("register_form", border=False):
        username = st.text_input("Username", key="reg_username", placeholder="3-20 chars, letters/numbers/_")
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_pass", placeholder="Min 8 chars, 1 letter + 1 number")
        confirm = st.text_input("Confirm Password", type="password", key="reg_confirm")

        # Inline field errors
        for field in ["username", "email", "password", "confirm_password", "general"]:
            err = st.session_state.get(f"auth_error_{field}")
            if err:
                st.error(err)

        btn_disabled = st.session_state.get("auth_in_flight", False)
        submitted = st.form_submit_button("Create Account", disabled=btn_disabled, use_container_width=True)

    if submitted:
        # Clear previous errors
        for key in list(st.session_state.keys()):
            if key.startswith("auth_error_"):
                del st.session_state[key]

        st.session_state["auth_in_flight"] = True
        
        from datamind.security.rate_limiter import RateLimiter
        rate_result = RateLimiter.check_register("default")
        if not rate_result["allowed"]:
            st.session_state["auth_in_flight"] = False
            st.error(rate_result["message"])
            st.stop()
            
        with st.spinner("Creating account..."):
            result = auth.register_user(username, email, password, confirm)
        st.session_state["auth_in_flight"] = False

        if result["success"]:
            _apply_auth_result(result, email)
        else:
            field = result.get("field", "general")
            st.session_state[f"auth_error_{field}"] = result["error"]
            st.rerun()

def _render_guest_tab():
    st.warning("⚠️ Guest sessions are temporary. Files and analyses won't be saved.")
    st.caption("Sign up for free to save your work permanently.")
    if st.button("Continue as Guest", width="stretch"):
        st.session_state["current_user"] = {
            "id": None,
            "username": "Guest",
            "email": None,
            "is_admin": False,
            "is_guest": True,
            "guest_key": str(uuid.uuid4())
        }
        st.session_state["_session_token"] = None
        st.rerun()
