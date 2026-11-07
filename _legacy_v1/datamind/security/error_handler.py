import logging, traceback, uuid
from datetime import datetime
import os

# Ensure data dir exists for logging
os.makedirs('data', exist_ok=True)

# Configure logging to file (not stdout — stdout leaks to browser)
logging.basicConfig(
    filename='data/datamind_errors.log',
    level=logging.ERROR,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

class SafeErrorHandler:

    ERROR_MESSAGES = {
        'database': "A data error occurred. Please try again.",
        'auth': "Authentication failed. Please check your credentials.",
        'file': "File processing failed. Check the file format and try again.",
        'agent': "Analysis encountered an issue. Please rephrase your question.",
        'permission': "You don't have permission to access this resource.",
        'upload': "File upload failed. Please try a different file.",
        'generic': "Something went wrong. Please try again.",
    }

    @classmethod
    def handle(cls, exception: Exception, context: str = 'generic',
               user_id: int = None, show_in_ui: bool = True) -> str:
        error_id = str(uuid.uuid4())[:8].upper()

        logging.error(
            f"[{error_id}] Context={context} | User={user_id} | "
            f"Type={type(exception).__name__} | "
            f"Detail={str(exception)}\n"
            f"{traceback.format_exc()}"
        )

        exc_type = type(exception).__name__.lower()
        if 'sql' in exc_type or 'database' in exc_type or 'operational' in exc_type:
            category = 'database'
        elif 'permission' in exc_type or 'security' in exc_type:
            category = 'permission'
        elif 'file' in exc_type or 'io' in exc_type:
            category = 'file'
        elif 'auth' in context.lower():
            category = 'auth'
        else:
            category = 'generic'

        user_message = (f"{cls.ERROR_MESSAGES.get(category, cls.ERROR_MESSAGES['generic'])}"
                       f" (Ref: {error_id})")

        if show_in_ui:
            import streamlit as st
            st.error(f"⚠️ {user_message}")

        return user_message
