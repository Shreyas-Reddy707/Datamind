"""
DataMind v4.0 Configuration

Centralized configuration for model names, timeouts, thresholds, and system behavior.
"""

import os
from typing import Final
from dotenv import load_dotenv
import streamlit as st

# Load environment variables from .env if it exists
load_dotenv()

def _get_secret(env_key: str, st_key: str, default: str = "") -> str:
    """Try environment first, then Streamlit secrets, then default."""
    env_val = os.getenv(env_key)
    if env_val:
        return env_val
    try:
        return st.secrets.get(st_key, default)
    except Exception:
        return default

# ── Environment variables (from .env or secrets) ──
OLLAMA_BASE_URL: Final[str] = _get_secret("OLLAMA_BASE_URL", "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL: Final[str] = _get_secret("OLLAMA_MODEL", "OLLAMA_MODEL", "qwen2.5-coder:latest")
SESSION_SECRET: Final[str] = _get_secret("SESSION_SECRET", "SESSION_SECRET", "insecure-default-change-in-production")
DEBUG: Final[bool] = _get_secret("DEBUG", "DEBUG", "false").lower() == "true"

# ── Paths (computed, never hardcoded) ──
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "datamind.db")
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# ── App constants ──
MAX_FILE_SIZE_MB: Final[int] = 50
MAX_ROWS: Final[int] = 500_000
BCRYPT_ROUNDS: Final[int] = 10
SESSION_DURATION_HOURS: Final[int] = 24
MAX_FAILED_ATTEMPTS: Final[int] = 5
LOCKOUT_MINUTES: Final[int] = 15
MAX_HISTORY_MESSAGES: Final[int] = 500
MAX_SESSIONS_TO_CACHE: Final[int] = 5
SUPPORTED_EXTENSIONS: Final[list[str]] = [".csv", ".xlsx", ".xls", ".json", ".parquet"]
LOG_LEVEL: Final[str] = "INFO" if not DEBUG else "DEBUG"

# ── Timeout Settings ──────────────────────────────────────────────
OLLAMA_TIMEOUT: Final[int] = int(os.getenv("OLLAMA_TIMEOUT", "300"))
SUMMARY_TIMEOUT: Final[int] = int(os.getenv("SUMMARY_TIMEOUT", "300"))
DIAGNOSTIC_TIMEOUT: Final[int] = int(os.getenv("DIAGNOSTIC_TIMEOUT", "300"))
VIZ_TIMEOUT: Final[int] = int(os.getenv("VIZ_TIMEOUT", "60"))
PREDICT_TIMEOUT: Final[int] = int(os.getenv("PREDICT_TIMEOUT", "300"))
CHAT_TIMEOUT: Final[int] = int(os.getenv("CHAT_TIMEOUT", "300"))
OLLAMA_MAX_RETRIES: Final[int] = 3

# ── Threshold Settings ────────────────────────────────────────────
NULL_RATE_THRESHOLD: Final[float] = float(os.getenv("NULL_RATE_THRESHOLD", "0.3"))
MIN_NUMERIC_FOR_CLUSTERING: Final[int] = int(os.getenv("MIN_NUMERIC_FOR_CLUSTERING", "2"))
MIN_NULL_RATE_FOR_ID: Final[float] = float(os.getenv("MIN_NULL_RATE_FOR_ID", "0.9"))
CORRELATION_MIN_NUMERIC: Final[int] = int(os.getenv("CORRELATION_MIN_NUMERIC", "3"))

# ── ML Settings ───────────────────────────────────────────────────
TRAIN_TEST_SPLIT_RATIO: Final[float] = float(os.getenv("TRAIN_TEST_SPLIT_RATIO", "0.8"))
CROSS_VALIDATION_FOLDS: Final[int] = int(os.getenv("CROSS_VALIDATION_FOLDS", "5"))
FORECAST_HORIZON_DAYS: Final[int] = int(os.getenv("FORECAST_HORIZON_DAYS", "30"))
FORECAST_CONFIDENCE_LEVEL: Final[float] = float(os.getenv("FORECAST_CONFIDENCE_LEVEL", "0.95"))