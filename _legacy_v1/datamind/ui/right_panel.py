"""
Right Panel for DataMind SaaS.
Handles Conversational Interaction with Multi-Tiered Intelligence.
"""

from __future__ import annotations
import time
import json
import uuid
import requests
import streamlit as st
from datetime import datetime
from typing import Optional, Dict, Any, List

from datamind.agent.orchestrator import Orchestrator
from datamind.agent import chat_classifier, instant_responder
from datamind.memory import context_builder
from datamind.memory.session import get_chat_history, add_chat_message, get_dataframe
from datamind.llm.ollama_client import OllamaClient
from config import OLLAMA_BASE_URL, OLLAMA_MODEL

def render_right_panel():
    """Main rendering loop for right panel with tiered intelligence routing."""
    user = st.session_state.get("current_user")
    df = get_dataframe()
    fingerprint = st.session_state.get("schema_fingerprint")
    
    # 1. File Disambiguation & Availability Check
    if df is None:
        st.info("Upload a file to start asking questions →")
        return
        
    # 1. Multi-file Switcher Logic removed as per user request (Asking about... bar)

    
    chat_history = get_chat_history()
    
    # --- 2. Chat History Display ---
    from datamind.ui.layout import render_chat_interface
    # render_chat_interface now handles the rendering part
    render_chat_interface(chat_history)
    
    # --- 3. Custom Input Bar with Premium Styling ---

    col_input, col_send = st.columns([6, 1], gap="small")
    
    # Callback to handle clearing and Enter key
    def on_chat_submit():
        raw_query = st.session_state.get("chat_input_box", "").strip()
        if raw_query:
            st.session_state["pending_input_query"] = raw_query
            st.session_state["chat_input_box"] = "" # Instant clear

    query = col_input.text_input(
        label="Query Input", placeholder="Ask anything about your data...",
        key="chat_input_box", label_visibility="collapsed",
        on_change=on_chat_submit
    )
    
    is_in_flight = st.session_state.get("chat_in_flight", False)
    # The arrow button
    send_clicked = col_send.button("→", key="send_btn", disabled=is_in_flight)

    # Process if either button clicked or Enter pressed
    pending_query = st.session_state.get("pending_input_query")
    if (send_clicked and query) or pending_query:
        # Determine the final query to use
        final_query = pending_query if pending_query else query
        # Clean up state
        st.session_state.pop("pending_input_query", None)
        
        last_query = st.session_state.get("last_query", "")
        if final_query.strip().lower() == last_query.strip().lower():
            st.warning("⚠️ Same question — see answer above")
        else:
            st.session_state["chat_in_flight"] = True
            st.session_state["last_query"] = final_query
            
            # Step 1: Add user message to state
            add_chat_message("user", final_query)
            
            # Step 2: Handle response pipeline
            from datamind.security.authorizer import SecurityError
            from datamind.security.error_handler import SafeErrorHandler
            
            try:
                # Add Authorizer test early to fail fast before doing analysis
                user_id = user["id"] if user else 0
                handle_chat_query(final_query, user_id, st.session_state["current_file_id"], df, fingerprint)
            except SecurityError as e:
                SafeErrorHandler.handle(e, context="permission", user_id=user["id"] if user else None)
                st.session_state.pop("pending_agent_call", None)
            except Exception as e:
                SafeErrorHandler.handle(e, context="agent", user_id=user["id"] if user else None)
                st.session_state.pop("pending_agent_call", None)
            
            st.session_state["chat_in_flight"] = False
            st.rerun()

    # --- 4. Custom Styling (Moved to end to prevent jump) ---
    st.markdown("""
        <style>
        button[key="send_btn"] {
            background: #8B5CF6 !important;
            border: none !important;
            border-radius: 8px !important;
            height: 38px !important;
            width: 38px !important;
            min-width: 38px !important;
            padding: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            transition: all 0.3s ease !important;
        }
        button[key="send_btn"]:hover { background: #7C3AED !important; transform: scale(1.05); box-shadow: 0 0 15px rgba(139, 92, 246, 0.4); }
        button[key="send_btn"]:active { transform: scale(0.95); }
        div[data-testid="stColumn"] > div { padding: 0 !important; display: flex !important; align-items: center !important; justify-content: center !important; }
        </style>
    """, unsafe_allow_html=True)

    # --- 4. Pending Tier 3 Agent Processing ---
    if st.session_state.get("pending_agent_call"):
        agent_data = st.session_state.pop("pending_agent_call")
        _process_tier3_agent(agent_data)
        st.rerun()

def handle_chat_query(query: str, user_id: Any, file_id: int, df: Any, fingerprint: Dict):
    """Tiered Response Pipeline."""
    from datamind.security.rate_limiter import RateLimiter
    from datamind.security.authorizer import Authorizer

    user = st.session_state.get("current_user")
    is_guest = user and user.get("is_guest")

    if is_guest:
        user_id = user.get("guest_key", "guest")
    else:
        Authorizer.assert_file_access(user_id, file_id)
    
    rate_result = RateLimiter.check_chat(user_id)
    if not rate_result["allowed"]:
        st.warning(rate_result["message"])
        return

    start_time = time.time()
    cache = st.session_state.get("query_cache")
    
    # 1. Check Cache
    if cache:
        cached = cache.get(user_id, file_id, query)
        if cached:
            add_chat_message("assistant", cached + " _(cached ⚡)_", tier=1, latency=0)
            return

    # 2. Classify Tier
    cls = chat_classifier.classify_tier(query, list(df.columns))
    tier = cls["tier"]
    intent = cls["intent"]
    
    # 3. Disambiguation Check
    if not cls["target_columns"] and tier > 1:
        ambiguous = chat_classifier.find_possible_target_columns(query, fingerprint)
        if len(ambiguous) > 1:
            opts = ", ".join([f"**{c}**" for c in ambiguous[:5]])
            add_chat_message("assistant", f"Which column are you asking about? {opts}", tier=1)
            return

    # 4. Route by Tier
    if tier == 1:
        response = instant_responder.handle_tier1(query, df, fingerprint)
        latency = int((time.time() - start_time) * 1000)
        if cache: cache.set(user_id, file_id, query, response, tier=1)
        add_chat_message("assistant", response, tier=1, latency=latency, intent=intent)

    elif tier == 2:
        with st.chat_message("assistant"):
            placeholder = st.empty()
            # Fetch current analytical briefing for grounding
            current_summary = st.session_state.get("summary_text", "")
            dossier_text = ""
            if isinstance(current_summary, dict):
                dossier_text = current_summary.get("text", "")
            elif isinstance(current_summary, str):
                dossier_text = current_summary

            context = context_builder.build_context(
                tier=2, query=query, fingerprint=fingerprint,
                conversation_history=get_chat_history(),
                prior_patterns=[], target_columns=cls["target_columns"],
                summary_text=dossier_text
            )
            # Use streaming for Tier 2
            response = stream_ollama_response(context, query, placeholder)
            latency = int((time.time() - start_time) * 1000)
            if cache: cache.set(user_id, file_id, query, response, tier=2)
            # Add to history after streaming finishes
            add_chat_message("assistant", response, tier=2, latency=latency, intent=intent)

    elif tier == 3:
        lab = cls.get("lab_target", "analysis")
        status_msg = "🔬 Sending to Analysis Lab..." if lab == "analysis" else "🤖 Running prediction pipeline..."
        add_chat_message("assistant", status_msg, tier=3, latency=0, intent=intent)
        
        # Store for full agent processing on next rerun to avoid UI block
        st.session_state["pending_agent_call"] = {
            "query": query,
            "lab": lab,
            "classification": cls,
            "start_time": start_time
        }

def stream_ollama_response(system_prompt: str, user_prompt: str, placeholder: Any) -> str:
    """Streams response from Ollama via requests."""
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "system": system_prompt,
                "prompt": user_prompt,
                "stream": True,
                "options": {"num_predict": 250, "temperature": 0.3}
            },
            stream=True,
            timeout=30
        )
        
        full_text = ""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                if not chunk.get("done"):
                    token = chunk.get("response", "")
                    full_text += token
                    placeholder.markdown(full_text + "▌")
        
        placeholder.markdown(full_text)
        return full_text
    except Exception as e:
        placeholder.error(f"⚠️ Connection lost: {str(e)}")
        return "⚠️ I encountered a connection issue with the local AI node."

def _process_tier3_agent(agent_data: Dict):
    """Executes the full agent pipeline (Existing Orchestrator)."""
    start_time = agent_data["start_time"]
    query = agent_data["query"]
    lab = agent_data["lab"]
    cls = agent_data["classification"]
    
    user_id = st.session_state.get("current_user", {}).get("id")
    file_id = st.session_state.get("current_file_id")

    from datamind.security.authorizer import Authorizer, SecurityError
    from datamind.security.error_handler import SafeErrorHandler

    with st.spinner("Executing Deep Analysis..."):
        try:
            user = st.session_state.get("current_user")
            if not (user and user.get("is_guest")):
                Authorizer.assert_file_access(user_id, file_id)
            orch = Orchestrator()
            res = orch.route_query(
                query=query,
                fingerprint=st.session_state.get("schema_fingerprint"),
                file_id=file_id,
                intent_override=cls.get("intent")
            )
            
            latency = int((time.time() - start_time) * 1000)
        except SecurityError as e:
            SafeErrorHandler.handle(e, context="permission", user_id=user_id)
            return
        except Exception as e:
            SafeErrorHandler.handle(e, context="agent", user_id=user_id)
            return
        
        if res.get("success"):
            add_chat_message(
                "assistant",
                res.get("response", "Strategic analysis complete."),
                tier=3,
                latency=latency,
                intent=cls["intent"],
                figures=res.get("figures", []),
                lab_narrative=res.get("lab_narrative"),
                is_artifact=1,
                lab_target=lab,
                category=lab
            )
        else:
            add_chat_message("assistant", f"⚠️ Analysis interrupted: {res.get('error')}", tier=3, latency=latency)