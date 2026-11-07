"""Memory package for DataMind v4.0"""

from datamind.memory.session import (
    get_dataframe,
    get_summary_text,
    set_summary_text,
    get_chat_history,
    add_chat_message,
    set_pre_generated_chart,
    get_pre_generated_charts,
    initialize_session_state,
    clear_pre_generated_charts,
    handle_file_upload,
    activate_data_asset
)

from datamind.memory.feedback import (
    add_rating,
    render_rating_widget,
    render_session_summary,
    clear_feedback_data,
    get_user_preferences,
    get_chart_recommendations,
)

__all__ = [
    # Session state accessors
    "get_dataframe",
    "get_summary_text",
    "set_summary_text",
    "get_chat_history",
    "add_chat_message",
    "set_pre_generated_chart",
    "get_pre_generated_charts",
    "initialize_session_state",
    "clear_pre_generated_charts",
    "handle_file_upload",
    "activate_data_asset",
    # Feedback
    "add_rating",
    "render_rating_widget",
    "render_session_summary",
    "clear_feedback_data",
    "get_user_preferences",
    "get_chart_recommendations",
]