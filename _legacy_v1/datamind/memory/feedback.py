"""
Feedback Loop Subsystem for DataMind v4.0

Manages user ratings and learning over time:
- Store ratings (thumbs up/down) in local JSON per session
- Use stored feedback to: skip unpopular chart types, prefer successful models,
  adjust explanation verbosity
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]

from datamind.memory.session import get_dataframe
from config import OLLAMA_BASE_URL, OLLAMA_MODEL

# Path for feedback storage
FEEDBACK_DIR = os.path.join(os.path.dirname(__file__), "..", "feedback_data")
FEEDBACK_FILE = os.path.join(FEEDBACK_DIR, "user_ratings.json")


def ensure_feedback_dir() -> None:
    """Ensure feedback directory exists."""
    os.makedirs(FEEDBACK_DIR, exist_ok=True)


def load_all_ratings() -> List[Dict[str, Any]]:
    """Load all ratings from the feedback file."""
    ensure_feedback_dir()

    if not os.path.exists(FEEDBACK_FILE):
        return []

    try:
        with open(FEEDBACK_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_ratings(ratings: List[Dict[str, Any]]) -> None:
    """Save ratings to the feedback file."""
    ensure_feedback_dir()

    with open(FEEDBACK_FILE, "w") as f:
        json.dump(ratings, f, indent=2, default=str)


def add_rating(
    session_id: str,
    content_type: str,
    content_id: str,
    rating: int,  # 1 for thumbs up, 0 for thumbs down
    feedback_text: Optional[str] = None,
) -> None:
    """
    Add a rating to the feedback store.

    Args:
        session_id: Unique session identifier.
        content_type: Type of content ('chart', 'model', 'explanation').
        content_id: Specific content identifier.
        rating: 1 for positive, 0 for negative.
        feedback_text: Optional text feedback.
    """
    ensure_feedback_dir()

    all_ratings = load_all_ratings()

    rating_entry = {
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "content_type": content_type,
        "content_id": content_id,
        "rating": rating,
        "feedback_text": feedback_text or "",
        "feedback_vector": get_feedback_vector(rating, content_type),
    }

    all_ratings.append(rating_entry)

    # Keep only last 1000 ratings
    if len(all_ratings) > 1000:
        all_ratings = all_ratings[-1000:]

    save_ratings(all_ratings)

    # Also update session state
    session_ratings = st.session_state.get("feedback_log", [])
    session_ratings.append(rating_entry)
    st.session_state["feedback_log"] = session_ratings


def get_feedback_vector(rating: int, content_type: str) -> Dict[str, float]:
    """
    Convert a rating to a feedback vector for learning.

    Args:
        rating: 1 for positive, 0 for negative.
        content_type: Type of content.

    Returns:
        Dictionary with feedback weights.
    """
    # Initialize vector based on content type
    vector = {}

    if content_type == "chart":
        vector["chart_preference"] = 1.0 if rating else -1.0
    elif content_type == "model":
        vector["model_preference"] = 1.0 if rating else -1.0
    elif content_type == "explanation":
        vector["verbosity_preference"] = 1.0 if rating else -0.5

    return vector


def get_user_preferences() -> Dict[str, Any]:
    """
    Analyze feedback history to extract user preferences.

    Returns:
        Dictionary with user's preference weights.
    """
    all_ratings = load_all_ratings()

    if not all_ratings:
        return {}

    preferences = {
        "preferred_chart_types": [],
        "rejected_chart_types": [],
        "preferred_models": [],
        "rejected_models": [],
        "verbosity_pref": "balanced",  # Default
    }

    # Analyze ratings by type
    for rating in all_ratings:
        content_type = rating["content_type"]
        content_id = rating["content_id"]
        is_positive = rating["rating"] == 1

        if content_type == "chart":
            if is_positive:
                preferences["preferred_chart_types"].append(content_id)
            else:
                preferences["rejected_chart_types"].append(content_id)

        elif content_type == "model":
            if is_positive:
                preferences["preferred_models"].append(content_id)
            else:
                preferences["rejected_models"].append(content_id)

    # Check verbosity preference based on explanation ratings
    explanation_ratings = [
        r for r in all_ratings if r["content_type"] == "explanation"
    ]
    if explanation_ratings:
        avg_rating = sum(r["rating"] for r in explanation_ratings) / len(explanation_ratings)
        if avg_rating > 0.7:
            preferences["verbosity_pref"] = "detailed"
        elif avg_rating < 0.3:
            preferences["verbosity_pref"] = "concise"

    # Remove duplicates while preserving order
    for key in ["preferred_chart_types", "rejected_chart_types", "preferred_models", "rejected_models"]:
        seen = set()
        unique = []
        for item in preferences[key]:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        preferences[key] = unique

    return preferences


def get_chart_recommendations(content_id: str) -> List[str]:
    """
    Get chart recommendations based on user preferences.

    Args:
        content_id: The content type being requested.

    Returns:
        List of recommended chart types to try.
    """
    preferences = get_user_preferences()
    rejected = preferences.get("rejected_chart_types", [])

    # Default chart types
    default_types = ["distribution", "correlation", "time_series", "scatter_matrix"]

    # Filter out rejected types
    recommendations = [c for c in default_types if c not in rejected]

    # If all rejected, return all (user may have changed mind)
    if not recommendations:
        recommendations = default_types

    return recommendations


def get_model_recommendations(task_type: str) -> List[str]:
    """
    Get model recommendations based on user preferences.

    Args:
        task_type: Type of ML task.

    Returns:
        List of model names in recommended order.
    """
    preferences = get_user_preferences()
    rejected = preferences.get("rejected_models", [])

    # Default model preferences based on task type
    model_order = {
        "classification": ["RandomForest", "LogisticRegression", "XGBoost"],
        "regression": ["RandomForest", "Ridge", "LinearRegression"],
        "forecasting": ["Prophet", "ARIMA"],
    }

    default_order = model_order.get(task_type, ["RandomForest", "LogisticRegression"])

    # Filter out rejected models
    recommendations = [m for m in default_order if m not in rejected]

    # If all rejected, return all
    if not recommendations:
        recommendations = default_order

    return recommendations


def get_verbosity_preference() -> str:
    """
    Get user's preferred explanation verbosity.

    Returns:
        One of 'concise', 'balanced', or 'detailed'.
    """
    preferences = get_user_preferences()
    return preferences.get("verbosity_pref", "balanced")


def render_rating_widget(
    session_id: str, content_type: str, content_id: str, key: str = ""
) -> None:
    """
    Render a rating widget (thumbs up/down) with optional feedback text.

    Args:
        session_id: Unique session identifier.
        content_type: Type of content being rated.
        content_id: Specific content identifier.
        key: Streamlit key for the widget.
    """
    st.markdown(
        """
        <div style="margin-top: 1rem; padding: 1rem; background: rgba(255, 255, 255, 0.03); border-radius: 8px;">
            <span style="font-size: 0.85rem; color: #9CA3AF;">Was this helpful?</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 3])

    with col1:
        thumbs_up = st.button("👍", key=f"thumb_up_{key}")
        thumbs_down = st.button("👎", key=f"thumb_down_{key}")

    if thumbs_up:
        add_rating(session_id, content_type, content_id, 1)
        st.session_state[f"rated_{key}"] = True
        st.rerun()

    if thumbs_down:
        feedback = st.text_area(
            "What could be better?",
            key=f"feedback_{key}",
            placeholder="Tell us what we can improve...",
            height=60,
        )

        if st.button("Submit", key=f"submit_feedback_{key}"):
            add_rating(session_id, content_type, content_id, 0, feedback)
            st.session_state[f"rated_{key}"] = True
            st.rerun()


def render_session_summary() -> None:
    """Render a summary of user ratings in the sidebar."""
    all_ratings = load_all_ratings()

    if not all_ratings:
        return

    # Count ratings by type
    chart_ratings = [r for r in all_ratings if r["content_type"] == "chart"]
    model_ratings = [r for r in all_ratings if r["content_type"] == "model"]
    explanation_ratings = [r for r in all_ratings if r["content_type"] == "explanation"]

    st.markdown(
        """
        <div style="margin-top: 2rem;">
            <h5 style="color: #9CA3AF; font-size: 0.85rem; margin-bottom: 0.5rem;">
                📊 Your Learning Summary
            </h5>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Charts Rated", len(chart_ratings))
    with col2:
        st.metric("Models Rated", len(model_ratings))
    with col3:
        st.metric("Explanations Rated", len(explanation_ratings))

    # Recent activity
    if all_ratings:
        st.markdown(
            """
            <h5 style="color: #9CA3AF; font-size: 0.85rem; margin: 1rem 0 0.5rem 0;">
                Recent Activity
            </h5>
            """,
            unsafe_allow_html=True,
        )

        for rating in all_ratings[-3:]:
            icon = "👍" if rating["rating"] == 1 else "👎"
            st.markdown(
                f"""
                <div style="background: rgba(255, 255, 255, 0.03); border-radius: 4px; padding: 0.25rem 0.5rem; margin-bottom: 0.25rem;">
                    <span style="font-size: 0.75rem;">
                        {icon} {rating['content_type'].title()}: {rating['content_id']}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )


def clear_feedback_data() -> None:
    """Clear all feedback data (for testing/reset)."""
    if os.path.exists(FEEDBACK_FILE):
        os.remove(FEEDBACK_FILE)
    st.session_state["feedback_log"] = []