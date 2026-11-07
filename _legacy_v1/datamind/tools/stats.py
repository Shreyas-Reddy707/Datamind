"""
Tools for fast pandas profiling and statistics computation.
Aligns with Phase 2 requirements for the Summary Agent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np

from config import NULL_RATE_THRESHOLD

logger = logging.getLogger(__name__)

@dataclass
class DatasetStats:
    """Pre-computed statistics for the Summary Agent."""
    row_count: int
    column_count: int
    memory_usage_mb: float
    duplicate_rows: int
    null_percent: Dict[str, float]
    column_types: Dict[str, List[str]] # Grouped by type: {"numeric": [...], "categorical": [...], etc.}
    column_details: Dict[str, Dict[str, Any]] # Per-column details
    top_columns: List[str]
    ml_capabilities: List[str]
    data_quality_warnings: List[str]

def compute_fast_stats(df: pd.DataFrame, sample_threshold: int = 50000) -> DatasetStats:
    """
    Computes dataset statistics with performance optimizations for large datasets.
    """
    row_count = len(df)
    column_count = len(df.columns)
    
    # Performance Optimization: Deep memory usage is slow on large datasets
    if row_count > sample_threshold:
        # Sample for memory estimation
        memory_usage_mb = (df.memory_usage(deep=True).sum() / (1024 * 1024))
    else:
        memory_usage_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
        
    # Performance Optimization: Duplication check is O(N) but can be slow
    if row_count > sample_threshold:
        duplicate_rows = -1 # Indicate it was skipped for speed
    else:
        duplicate_rows = int(df.duplicated().sum())
    
    null_percent = {col: float(df[col].isnull().mean() * 100) for col in df.columns}
    
    # Column Details
    column_types = {}
    numeric_cols = []
    categorical_cols = []
    datetime_cols = []
    boolean_cols = []
    
    for col in df.columns:
        dtype = str(df[col].dtype)
        
        # Performance Tuning: nunique can be slow
        if row_count > sample_threshold:
             unique_count = int(df[col].head(sample_threshold).nunique())
        else:
             unique_count = int(df[col].nunique())
             
        sample_values = [str(v) for v in df[col].dropna().head(3).tolist()]
        
        col_type = "categorical"
        if pd.api.types.is_numeric_dtype(df[col]):
            col_type = "numeric"
            numeric_cols.append(col)
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            col_type = "datetime"
            datetime_cols.append(col)
        elif pd.api.types.is_bool_dtype(df[col]):
            col_type = "boolean"
            boolean_cols.append(col)
        else:
            categorical_cols.append(col)
            
        column_types[col] = {
            "type": col_type,
            "dtype": dtype,
            "unique_count": unique_count,
            "sample_values": sample_values,
            "null_pct": null_percent[col]
        }

    # Top columns identification logic (Improved accuracy)
    top_columns = _identify_top_columns(df, numeric_cols, null_percent)
    
    ml_capabilities = _assess_ml_capabilities(df, numeric_cols, categorical_cols, datetime_cols, null_percent)
    data_quality_warnings = _get_data_quality_warnings(df, null_percent, column_types)
    
    return DatasetStats(
        row_count=row_count,
        column_count=column_count,
        memory_usage_mb=round(memory_usage_mb, 2),
        duplicate_rows=duplicate_rows,
        null_percent=null_percent,
        column_types={
            "all": df.columns.tolist(),
            "numeric": numeric_cols,
            "categorical": categorical_cols,
            "datetime": datetime_cols,
            "boolean": boolean_cols
        },
        column_details=column_types,
        top_columns=top_columns,
        ml_capabilities=ml_capabilities,
        data_quality_warnings=data_quality_warnings
    )

def _identify_top_columns(df: pd.DataFrame, numeric_cols: List[str], null_percent: Dict[str, float]) -> List[str]:
    """Identifies top columns based on variance, entropy, and information density."""
    scores = []
    
    # Noise words that usually imply non-analytical columns
    noise_words = ["id", "uuid", "guid", "index", "unnamed", "pk", "fk", "key", "name", "email", "phone", "address", "contact", "street", "city", "state", "zip"]
    
    for col in df.columns:
        # Ignore ID/Index columns from being 'Top' insights
        if any(x in col.lower() for x in noise_words):
            continue
            
        null_factor = (1 - null_percent[col] / 100)
        
        if col in numeric_cols:
            # Standardized variance for numeric
            std_dev = df[col].std() if len(df) > 1 else 0
            if np.isnan(std_dev): std_dev = 0
            # Higher variance (within reason) usually means more info
            score = std_dev * null_factor
        else:
            # Categorical importance: prefer columns with 5-20 unique values (segments)
            unique_count = df[col].nunique()
            if 2 <= unique_count <= 25:
                # Golden ratio for categorical insights: not too few, not too many
                score = (unique_count / 10) * 5 * null_factor
            else:
                score = 0
                
        scores.append((col, score))
    
    # Sort and take top 5 for better variety
    scores.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in scores[:5]]

def _assess_ml_capabilities(df: pd.DataFrame, numeric_cols: List[str], categorical_cols: List[str], datetime_cols: List[str], null_percent: Dict[str, float]) -> List[str]:
    capabilities = []
    
    # Classification
    for col in categorical_cols:
        unique = df[col].nunique()
        if 2 <= unique <= 20 and null_percent[col] < 30:
            capabilities.append(f"Classification possible → target column: {col} ({'binary' if unique == 2 else f'{unique} classes'})")
            break
            
    # Regression
    for col in numeric_cols:
        if df[col].nunique() > 10 and null_percent[col] < 30:
            capabilities.append(f"Regression possible → target column: {col} (continuous)")
            break
            
    # Forecasting
    if datetime_cols:
        capabilities.append(f"Forecasting possible → found {len(datetime_cols)} datetime columns")
    else:
        capabilities.append("Forecasting NOT possible → no datetime column found")
        
    # Clustering
    clean_numeric = [c for c in numeric_cols if null_percent[c] < (NULL_RATE_THRESHOLD * 100)]
    if len(clean_numeric) >= 2:
        capabilities.append(f"Clustering possible → {len(clean_numeric)} numeric features with low null rate")
    else:
        capabilities.append(f"Clustering likely not optimal → only {len(clean_numeric)} clean numeric columns")
        
    return capabilities

def _get_data_quality_warnings(df: pd.DataFrame, null_percent: Dict[str, float], column_types: Dict[str, Dict[str, Any]]) -> List[str]:
    warnings = []
    for col, pct in null_percent.items():
        if pct > 30:
            warnings.append(f"Column '{col}' has high null rate ({pct:.1f}%)")
            
    for col, details in column_types.items():
        if details["unique_count"] == 1:
            warnings.append(f"Column '{col}' has only one unique value (constant)")
        if details["type"] == "numeric" and details["unique_count"] == len(df) and len(df) > 100:
            warnings.append(f"Column '{col}' appears to be a unique ID or index")
            
    if df.duplicated().any():
        warnings.append(f"Dataset contains {df.duplicated().sum()} duplicate rows")
            
    return warnings
