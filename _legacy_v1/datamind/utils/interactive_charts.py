"""
Interactive chart generators using Plotly.

All charts are styled to match DataMind's dark glassmorphic theme.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import numpy as np

try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# ── DataMind dark theme ─────────────────────────────────────────
DATAMIND_TEMPLATE = {
    "layout": {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(30, 30, 46, 0.6)",
        "font": {"color": "#E0E0E0", "family": "Inter, sans-serif"},
        "title": {"font": {"family": "Outfit, sans-serif", "size": 18, "color": "#FFFFFF"}},
        "xaxis": {
            "gridcolor": "rgba(255,255,255,0.05)",
            "linecolor": "rgba(255,255,255,0.1)",
            "tickfont": {"color": "#9CA3AF"},
            "title": {"font": {"color": "#9CA3AF"}},
        },
        "yaxis": {
            "gridcolor": "rgba(255,255,255,0.05)",
            "linecolor": "rgba(255,255,255,0.1)",
            "tickfont": {"color": "#9CA3AF"},
            "title": {"font": {"color": "#9CA3AF"}},
        },
        "colorway": [
            "#6C63FF", "#48C9B0", "#F97316", "#8B5CF6",
            "#3B82F6", "#14B8A6", "#EC4899", "#FBBF24",
        ],
        "legend": {"font": {"color": "#9CA3AF"}},
        "margin": {"l": 60, "r": 30, "t": 50, "b": 50},
    }
}

ACCENT_GRADIENT = [
    [0.0, "#6C63FF"],
    [0.5, "#48C9B0"],
    [1.0, "#F97316"],
]


def _apply_theme(fig: "go.Figure") -> "go.Figure":
    """Apply DataMind dark theme to a Plotly figure."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(30, 30, 46, 0.6)",
        font=dict(color="#E0E0E0", family="Inter, sans-serif"),
        title_font=dict(family="Outfit, sans-serif", size=18, color="#FFFFFF"),
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.05)",
            linecolor="rgba(255,255,255,0.1)",
            tickfont=dict(color="#9CA3AF"),
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.05)",
            linecolor="rgba(255,255,255,0.1)",
            tickfont=dict(color="#9CA3AF"),
        ),
        legend=dict(font=dict(color="#9CA3AF")),
        margin=dict(l=60, r=30, t=50, b=50),
    )
    return fig


# ═══════════════════════════════════════════════════════════════
# Individual chart generators
# ═══════════════════════════════════════════════════════════════

def auto_histogram(df: pd.DataFrame, column: str, bins: int = 30) -> "go.Figure":
    """Create an interactive histogram for a numeric column."""
    fig = px.histogram(
        df, x=column, nbins=bins,
        title=f"Distribution of {column}",
        color_discrete_sequence=["#6C63FF"],
        opacity=0.85,
    )
    fig.update_traces(
        marker_line_color="rgba(108, 99, 255, 0.8)",
        marker_line_width=1,
    )
    return _apply_theme(fig)


def auto_scatter(
    df: pd.DataFrame, x: str, y: str, color: Optional[str] = None
) -> "go.Figure":
    """Create an interactive scatter plot."""
    fig = px.scatter(
        df, x=x, y=y, color=color,
        title=f"{y} vs {x}",
        color_discrete_sequence=[
            "#6C63FF", "#48C9B0", "#F97316", "#8B5CF6",
            "#3B82F6", "#14B8A6", "#EC4899", "#FBBF24",
        ],
        opacity=0.7,
    )
    fig.update_traces(marker=dict(size=6, line=dict(width=0.5, color="rgba(255,255,255,0.1)")))
    return _apply_theme(fig)


def auto_bar(
    df: pd.DataFrame, x: str, y: str, orientation: str = "v"
) -> "go.Figure":
    """Create an interactive bar chart."""
    fig = px.bar(
        df, x=x, y=y, orientation=orientation,
        title=f"{y} by {x}",
        color_discrete_sequence=["#48C9B0"],
    )
    fig.update_traces(
        marker_line_color="rgba(72, 201, 176, 0.8)",
        marker_line_width=1,
        opacity=0.85,
    )
    return _apply_theme(fig)


def auto_line(df: pd.DataFrame, x: str, y: str) -> "go.Figure":
    """Create an interactive line chart."""
    fig = px.line(
        df, x=x, y=y,
        title=f"{y} over {x}",
        color_discrete_sequence=["#6C63FF"],
    )
    fig.update_traces(line=dict(width=2.5))
    return _apply_theme(fig)


def auto_box(df: pd.DataFrame, column: str, group_by: Optional[str] = None) -> "go.Figure":
    """Create an interactive box plot."""
    fig = px.box(
        df, y=column, x=group_by,
        title=f"Box Plot — {column}" + (f" by {group_by}" if group_by else ""),
        color_discrete_sequence=[
            "#6C63FF", "#48C9B0", "#F97316", "#8B5CF6",
        ],
        color=group_by,
    )
    return _apply_theme(fig)


def auto_correlation_heatmap(df: pd.DataFrame) -> "go.Figure":
    """Create an interactive correlation heatmap for numeric columns."""
    numeric_df = df.select_dtypes(include=["number"])
    if numeric_df.empty or numeric_df.shape[1] < 2:
        fig = go.Figure()
        fig.add_annotation(
            text="Need at least 2 numeric columns for correlation",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(color="#9CA3AF", size=14),
        )
        return _apply_theme(fig)

    corr = numeric_df.corr()

    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns.tolist(),
        y=corr.index.tolist(),
        colorscale=[
            [0.0, "#6C63FF"],
            [0.25, "#1E1E2E"],
            [0.5, "#0A0A12"],
            [0.75, "#1E3A3A"],
            [1.0, "#48C9B0"],
        ],
        zmid=0,
        text=np.round(corr.values, 2),
        texttemplate="%{text}",
        textfont=dict(size=11, color="#E0E0E0"),
        hovertemplate="<b>%{x}</b> vs <b>%{y}</b><br>Correlation: %{z:.3f}<extra></extra>",
        colorbar=dict(
            title="Correlation",
            titlefont=dict(color="#9CA3AF"),
            tickfont=dict(color="#9CA3AF"),
        ),
    ))
    fig.update_layout(title="Correlation Matrix")
    return _apply_theme(fig)


def auto_pie(df: pd.DataFrame, column: str, top_n: int = 10) -> "go.Figure":
    """Create an interactive pie/donut chart for a categorical column."""
    counts = df[column].value_counts().head(top_n)
    if len(df[column].value_counts()) > top_n:
        other_count = df[column].value_counts().iloc[top_n:].sum()
        counts = pd.concat([counts, pd.Series({"Other": other_count})])

    fig = go.Figure(data=[go.Pie(
        labels=counts.index.tolist(),
        values=counts.values.tolist(),
        hole=0.45,
        marker=dict(
            colors=["#6C63FF", "#48C9B0", "#F97316", "#8B5CF6",
                     "#3B82F6", "#14B8A6", "#EC4899", "#FBBF24",
                     "#A78BFA", "#34D399", "#FB923C"],
            line=dict(color="rgba(10,10,18,0.8)", width=2),
        ),
        textfont=dict(color="#E0E0E0"),
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>",
    )])
    fig.update_layout(title=f"Distribution of {column}")
    return _apply_theme(fig)


# ═══════════════════════════════════════════════════════════════
# Auto-visualization engine
# ═══════════════════════════════════════════════════════════════

def auto_visualize(df: pd.DataFrame, max_charts: int = 6) -> list[tuple[str, "go.Figure"]]:
    """
    Automatically generate relevant interactive charts based on the dataset structure.

    Returns a list of (title, figure) tuples.
    """
    if not PLOTLY_AVAILABLE:
        return []

    charts: list[tuple[str, "go.Figure"]] = []
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

    # 1. Correlation heatmap (if enough numeric columns)
    if len(numeric_cols) >= 2:
        charts.append(("Correlation Matrix", auto_correlation_heatmap(df)))

    # 2. Distributions of top numeric columns
    for col in numeric_cols[:3]:
        if len(charts) >= max_charts:
            break
        charts.append((f"Distribution: {col}", auto_histogram(df, col)))

    # 3. Scatter plot of first two numeric columns
    if len(numeric_cols) >= 2 and len(charts) < max_charts:
        color_col = categorical_cols[0] if categorical_cols else None
        charts.append((
            f"Scatter: {numeric_cols[0]} vs {numeric_cols[1]}",
            auto_scatter(df, numeric_cols[0], numeric_cols[1], color=color_col),
        ))

    # 4. Categorical distributions (pie charts)
    for col in categorical_cols[:2]:
        if len(charts) >= max_charts:
            break
        n_unique = df[col].nunique()
        if 2 <= n_unique <= 20:
            charts.append((f"Categories: {col}", auto_pie(df, col)))

    # 5. Box plots of numeric by category
    if numeric_cols and categorical_cols and len(charts) < max_charts:
        cat_col = categorical_cols[0]
        if df[cat_col].nunique() <= 10:
            charts.append((
                f"Box: {numeric_cols[0]} by {cat_col}",
                auto_box(df, numeric_cols[0], group_by=cat_col),
            ))

    return charts[:max_charts]
