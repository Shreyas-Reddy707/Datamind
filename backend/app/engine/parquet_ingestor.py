"""DataMind v2 Content-Addressed Parquet Ingestor.

Deduplicates datasets by SHA256 digest, validates with UploadGuard, extracts
schematic metadata, detects domain heuristics, and converts to Parquet.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import logging
import os
from typing import Any

import chardet
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.file import GlobalFile, UserFile
from app.security.sanitizer import InputSanitizer
from app.security.upload_guard import UploadGuard

logger = logging.getLogger("datamind.engine.ingestor")

PII_KEYWORDS = [
    "email",
    "phone",
    "ssn",
    "dob",
    "salary",
    "address",
    "national_id",
    "passport",
    "credit_card",
    "account_number",
    "mobile",
]


class ParquetIngestor:
    """Streams and converts multi-format datasets into content-addressed Parquet files."""

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """Compute SHA256 hex digest for deduplication."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def detect_domain(column_names: list[str]) -> str:
        """Autonomous domain discovery based on column names and semantic keywords."""
        full_text = " ".join(column_names).lower()
        if any(
            x in full_text
            for x in ["price", "revenue", "sale", "cost", "invoice", "profit", "margin", "tax"]
        ):
            return "finance"
        if any(
            x in full_text
            for x in ["patient", "diagnosis", "doctor", "health", "symptom", "blood", "medical"]
        ):
            return "health"
        if any(
            x in full_text
            for x in ["customer", "order", "sku", "cart", "product", "inventory", "checkout"]
        ):
            return "ecommerce"
        if any(
            x in full_text
            for x in ["employee", "salary", "hiring", "leave", "department", "tenure"]
        ):
            return "hr"
        if any(
            x in full_text
            for x in ["shipment", "warehouse", "tracking", "carrier", "freight", "logistics"]
        ):
            return "logistics"
        if any(
            x in full_text
            for x in ["student", "grade", "course", "gpa", "exam", "enrollment", "score"]
        ):
            return "education"
        return "generic"

    @staticmethod
    def load_dataframe_from_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
        """Load DataFrame from in-memory bytes with auto-encoding and delimiter detection."""
        ext = os.path.splitext(filename)[1].lower()

        if ext == ".csv":
            # Cap sniff to first 64KB to avoid CPU stalls on 16MB+ datasets
            raw_sample = file_bytes[:65536]
            enc_result = chardet.detect(raw_sample)
            encoding = enc_result.get("encoding") or "utf-8"
            if encoding.lower() in ("ascii", "none"):
                encoding = "utf-8"
            try:
                snippet = raw_sample[:4096].decode(encoding, errors="ignore")
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(snippet)
                delimiter = dialect.delimiter
            except Exception:
                delimiter = ","
            try:
                df = pd.read_csv(
                    io.BytesIO(file_bytes),
                    encoding=encoding,
                    sep=delimiter,
                    low_memory=False,
                    on_bad_lines="skip",
                )
            except Exception:
                df = pd.read_csv(
                    io.BytesIO(file_bytes),
                    encoding="latin-1",
                    sep=delimiter,
                    low_memory=False,
                    on_bad_lines="skip",
                )

        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(io.BytesIO(file_bytes))

        elif ext == ".json":
            df = pd.read_json(io.BytesIO(file_bytes))

        elif ext == ".parquet":
            df = pd.read_parquet(io.BytesIO(file_bytes))

        else:
            raise ValueError(f"Unsupported file format: {ext}")

        return df

    @classmethod
    def extract_schema_metadata(cls, df: pd.DataFrame) -> dict[str, Any]:
        """Generate schema metadata, type tagging, and PII masking."""
        cols_meta: dict[str, Any] = {}
        pii_columns: list[str] = []

        for col in df.columns:
            dtype_label = "text"
            if pd.api.types.is_numeric_dtype(df[col]):
                dtype_label = "numeric"
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                dtype_label = "datetime"
            elif pd.api.types.is_bool_dtype(df[col]):
                dtype_label = "boolean"

            unique_count = int(df[col].nunique(dropna=True))
            if unique_count == len(df) and len(df) > 50:
                dtype_label = "id_like"

            is_pii = any(k in col.lower() for k in PII_KEYWORDS)
            if is_pii:
                pii_columns.append(col)

            # Sample values with PII redaction
            raw_samples = df[col].dropna().head(3).tolist()
            if is_pii:
                sample_values = ["[REDACTED]"] * len(raw_samples)
            else:
                sample_values = [str(x)[:100] for x in raw_samples]

            cols_meta[col] = {
                "dtype": dtype_label,
                "null_pct": float(df[col].isnull().mean() * 100),
                "unique_count": unique_count,
                "sample_values": sample_values,
                "is_pii": is_pii,
            }

        domain = cls.detect_domain(list(df.columns))
        return {
            "columns": cols_meta,
            "row_count": len(df),
            "col_count": len(df.columns),
            "detected_domain": domain,
            "pii_detected": len(pii_columns) > 0,
            "pii_columns": pii_columns,
        }

    @classmethod
    def _clean_and_write_parquet(
        cls,
        df: pd.DataFrame,
        clean_filename: str,
        parquet_rel_path: str,
    ) -> tuple[dict[str, Any], int, int]:
        """Validate, sanitize columns, normalize mixed types, and write zstd Parquet."""
        post_val = UploadGuard.validate_after_read(df, clean_filename)
        if not post_val["safe"]:
            raise ValueError(post_val["error"])

        df, _ = InputSanitizer.sanitize_column_names(df)

        # PyArrow Mixed-Type Resilience
        for col in df.columns:
            if df[col].dtype == "object":
                s_cleaned = df[col].replace(["NULL", "null", "NA", "na", "NaN", "None", ""], None)
                numeric_s = pd.to_numeric(s_cleaned, errors="coerce")
                valid_count = s_cleaned.dropna().count()
                if valid_count > 0 and numeric_s.notnull().sum() == valid_count:
                    df[col] = numeric_s
                else:
                    df[col] = df[col].apply(
                        lambda v: None if pd.isna(v) or (isinstance(v, str) and v.strip().upper() in ("NULL", "NA", "NAN", "NONE", "")) else str(v)
                    )

        schema_info = cls.extract_schema_metadata(df)

        try:
            arrow_table = pa.Table.from_pandas(df, preserve_index=False)
            pq.write_table(arrow_table, parquet_rel_path, compression="zstd")
        except Exception as e:
            logger.warning("pa.Table.from_pandas failed (%s), stringifying objects for fallback", e)
            for col in df.columns:
                if df[col].dtype == "object":
                    df[col] = df[col].astype(str).replace({"nan": None, "None": None, "<NA>": None})
            df.to_parquet(parquet_rel_path, engine="pyarrow", compression="zstd", index=False)

        return schema_info, len(df), len(df.columns)

    @classmethod
    def _process_file_sync(
        cls,
        file_bytes: bytes,
        clean_filename: str,
        parquet_rel_path: str,
    ) -> tuple[dict[str, Any], int, int, str]:
        """Synchronous CPU/disk heavy file parsing and Parquet conversion.

        Executed via asyncio.to_thread to keep FastAPI's event loop fully non-blocking.
        Supports multi-sheet Excel workbooks by persisting each non-empty sheet.
        """
        ext = os.path.splitext(clean_filename)[1].lstrip(".").lower()

        if ext in ("xlsx", "xls"):
            xl = pd.ExcelFile(io.BytesIO(file_bytes))
            sheet_entries: list[dict[str, Any]] = []
            primary_schema: dict[str, Any] | None = None
            primary_rows = 0
            primary_cols = 0
            base_path = parquet_rel_path[:-8] if parquet_rel_path.endswith(".parquet") else parquet_rel_path

            for idx, sheet_name in enumerate(xl.sheet_names):
                try:
                    sheet_df = xl.parse(sheet_name)
                except Exception as exc:
                    logger.debug("Skipping unreadable sheet '%s': %s", sheet_name, exc)
                    continue
                if sheet_df.empty or len(sheet_df.columns) == 0:
                    continue

                is_first = len(sheet_entries) == 0
                target_path = parquet_rel_path if is_first else f"{base_path}_sheet_{idx}.parquet"
                s_meta, r_cnt, c_cnt = cls._clean_and_write_parquet(sheet_df, clean_filename, target_path)
                sheet_entries.append({
                    "name": str(sheet_name),
                    "parquet_path": target_path,
                    "row_count": r_cnt,
                    "col_count": c_cnt,
                    "schema_json": s_meta,
                })
                if is_first:
                    primary_schema = dict(s_meta)
                    primary_rows = r_cnt
                    primary_cols = c_cnt

            if primary_schema is None:
                raise ValueError("Uploaded Excel workbook contains no non-empty sheets.")

            if len(sheet_entries) > 1:
                primary_schema["active_sheet"] = sheet_entries[0]["name"]
                primary_schema["sheets"] = sheet_entries
            return primary_schema, primary_rows, primary_cols, ext

        df = cls.load_dataframe_from_bytes(file_bytes, clean_filename)
        schema_info, row_count, col_count = cls._clean_and_write_parquet(
            df, clean_filename, parquet_rel_path
        )
        return schema_info, row_count, col_count, ext

    @classmethod
    async def ingest_file(
        cls,
        file_bytes: bytes,
        original_filename: str,
        user_id: Any,
        org_id: Any,
        db: AsyncSession,
    ) -> tuple[UserFile, GlobalFile, bool]:
        """
        Transactional ingestion: checks pre-read guard, computes SHA-256,
        locks global_files row with FOR UPDATE, persists single on-disk Parquet,
        and provisions user_files reference.
        """
        clean_filename = InputSanitizer.sanitize_filename(original_filename)
        pre_val = UploadGuard.validate_before_read(file_bytes, clean_filename)
        if not pre_val["safe"]:
            raise ValueError(pre_val["error"])

        sha256 = cls.compute_sha256(file_bytes)
        os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
        parquet_rel_path = os.path.join(settings.UPLOADS_DIR, f"{sha256}.parquet").replace(
            "\\", "/"
        )

        # 1. Atomic Check & Lock on global_files
        stmt = select(GlobalFile).where(GlobalFile.sha256_hash == sha256).with_for_update()
        result = await db.execute(stmt)
        global_file = result.scalar_one_or_none()
        is_deduplicated = False

        if global_file is not None:
            global_file.ref_count += 1
            is_deduplicated = True
        else:
            # Parse dataset and write Parquet in worker thread (non-blocking)
            schema_info, row_count, col_count, ext = await asyncio.to_thread(
                cls._process_file_sync, file_bytes, clean_filename, parquet_rel_path
            )

            global_file = GlobalFile(
                sha256_hash=sha256,
                parquet_path=parquet_rel_path,
                original_format=ext,
                file_size_bytes=len(file_bytes),
                row_count=row_count,
                col_count=col_count,
                schema_json=schema_info,
                detected_domain=schema_info["detected_domain"],
                ref_count=1,
            )
            db.add(global_file)
            await db.flush()

        # 2. Check if UserFile already exists for (user_id, global_file.id, clean_filename)
        user_file_stmt = select(UserFile).where(
            UserFile.user_id == user_id,
            UserFile.global_file_id == global_file.id,
            UserFile.display_name == clean_filename,
        )
        existing_uf = (await db.execute(user_file_stmt)).scalar_one_or_none()
        if existing_uf:
            await db.commit()
            return existing_uf, global_file, is_deduplicated

        user_file = UserFile(
            user_id=user_id,
            org_id=org_id,
            global_file_id=global_file.id,
            display_name=clean_filename,
        )
        db.add(user_file)
        await db.commit()
        await db.refresh(user_file)
        await db.refresh(global_file)

        return user_file, global_file, is_deduplicated
