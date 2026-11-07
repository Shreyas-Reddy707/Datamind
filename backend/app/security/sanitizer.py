"""DataMind v2 Input Sanitizer Module.

Provides ReDoS-resistant sanitization for filenames, column names,
authentication inputs, and prompt cell values.
"""

from __future__ import annotations

import os
import re
from typing import Any

import pandas as pd


class InputSanitizer:
    """Security-focused input sanitizer resisting ReDoS and injection attacks."""

    # ── Filename Sanitization ──
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Strip directory traversal components, null bytes, and dangerous characters."""
        if not filename:
            return "upload_unnamed"
        # Prevent path traversal
        filename = os.path.basename(filename)
        # Remove null bytes
        filename = filename.replace("\x00", "")
        # Allow only alphanumeric, dashes, underscores, and dots
        filename = re.sub(r"[^\w\-.]", "_", filename)
        # Prevent hidden files
        filename = filename.lstrip(".")
        # Enforce max length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[: 255 - len(ext)] + ext
        if not filename or filename == "_":
            return "upload_unnamed"
        return filename

    # ── Column Name Sanitization ──
    @staticmethod
    def sanitize_column_names(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
        """Sanitize DataFrame columns against SQL injection and formatting hazards."""
        mapping: dict[str, str] = {}
        new_columns: list[str] = []

        for idx, col in enumerate(df.columns):
            col_str = str(col).strip()
            # Remove SQL-dangerous characters
            sanitized = re.sub(r"['\";\\/*%$]", "", col_str)
            # Remove comment sequences
            sanitized = re.sub(r"--", "", sanitized)
            sanitized = re.sub(r"/\*", "", sanitized)
            sanitized = re.sub(r"\*/", "", sanitized)
            # Remove control characters and trim
            sanitized = re.sub(r"[\x00-\x1f\x7f]", "", sanitized).strip()[:100]
            if not sanitized:
                sanitized = f"col_{idx}"
            # Ensure unique column names
            base_sanitized = sanitized
            counter = 1
            while sanitized in new_columns:
                sanitized = f"{base_sanitized}_{counter}"
                counter += 1

            mapping[col_str] = sanitized
            new_columns.append(sanitized)

        df = df.copy()
        df.columns = pd.Index(new_columns)
        return df, mapping

    # ── Cell Value Sanitization for LLM Prompts ──
    @staticmethod
    def sanitize_for_llm(text: Any, max_length: int = 500) -> str:
        """Neutralize prompt injection attempts and truncate to prevent token exhaustion."""
        if text is None:
            return ""
        if not isinstance(text, str):
            text = str(text)

        injection_patterns = [
            r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
            r"forget\s+(everything|all)",
            r"you\s+are\s+(now\s+)?(a|an)",
            r"new\s+instructions?:",
            r"system\s*prompt",
            r"disregard\s+(your\s+)?",
            r"act\s+as\s+(if\s+)?",
            r"pretend\s+(you\s+are|to\s+be)",
            r"jailbreak",
            r"dan\s+mode",
            r"developer\s+mode",
            r"do\s+anything\s+now",
        ]
        for pattern in injection_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return "[CONTENT_FILTERED]"

        if len(text) > max_length:
            return text[:max_length] + "...[truncated]"
        return text

    # ── Auth Input Sanitization ──
    @staticmethod
    def sanitize_auth_input(value: str, field_type: str) -> str:
        """Sanitize auth fields and bound maximum lengths to prevent bcrypt/regex DoS."""
        if not isinstance(value, str):
            return ""
        value = value.strip().replace("\x00", "")

        if field_type == "email":
            return value.lower()[:254]
        if field_type == "username":
            return value[:20]
        if field_type == "password":
            return value[:128]
        return value[:1000]

    # ── Safe Email Regex (ReDoS-resistant) ──
    @staticmethod
    def validate_email_safe(email: str) -> bool:
        """Linear-time validation resisting catastrophic regex backtracking."""
        if not email or len(email) > 254:
            return False
        parts = email.split("@")
        if len(parts) != 2:
            return False
        local, domain = parts
        if not local or not domain or len(local) > 64:
            return False
        if "." not in domain or domain.startswith(".") or domain.endswith("."):
            return False
        allowed = re.compile(r"^[\w.+-]+$")
        return bool(allowed.match(local)) and bool(allowed.match(domain))
