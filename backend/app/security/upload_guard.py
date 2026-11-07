"""DataMind v2 Upload Guard Module.

Implements pre- and post-read validation for uploaded datasets, detecting magic
bytes mismatches, active script injection, zip/CSV bombs, and SSRF ranges.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
from typing import Any
from urllib.parse import urlparse

import pandas as pd

logger = logging.getLogger("datamind.security.upload_guard")


class UploadGuard:
    """Rigorous file validation against bombs, binary injection, and SSRF attacks."""

    ALLOWED_EXTENSIONS: set[str] = {".csv", ".xlsx", ".xls", ".json", ".parquet"}
    MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50MB
    MAX_ROWS_SAFE: int = 500_000
    MAX_COLS_SAFE: int = 500
    MAX_EXCEL_ROWS: int = 100_000
    MAX_EXCEL_COLS: int = 200
    MAX_MEMORY_MB: int = 500

    BLOCKED_MAGIC_SIGNATURES: dict[str, bytes] = {
        "exe_or_dll": b"MZ",
        "elf_binary": b"\x7fELF",
        "pdf": b"%PDF",
        "zip_without_excel": b"PK\x05\x06",
    }

    @staticmethod
    def validate_before_read(file_bytes: bytes, filename: str) -> dict[str, Any]:
        """Inspect file raw bytes before parsing into memory."""
        ext = os.path.splitext(filename)[1].lower()

        # 1. Extension check
        if ext not in UploadGuard.ALLOWED_EXTENSIONS:
            return {
                "safe": False,
                "error": f"File type '{ext}' is not permitted. Supported: {', '.join(sorted(UploadGuard.ALLOWED_EXTENSIONS))}",
            }

        # 2. File size check
        file_len = len(file_bytes)
        if file_len == 0:
            return {"safe": False, "error": "Uploaded file is empty."}

        if file_len > UploadGuard.MAX_FILE_SIZE_BYTES:
            mb = file_len / (1024 * 1024)
            limit_mb = UploadGuard.MAX_FILE_SIZE_BYTES // (1024 * 1024)
            return {
                "safe": False,
                "error": f"File size ({mb:.1f}MB) exceeds the maximum allowed limit of {limit_mb}MB.",
            }

        # 3. Executable / binary detection
        if file_bytes.startswith(b"MZ") or file_bytes.startswith(b"\x7fELF"):
            return {"safe": False, "error": "Executable binary payload detected. Upload rejected."}

        # 4. Active content / script blocking in textual datasets
        sample_head = file_bytes[:4096].lower()
        if any(tag in sample_head for tag in [b"<svg", b"<script", b"<html", b"<!doctype"]):
            return {
                "safe": False,
                "error": "HTML/SVG or script content detected in dataset. Upload rejected for security reasons.",
            }

        # 5. Magic bytes checks for structured binaries
        magic_checks = {
            ".xlsx": b"PK\x03\x04",
            ".xls": b"\xd0\xcf\x11\xe0",
            ".parquet": b"PAR1",
        }
        if ext in magic_checks:
            expected_magic = magic_checks[ext]
            if not file_bytes.startswith(expected_magic):
                return {
                    "safe": False,
                    "error": f"File header does not match expected signature for {ext}. Upload rejected.",
                }

        # 6. Null byte check in CSV (binary injection attempt)
        if ext == ".csv" and b"\x00" in file_bytes[:1024]:
            return {
                "safe": False,
                "error": "Null bytes detected in CSV file. Invalid or malicious content.",
            }

        return {"safe": True, "error": None}

    @staticmethod
    def validate_after_read(df: pd.DataFrame, filename: str) -> dict[str, Any]:
        """Validate DataFrame dimensions and memory profile after parsing."""
        ext = os.path.splitext(filename)[1].lower()

        # 1. Row count cap
        if len(df) > UploadGuard.MAX_ROWS_SAFE:
            return {
                "safe": False,
                "error": f"Dataset contains {len(df):,} rows (maximum allowed: {UploadGuard.MAX_ROWS_SAFE:,}).",
            }

        # 2. Column count cap (wide table bomb)
        if len(df.columns) > UploadGuard.MAX_COLS_SAFE:
            return {
                "safe": False,
                "error": f"Dataset has {len(df.columns)} columns (maximum allowed: {UploadGuard.MAX_COLS_SAFE}).",
            }

        # 3. Excel row cap
        if ext in (".xlsx", ".xls"):
            if len(df) > UploadGuard.MAX_EXCEL_ROWS:
                return {
                    "safe": False,
                    "error": f"Excel dataset exceeds the safety threshold of {UploadGuard.MAX_EXCEL_ROWS:,} rows.",
                }

        # 4. Memory footprint estimate
        try:
            mem_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
            if mem_mb > UploadGuard.MAX_MEMORY_MB:
                return {
                    "safe": False,
                    "error": f"In-memory footprint ({mem_mb:.1f}MB) exceeds the {UploadGuard.MAX_MEMORY_MB}MB safety boundary.",
                }
        except Exception as exc:
            logger.debug("Failed to calculate in-memory footprint: %s", exc)

        return {"safe": True, "error": None}

    @staticmethod
    def validate_remote_url(url: str) -> dict[str, Any]:
        """Validate URL to protect against SSRF, internal network scanning, and loopback exploits."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return {"safe": False, "error": "Only HTTP and HTTPS URLs are permitted."}

            hostname = parsed.hostname
            if not hostname:
                return {"safe": False, "error": "Invalid URL hostname."}

            # Resolve IP
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                ip_str = item[4][0]
                ip = ipaddress.ip_address(ip_str)
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_reserved
                    or ip.is_link_local
                    or ip.is_multicast
                    or ip_str in ("169.254.169.254", "0.0.0.0")  # noqa: S104
                ):
                    return {
                        "safe": False,
                        "error": "Access to private, link-local, or cloud metadata network addresses is strictly prohibited.",
                    }

            return {"safe": True, "error": None}
        except Exception as e:
            return {"safe": False, "error": f"Failed to validate remote URL: {str(e)}"}
