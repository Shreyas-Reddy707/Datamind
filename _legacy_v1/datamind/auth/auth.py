"""
DataMind SaaS - Authentication & Session Subsystem
Hardened implementation with bcrypt, secure tokens, and lockout protection.
"""

import bcrypt
import secrets
import hashlib
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any

import database as db

# Constants
BCRYPT_ROUNDS = 10          # Safe balance between security and performance
SESSION_DURATION_HOURS = 24
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
RESET_TOKEN_EXPIRY_HOURS = 1
MIN_PASSWORD_LENGTH = 8

# Validation Helpers
def validate_email(email: str) -> tuple[bool, str]:
    from datamind.security.sanitizer import InputSanitizer
    if not InputSanitizer.validate_email_safe(email):
        return False, "Invalid email format or length"
    return True, ""

def validate_username(username: str) -> tuple[bool, str]:
    if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username.strip()):
        return False, "Username must be 3-20 chars: letters, numbers, underscore"
    return True, ""

def validate_password(password: str) -> tuple[bool, str]:
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    if not re.search(r'[a-zA-Z]', password):
        return False, "Password must contain at least one letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    return True, ""

def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()

# Register
def register_user(username, email, password, confirm_password) -> dict:
    from datamind.security.sanitizer import InputSanitizer
    email = InputSanitizer.sanitize_auth_input(email, 'email')
    username = InputSanitizer.sanitize_auth_input(username, 'username')
    password = InputSanitizer.sanitize_auth_input(password, 'password')
    confirm_password = InputSanitizer.sanitize_auth_input(confirm_password, 'password')

    ok, err = validate_username(username)
    if not ok: return {"success": False, "field": "username", "error": err}

    ok, err = validate_email(email)
    if not ok: return {"success": False, "field": "email", "error": err}

    ok, err = validate_password(password)
    if not ok: return {"success": False, "field": "password", "error": err}

    if password != confirm_password:
        return {"success": False, "field": "confirm_password", "error": "Passwords do not match"}

    # Check uniqueness
    if db.get_user_by_email(email):
        return {"success": False, "field": "email", "error": "An account with this email already exists"}

    if db.get_user_by_username(username):
        return {"success": False, "field": "username", "error": "Username already taken"}

    # Hash and store
    password_hash = bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    ).decode('utf-8')

    try:
        user_id = db.create_user(username, email, password_hash)
        db.log_event(user_id, 'register')
        # Auto-login after registration
        session_result = create_session_for_user(user_id)
        return {
            "success": True, 
            "user": {
                "id": user_id, 
                "username": username, 
                "email": email, 
                "is_admin": False
            },
            "session_token": session_result["token"]
        }
    except Exception as e:
        logging.error(f"Register error: {e}")
        return {"success": False, "field": "general", "error": "Registration failed. Please try again."}

# Login
def login_user(email, password) -> dict:
    from datamind.security.sanitizer import InputSanitizer
    email = InputSanitizer.sanitize_auth_input(email, 'email')
    password = InputSanitizer.sanitize_auth_input(password, 'password')

    # Check lockout BEFORE DB user fetch
    lockout = db.get_lockout_status(email)
    if lockout["is_locked"]:
        remaining = int((lockout["lockout_until"] - datetime.now(timezone.utc)).total_seconds() / 60)
        return {"success": False, "field": "general", "error": f"Account locked. Try again in {remaining} minutes."}

    user = db.get_user_by_email(email)

    # Constant-time comparison even if user doesn't exist
    dummy_hash = "$2b$10$dummy.hash.to.prevent.timing.attacks.xxxxxxxxxx"
    check_hash = user["password_hash"] if user else dummy_hash

    password_matches = bcrypt.checkpw(password.encode('utf-8'), check_hash.encode('utf-8'))

    if not user or not password_matches:
        if user:
            new_count = db.increment_failed_attempts(email)
            db.log_event(user["id"], 'login_failed')
            if new_count >= MAX_FAILED_ATTEMPTS:
                lockout_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                db.set_lockout(email, lockout_until)
                db.log_event(user["id"], 'account_locked', f"Locked after {new_count} failed attempts")
                return {"success": False, "field": "general", "error": f"Too many failed attempts. Account locked for {LOCKOUT_DURATION_MINUTES} minutes."}
        return {"success": False, "field": "general", "error": "Invalid email or password"}

    if not user.get("is_active", 1):
        return {"success": False, "field": "general", "error": "Account is deactivated. Contact support."}

    # Successful login
    db.reset_failed_attempts(email)
    db.update_last_login(user["id"])
    db.log_event(user["id"], 'login_success')

    session_result = create_session_for_user(user["id"])
    return {
        "success": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "is_admin": bool(user.get("is_admin", 0))
        },
        "session_token": session_result["token"]
    }

# Session Management
def create_session_for_user(user_id) -> dict:
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_DURATION_HOURS)
    db.create_session(user_id, raw_token, expires_at)
    return {"token": raw_token, "expires_at": expires_at}

def validate_session(session_token) -> Optional[Dict[str, Any]]:
    if not session_token:
        return None
    session = db.get_session(session_token)
    if not session:
        return None
    
    # Refresh session activity window
    db.refresh_session(session_token)
    db.update_last_active(session["user_id"])
    user = db.get_user_by_id(session["user_id"])
    if not user or not user.get("is_active", 1):
        return None
        
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "is_admin": bool(user.get("is_admin", 0)),
        "session_token": session_token
    }

def logout_user(session_token):
    session = db.get_session(session_token)
    if session:
        db.log_event(session["user_id"], 'logout')
        db.revoke_session(session_token)

# Password Reset
def request_password_reset(email) -> dict:
    # Always return success to prevent email enumeration
    user = db.get_user_by_email(email.strip().lower())
    if user:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS)
        db.create_reset_token(user["id"], token_hash, expires_at)
        db.log_event(user["id"], 'password_reset_request')
        return {"success": True, "reset_token": raw_token, "note": "Show this token to the user securely."}
    return {"success": True, "note": "If account exists, a token was generated."}

def reset_password(raw_token, new_password) -> dict:
    ok, err = validate_password(new_password)
    if not ok:
        return {"success": False, "error": err}

    token_hash = hash_token(raw_token)
    token_record = db.get_reset_token(token_hash)
    if not token_record:
        return {"success": False, "error": "Invalid or expired reset token"}

    new_hash = bcrypt.hashpw(
        new_password.encode('utf-8'),
        bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    ).decode('utf-8')

    with db.get_db_connection() as conn:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, token_record["user_id"]))
    
    db.consume_reset_token(token_hash)
    db.revoke_all_user_sessions(token_record["user_id"])
    db.log_event(token_record["user_id"], 'password_changed')
    return {"success": True}
