"""
DataMind SaaS - Session Memory Subsystem
Manages user-scoped state, file deduplication, and database synchronization with PII protection.
"""

import os
import re
import json
import hashlib
import logging
from typing import Any, Optional, Dict, List
import streamlit as st
import pandas as pd
from plotly.graph_objects import Figure


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

import database as db
from datamind.tools.file_loader import UniversalFileLoader
from config import UPLOADS_DIR, OLLAMA_MODEL

def initialize_session_state() -> None:
    """Initialize all session state variables with defaults."""
    defaults = {
        "current_user": None,  # Shared with app.py/auth.py
        "df": None,
        "current_file_id": None,
        "schema_fingerprint": None,
        "summary_text": None,
        "chat_history": [],
        "predictions": {},
        "pre_generated_charts": {},
        "current_file_name": None,
        "selected_model": OLLAMA_MODEL
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def activate_data_asset(file_id: int, user_id: int) -> bool:
    """Activates a past analytical asset by loading from disk and applying cache."""
    from datamind.security.authorizer import Authorizer
    Authorizer.assert_file_access(user_id, file_id)

    # 1. Fetch metadata
    files = db.get_user_files(user_id)
    file_meta = next((f for f in files if f['global_file_id'] == file_id), None)
    if not file_meta:
        return False
        
    # 2. Load from disk
    file_path = os.path.join(UPLOADS_DIR, file_meta['file_hash'])
    if not os.path.exists(file_path):
        st.error(f"Asset file not found in storage: {file_meta['file_hash']}")
        return False
        
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            
        df = UniversalFileLoader.load(file_bytes, file_meta['original_filename'])
        if df is None:
            return False
            
        # 3. Set Session State
        st.session_state["df"] = df
        st.session_state["current_file_id"] = file_id
        st.session_state["current_file_name"] = file_meta['original_filename']
        st.session_state["schema_fingerprint"] = json.loads(file_meta['schema_fingerprint'])
        st.session_state["predictions"] = {}
        
        # 3b. Load Chat History from DB
        st.session_state["chat_history"] = db.get_chat_history(user_id, file_id, limit=50)
        
        # 4. Load from Analytical Cache (Instant Recall)
        cache = db.get_analytical_cache(file_id)
        if cache and cache["summary_text"]:
            try:
                st.session_state["summary_text"] = json.loads(cache["summary_text"])
            except:
                st.session_state["summary_text"] = cache["summary_text"]
        else:
            st.session_state["summary_text"] = None
        
        db.update_last_accessed(user_id, file_id)
        return True
    except Exception as e:
        logging.error(f"Error activating asset: {e}")
        return False

def handle_file_upload(uploaded_file, user_id: int):
    """Processes file upload with SHA256 deduplication and DB mapping."""
    if not uploaded_file:
        return None

    if user_id:
        from datamind.security.rate_limiter import RateLimiter
        rate_result = RateLimiter.check_file_upload(user_id)
        if not rate_result["allowed"]:
            st.error(rate_result["message"])
            return None

    from datamind.security.sanitizer import InputSanitizer
    safe_name = InputSanitizer.sanitize_filename(uploaded_file.name)

    # 1. Read bytes for hashing
    file_bytes = uploaded_file.getvalue()
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    
    # 2. Universal Loading (Ingestion Guards)
    df = UniversalFileLoader.load(file_bytes, safe_name)
    if df is None:
        return None

    df, col_mapping = InputSanitizer.sanitize_column_names(df)
    st.session_state["col_mapping"] = col_mapping

    # 3. Generate Fingerprint & Mask PII
    fingerprint = UniversalFileLoader.generate_fingerprint(df)
    safe_fingerprint = UniversalFileLoader.mask_pii_samples(fingerprint)
    
    # 4. Global Registration (Deduplication)
    file_id = db.insert_global_file(
        file_hash=file_hash,
        filename=safe_name,
        fingerprint_json=json.dumps(safe_fingerprint),
        row_count=len(df),
        col_count=len(df.columns),
        domain=safe_fingerprint.get("detected_domain", "generic")
    )

    # 5. Map User to File
    if user_id is not None:
        db.create_user_file_ref(user_id, file_id, safe_name)
    
    # 5b. Persist to Disk if not present
    file_path = os.path.join(UPLOADS_DIR, file_hash)
    if not os.path.exists(file_path):
        with open(file_path, "wb") as f:
            f.write(file_bytes)
    
    # 6. Set Session Context
    st.session_state["df"] = df
    st.session_state["current_file_id"] = file_id
    st.session_state["current_file_name"] = safe_name
    st.session_state["schema_fingerprint"] = safe_fingerprint
    st.session_state["chat_history"] = []
    st.session_state["summary_text"] = None
    st.session_state["predictions"] = {}
    
    # Trigger Learning Loop (Statistical)
    try:
        from datamind.memory.learner import PatternLearner
        if user_id is not None:
            learner = PatternLearner()
            learner.extract_statistical_patterns(df, file_id, user_id)
    except Exception as e:
        logging.warning(f"Pattern learning failed: {e}")

    return df

# --- Accessors ---

def get_dataframe() -> Optional[pd.DataFrame]:
    return st.session_state.get("df")

def get_chat_history() -> List[Dict[str, Any]]:
    return st.session_state.get("chat_history", [])

def add_chat_message(
    role: str, 
    content: str, 
    figures: Optional[list] = None, 
    captions: Optional[list[str]] = None, 
    lab_narrative: Optional[str] = None, 
    category: str = "analysis",
    tier: int = 1,
    latency: int = 0,
    intent: str = "stat",
    is_artifact: int = 0,
    lab_target: str = None
) -> None:
    history = get_chat_history()
    message = {
        "role": role,
        "content": _clean_md_block(content) if role == "assistant" else content,
        "category": category,
        "figures": figures or [],
        "captions": captions or [],
        "lab_narrative": _clean_md_block(lab_narrative) if lab_narrative else None,
        "tier": tier,
        "latency": latency,
        "intent": intent,
        "is_artifact": is_artifact,
        "lab_target": lab_target
    }
    history.append(message)
    # Keep last 50 for session state
    if len(history) > 50:
        history = history[-50:]
    st.session_state["chat_history"] = history
    
    # Persist to DB if authenticated
    user = st.session_state.get("current_user")
    file_id = st.session_state.get("current_file_id")
    if user and file_id and not user.get("is_guest"):
        db.save_chat_message(
            user_id=user["id"],
            global_file_id=file_id,
            role=role,
            content=content,
            tier=tier,
            intent=intent,
            latency_ms=latency,
            is_lab_artifact=is_artifact,
            lab_target=lab_target
        )

def get_summary_text() -> Optional[str]:
    return st.session_state.get("summary_text")

def set_summary_text(summary: Any) -> None:
    st.session_state["summary_text"] = summary

def get_predictions() -> Dict[str, Any]:
    return st.session_state.get("predictions", {})

def set_predictions(preds: Dict[str, Any]) -> None:
    st.session_state["predictions"] = preds

def clear_predictions() -> None:
    st.session_state["predictions"] = {}

def get_pre_generated_charts() -> Dict[str, Figure]:
    return st.session_state.get("pre_generated_charts", {})

def set_pre_generated_chart(name: str, fig: Figure) -> None:
    charts = get_pre_generated_charts()
    charts[name] = fig
    st.session_state["pre_generated_charts"] = charts

def clear_pre_generated_charts() -> None:
    st.session_state["pre_generated_charts"] = {}