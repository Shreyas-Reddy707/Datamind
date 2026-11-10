"""DataMind v2 Dark-Mode Plotly Chart Builder.

Constructs production-grade Plotly chart JSON specifications styled with our
Anti-Vibecode Zinc/Slate/Emerald (#09090B / #18181B / #10B981) design system.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

logger = logging.getLogger("datamind.engine.chart_builder")

# Zinc/Slate/Emerald Design Tokens
DARK_THEME_LAYOUT = {
    "plot_bgcolor": "#121215",
    "paper_bgcolor": "#09090B",
    "font": {
        "color": "#FAFAFA",
        "family": "Geist Sans, Inter, system-ui, sans-serif",
        "size": 12,
    },
    "xaxis": {
        "gridcolor": "#27272A",
        "zerolinecolor": "#3F3F46",
        "tickfont": {"color": "#A1A1AA"},
    },
    "yaxis": {
        "gridcolor": "#27272A",
        "zerolinecolor": "#3F3F46",
        "tickfont": {"color": "#A1A1AA"},
    },
    "colorway": [
        "#10B981",  # Emerald primary accent
        "#3B82F6",  # Blue secondary
        "#F59E0B",  # Amber warning
        "#EC4899",  # Pink
        "#8B5CF6",  # Violet
        "#06B6D4",  # Cyan
    ],
    "margin": {"l": 50, "r": 30, "t": 50, "b": 50},
    "legend": {
        "font": {"color": "#A1A1AA"},
        "bgcolor": "rgba(18, 18, 21, 0.8)",
        "bordercolor": "#27272A",
        "borderwidth": 1,
    },
}


class ChartBuilder:
    """Builds interactive Plotly specifications as pure JSON-serializable dictionaries."""

    @classmethod
    def to_spec(cls, fig: go.Figure) -> dict[str, Any]:
        """Convert Plotly Figure to JSON-serializable dict with pure primitives."""
        fig.update_layout(**DARK_THEME_LAYOUT)
        return json.loads(fig.to_json())

    @classmethod
    def build_bar(
        cls,
        df: pd.DataFrame,
        x_col: str,
        y_col: str | None = None,
        color_col: str | None = None,
        max_categories: int = 15,
    ) -> dict[str, Any] | None:
        """Grouped or aggregated bar chart comparing y_col across categories of x_col."""
        if x_col not in df.columns:
            return None

        if not y_col or y_col not in df.columns or x_col == y_col:
            return cls.build_distribution(df, x_col, max_categories=max_categories)

        # Bin numeric x_col if high cardinality, or take top categories
        work_df = df[[x_col, y_col] + ([color_col] if color_col and color_col in df.columns and color_col not in (x_col, y_col) else [])].dropna(subset=[x_col, y_col])
        if work_df.empty:
            return None

        if pd.api.types.is_numeric_dtype(work_df[x_col]) and work_df[x_col].nunique() > max_categories:
            work_df = work_df.copy()
            work_df["_bin"] = pd.qcut(work_df[x_col], q=min(8, work_df[x_col].nunique()), duplicates="drop").astype(str)
            group_col = "_bin"
        else:
            top_cats = work_df[x_col].value_counts().head(max_categories).index
            work_df = work_df[work_df[x_col].isin(top_cats)].copy()
            work_df[x_col] = work_df[x_col].astype(str)
            group_col = x_col

        if pd.api.types.is_numeric_dtype(work_df[y_col]):
            if color_col and color_col in work_df.columns and color_col not in (x_col, y_col):
                top_colors = work_df[color_col].value_counts().head(6).index
                work_df = work_df[work_df[color_col].isin(top_colors)].copy()
                work_df[color_col] = work_df[color_col].astype(str)
                agg = work_df.groupby([group_col, color_col], observed=True)[y_col].mean().reset_index()
                fig = px.bar(
                    agg,
                    x=group_col,
                    y=y_col,
                    color=color_col,
                    barmode="group",
                    labels={group_col: x_col, y_col: f"Avg {y_col}"},
                    title=f"Average {y_col} by {x_col} & {color_col}",
                )
            else:
                agg = work_df.groupby(group_col, observed=True)[y_col].mean().reset_index()
                fig = px.bar(
                    agg,
                    x=group_col,
                    y=y_col,
                    color_discrete_sequence=["#10B981"],
                    labels={group_col: x_col, y_col: f"Avg {y_col}"},
                    title=f"Average {y_col} by {x_col}",
                )
        else:
            counts = work_df.groupby([group_col, y_col], observed=True).size().reset_index(name="count")
            fig = px.bar(
                counts,
                x=group_col,
                y="count",
                color=y_col,
                barmode="group",
                labels={group_col: x_col, "count": "Count"},
                title=f"{x_col} Breakdown by {y_col}",
            )

        return cls.to_spec(fig)

    @classmethod
    def build_distribution(
        cls, df: pd.DataFrame, column: str, max_categories: int = 15
    ) -> dict[str, Any] | None:
        """Histogram for continuous numeric data; bar chart for categorical."""
        if column not in df.columns:
            return None

        if pd.api.types.is_numeric_dtype(df[column]):
            sample_df = df.sample(min(len(df), 2000), random_state=42) if len(df) > 2000 else df
            fig = px.histogram(
                sample_df,
                x=column,
                nbins=30,
                color_discrete_sequence=["#10B981"],
                title=f"Distribution of {column}",
            )
        else:
            counts = df[column].value_counts().head(max_categories)
            fig = px.bar(
                x=counts.index.astype(str),
                y=counts.values,
                color_discrete_sequence=["#3B82F6"],
                labels={"x": column, "y": "Count"},
                title=f"Category Counts: {column}",
            )

        return cls.to_spec(fig)

    @classmethod
    def build_scatter(
        cls,
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
        color_col: str | None = None,
    ) -> dict[str, Any] | None:
        """Bivariate scatter plot with optional categorical or continuous color mapping."""
        if x_col not in df.columns or y_col not in df.columns:
            return None

        sample_df = df.sample(min(len(df), 2000), random_state=42) if len(df) > 2000 else df
        fig = px.scatter(
            sample_df,
            x=x_col,
            y=y_col,
            color=color_col if color_col in df.columns else None,
            color_discrete_sequence=["#10B981"] if not color_col else None,
            title=f"{x_col} vs {y_col}",
        )
        return cls.to_spec(fig)

    @classmethod
    def build_line(
        cls, df: pd.DataFrame, date_col: str, value_col: str
    ) -> dict[str, Any] | None:
        """Timeseries line chart with sorted dates."""
        if date_col not in df.columns or value_col not in df.columns:
            return None

        clean_df = df[[date_col, value_col]].dropna().sort_values(by=date_col)
        sample_df = clean_df.sample(min(len(clean_df), 2000), random_state=42).sort_values(by=date_col) if len(clean_df) > 2000 else clean_df
        fig = px.line(
            sample_df,
            x=date_col,
            y=value_col,
            color_discrete_sequence=["#10B981"],
            title=f"Timeline: {value_col} over {date_col}",
        )
        return cls.to_spec(fig)

    @classmethod
    def build_heatmap(cls, df: pd.DataFrame) -> dict[str, Any] | None:
        """Feature correlation heatmap for numeric columns."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if len(numeric_cols) < 2:
            return None

        corr = df[numeric_cols].corr()
        fig = go.Figure(
            data=go.Heatmap(
                z=corr.values,
                x=corr.columns.tolist(),
                y=corr.columns.tolist(),
                colorscale=[[0, "#3B82F6"], [0.5, "#18181B"], [1, "#10B981"]],
                zmin=-1,
                zmax=1,
                text=corr.round(2).values,
                texttemplate="%{text}",
            )
        )
        fig.update_layout(title="Feature Correlation Matrix")
        return cls.to_spec(fig)

    @classmethod
    def build_feature_importance(
        cls, feature_importances: dict[str, float], top_n: int = 12
    ) -> dict[str, Any]:
        """Horizontal bar chart showing relative feature influence."""
        items = list(feature_importances.items())[:top_n]
        # Invert order for bottom-up horizontal bar
        items.reverse()
        features = [x[0] for x in items]
        values = [x[1] for x in items]

        fig = go.Figure(
            go.Bar(
                x=values,
                y=features,
                orientation="h",
                marker={"color": "#10B981"},
            )
        )
        fig.update_layout(
            title="Feature Importance Ranking",
            xaxis={"title": "Relative Importance"},
            yaxis={"title": "Features"},
        )
        return cls.to_spec(fig)

    @classmethod
    def build_box(
        cls, df: pd.DataFrame, numeric_col: str, category_col: str | None = None
    ) -> dict[str, Any] | None:
        """Box plot for outlier detection and group quartile comparisons."""
        if numeric_col not in df.columns:
            return None

        sample_df = df.sample(min(len(df), 2000), random_state=42) if len(df) > 2000 else df
        fig = px.box(
            sample_df,
            y=numeric_col,
            x=category_col if category_col in df.columns else None,
            color=category_col if category_col in df.columns else None,
            color_discrete_sequence=["#10B981"] if not category_col else None,
            title=f"Quartile Spread: {numeric_col}",
        )
        return cls.to_spec(fig)
