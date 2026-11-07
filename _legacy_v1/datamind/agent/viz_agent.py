"""
Visualization Agent for DataMind v4.0
Delegates chart generation to tools/chart_builder.py.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from plotly.graph_objects import Figure

from datamind.tools.chart_builder import (
    build_distribution_chart,
    build_correlation_heatmap,
    build_null_map,
    build_time_series_chart,
    build_prediction_results
)
from datamind.tools.stats import compute_fast_stats, DatasetStats
from datamind.memory.session import set_pre_generated_chart

logger = logging.getLogger(__name__)

class VizAgent:
    """Agent for generating Plotly visualizations via tools/chart_builder."""

    def __init__(self, df: pd.DataFrame, stats: Optional[DatasetStats] = None):
        self.df = df
        self.stats = stats or compute_fast_stats(df)

    def generate_and_cache_top_charts(self):
        """Pre-generate the 3 most useful charts for the cache."""
        # 1. Distribution of top numeric column
        if self.stats.column_types["numeric"]:
            top_col = self.stats.top_columns[0]
            fig = build_distribution_chart(self.df, top_col)
            set_pre_generated_chart(f"dist_{top_col}", fig)

        # 2. Correlation Heatmap
        if len(self.stats.column_types["numeric"]) >= 2:
            fig = build_correlation_heatmap(self.df)
            set_pre_generated_chart("corr_heatmap", fig)

        # 3. Null Map
        fig = build_null_map(self.df)
        set_pre_generated_chart("null_map", fig)

    def handle_request(self, chart_type: str, **kwargs) -> Optional[Figure]:
        """Route specific chart requests to builders."""
        if chart_type == "distribution":
            return build_distribution_chart(self.df, kwargs.get("column"))
        elif chart_type == "correlation":
            return build_correlation_heatmap(self.df)
        elif chart_type == "time_series":
            return build_time_series_chart(self.df, kwargs.get("date_col"), kwargs.get("value_col"))
        elif chart_type == "missing":
            return build_null_map(self.df)
        return None