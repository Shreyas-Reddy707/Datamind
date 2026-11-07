"""
CSV loading, validation, and profiling utilities.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class DataProfile:
    """Summary profile of a loaded DataFrame."""
    rows: int
    columns: int
    file_size_kb: float
    dtypes: dict[str, str]
    null_counts: dict[str, int]
    numeric_summary: Optional[pd.DataFrame] = None
    column_names: list[str] = field(default_factory=list)
    sample_values: dict[str, list] = field(default_factory=dict)


def load_csv(uploaded_file) -> pd.DataFrame:
    """
    Load a CSV from a Streamlit UploadedFile or file-like object.

    Args:
        uploaded_file: A file-like object containing CSV data.

    Returns:
        A pandas DataFrame.

    Raises:
        ValueError: If the file cannot be parsed as CSV.
    """
    try:
        # Reset file position if possible
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file)
        if df.empty:
            raise ValueError("The uploaded CSV file is empty.")
        return df
    except pd.errors.EmptyDataError:
        raise ValueError("The uploaded file contains no data.")
    except pd.errors.ParserError as exc:
        raise ValueError(f"Could not parse the file as CSV: {exc}")


def validate_csv(df: pd.DataFrame) -> list[str]:
    """
    Validate a DataFrame and return a list of warning messages (empty = all good).
    """
    warnings: list[str] = []

    if df.shape[0] == 0:
        warnings.append("Dataset has no rows.")
    if df.shape[1] == 0:
        warnings.append("Dataset has no columns.")

    # Check for fully-null columns
    fully_null = [col for col in df.columns if df[col].isna().all()]
    if fully_null:
        warnings.append(f"Columns with all null values: {', '.join(fully_null)}")

    # Check for duplicate column names
    dupes = df.columns[df.columns.duplicated()].tolist()
    if dupes:
        warnings.append(f"Duplicate column names detected: {', '.join(dupes)}")

    # Warn if very large
    if df.shape[0] > 500_000:
        warnings.append(
            f"Large dataset ({df.shape[0]:,} rows). Analysis may be slow."
        )

    return warnings


def profile_dataframe(df: pd.DataFrame, file_size_bytes: int = 0) -> DataProfile:
    """
    Compute a summary profile of the DataFrame.

    Args:
        df: The pandas DataFrame to profile.
        file_size_bytes: Size of the original file in bytes.

    Returns:
        A DataProfile dataclass.
    """
    dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
    null_counts = {col: int(df[col].isna().sum()) for col in df.columns}

    # Numeric summary
    numeric_cols = df.select_dtypes(include=["number"])
    numeric_summary = numeric_cols.describe().T if not numeric_cols.empty else None

    # Sample values (first 3 non-null values per column)
    sample_values: dict[str, list] = {}
    for col in df.columns:
        non_null = df[col].dropna().head(3).tolist()
        sample_values[col] = [str(v) for v in non_null]

    return DataProfile(
        rows=df.shape[0],
        columns=df.shape[1],
        file_size_kb=round(file_size_bytes / 1024, 2) if file_size_bytes else 0,
        dtypes=dtypes,
        null_counts=null_counts,
        numeric_summary=numeric_summary,
        column_names=list(df.columns),
        sample_values=sample_values,
    )


def schema_summary(df: pd.DataFrame) -> str:
    """
    Return a concise text summary of the DataFrame schema for use in LLM prompts.

    Example:
        Columns (5):
        - name (object): e.g. "Alice", "Bob"
        - age (int64): e.g. 25, 30
        - salary (float64): e.g. 50000.0, 72000.5
    """
    lines = [f"Columns ({df.shape[1]}):"]
    for col in df.columns:
        dtype = df[col].dtype
        samples = df[col].dropna().head(2).tolist()
        sample_str = ", ".join(repr(s) for s in samples)
        lines.append(f"  - {col} ({dtype}): e.g. {sample_str}")
    lines.append(f"\nRows: {df.shape[0]}")
    return "\n".join(lines)
