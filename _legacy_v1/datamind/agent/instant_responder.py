"""
Instant Responder for DataMind v4.0.
Handles Tier 1 queries using direct pandas computation for sub-100ms latency.
"""

import re
import pandas as pd
from typing import Dict, Any

def handle_tier1(query: str, df: pd.DataFrame, fingerprint: Dict[str, Any]) -> str:
    """
    Routes Tier 1 queries to specific pandas-based handlers.
    """
    q_lower = query.lower().strip()
    
    # 1. Row Count
    if any(x in q_lower for x in ["how many rows", "row count"]):
        return f"**{len(df):,} rows** found in this dataset."

    # 2. Column Listing
    if any(x in q_lower for x in ["list columns", "what columns", "show columns"]):
        return _format_column_table(fingerprint)

    # 3. Numeric Aggregations (Average, Sum, Max, Min)
    agg_match = re.search(r"(average|mean|max|min|sum|count) of (.+)", q_lower)
    if agg_match:
        agg_type = agg_match.group(1)
        col_query = agg_match.group(2).strip()
        return _handle_aggregation(agg_type, col_query, df, fingerprint)

    # 4. Null Checks
    if any(x in q_lower for x in ["how many nulls", "missing values", "null values"]):
        return _handle_null_summary(df)

    # 5. Null count in specific column
    null_in_match = re.search(r"null.*in (.+)", q_lower)
    if null_in_match:
        col_query = null_in_match.group(1).strip()
        return _handle_column_nulls(col_query, df, fingerprint)

    return "I identified this as a statistics question, but I couldn't calculate the specific value. Try asking 'what columns' or 'average of [col]'."

def _format_column_table(fingerprint: Dict[str, Any]) -> str:
    """Formats columns into a markdown table by type."""
    cols = fingerprint.get("columns", {})
    if not cols: return "I don't have schema info for this file."
    
    rows = []
    # Sort columns: numeric first, then others
    sorted_cols = sorted(cols.items(), key=lambda x: x[1].get("dtype") != "numeric")
    
    for col, meta in sorted_cols[:15]: # Limit to 15 for brevity
        dtype = meta.get("dtype", "unknown")
        null_pct = meta.get("null_pct", 0)
        rows.append(f"| {col} | {dtype} | {null_pct:.1f}% |")
    
    table = "| Column | Type | Nulls |\n| :--- | :--- | :--- |\n" + "\n".join(rows)
    if len(cols) > 15:
        table += f"\n\n*(Showing 15 of {len(cols)} columns)*"
    return table

def _handle_aggregation(agg_type: str, col_query: str, df: pd.DataFrame, fingerprint: Dict[str, Any]) -> str:
    """Performs direct pandas aggregation on a target column."""
    # Remove common punctuation from query
    col_query = re.sub(r'[^\w\s]', '', col_query).strip()
    
    # Find matching column
    target_col = None
    for col in df.columns:
        if col.lower() == col_query:
            target_col = col
            break
            
    if not target_col:
        # Fuzzy match
        import difflib
        matches = difflib.get_close_matches(col_query, df.columns, n=1, cutoff=0.6)
        if matches: target_col = matches[0]

    if not target_col:
        return f"I couldn't find a column matching '{col_query}'."

    # Validate type for numeric aggs
    is_numeric = pd.api.types.is_numeric_dtype(df[target_col])
    
    try:
        if agg_type in ["average", "mean"]:
            if not is_numeric: return f"**{target_col}** is not numeric (it is {fingerprint['columns'][target_col]['dtype']})."
            val = df[target_col].mean()
            return f"**Average {target_col}**: {val:,.2f}"
            
        elif agg_type == "sum":
            if not is_numeric: return f"**{target_col}** is not numeric."
            val = df[target_col].sum()
            return f"**Total {target_col}**: {val:,.2f} across all {len(df):,} rows."
            
        elif agg_type == "max":
            val = df[target_col].max()
            # Try to get context for max
            idx = df[target_col].idxmax() if is_numeric else None
            return f"**Max {target_col}**: {val}."
            
        elif agg_type == "min":
            val = df[target_col].min()
            return f"**Min {target_col}**: {val}."
            
        elif agg_type == "count":
            val = df[target_col].count()
            return f"**Count of {target_col}**: {val:,} non-null values."
            
    except Exception as e:
        return f"Error calculating {agg_type} for {target_col}: {str(e)}"
    
    return f"Unsupported aggregation: {agg_type}"

def _handle_null_summary(df: pd.DataFrame) -> str:
    """Returns a table of columns with missing values."""
    null_counts = df.isnull().sum()
    null_cols = null_counts[null_counts > 0].sort_values(ascending=False)
    
    if null_cols.empty:
        return "✅ **No missing values** found in this dataset."
    
    rows = []
    for col, count in null_cols.items()[:10]:
        pct = (count / len(df)) * 100
        rows.append(f"| {col} | {count:,} | {pct:.1f}% |")
        
    table = "| Column | Missing | Pct |\n| :--- | :--- | :--- |\n" + "\n".join(rows)
    if len(null_cols) > 10:
        table += f"\n\n*(Showing top 10 of {len(null_cols)} columns with nulls)*"
    return table

def _handle_column_nulls(col_query: str, df: pd.DataFrame, fingerprint: Dict[str, Any]) -> str:
    """Returns null info for a specific column."""
    # Find matching column
    target_col = None
    for col in df.columns:
        if col.lower() in col_query.lower():
            target_col = col
            break
            
    if not target_col:
        return f"I couldn't find a column matching your query for null checks."
        
    count = int(df[target_col].isnull().sum())
    pct = (count / len(df)) * 100
    if count == 0:
        return f"✅ **{target_col}** has no missing values."
    return f"**{target_col}** has **{count:,} missing values** ({pct:.1f}% of data)."
