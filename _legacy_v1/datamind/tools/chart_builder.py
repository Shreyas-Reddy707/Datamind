"""
Chart builder tools using Plotly.
Aligns with Phase 4 requirements.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any, Union

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.graph_objects import Figure

logger = logging.getLogger(__name__)

# Premium Chart Theme
CHART_THEME = {
    "plot_bgcolor": "rgba(0,0,0,0)",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "font": {"color": "#E0E0E0", "family": "Inter, system-ui, sans-serif"},
    "xaxis": {"gridcolor": "rgba(255,255,255,0.05)", "zerolinecolor": "rgba(255,255,255,0.1)"},
    "yaxis": {"gridcolor": "rgba(255,255,255,0.05)", "zerolinecolor": "rgba(255,255,255,0.1)"},
}

def build_distribution_chart(df: pd.DataFrame, column: str) -> Optional[Figure]:
    """Builds histogram or bar chart based on column type."""
    if column not in df.columns:
        return None

    if pd.api.types.is_numeric_dtype(df[column]):
        fig = px.histogram(
            df, x=column, 
            nbins=30, 
            color_discrete_sequence=["#6366F1"],
            title=f"Distribution: {column}"
        )
    else:
        counts = df[column].value_counts().head(15)
        fig = px.bar(
            x=counts.index, y=counts.values,
            color_discrete_sequence=["#10B981"],
            title=f"Distribution: {column}"
        )
    
    fig.update_layout(**CHART_THEME)
    return fig

def build_correlation_heatmap(df: pd.DataFrame) -> Optional[Figure]:
    """Builds correlation heatmap for numeric columns."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(numeric_cols) < 2:
        return None
        
    corr = df[numeric_cols].corr()
    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns,
        y=corr.columns,
        colorscale="RdBu",
        zmin=-1, zmax=1,
        text=corr.round(2).values,
        texttemplate="%{text}"
    ))
    
    fig.update_layout(
        title="Feature Correlation Heatmap",
        **CHART_THEME
    )
    return fig

def build_null_map(df: pd.DataFrame) -> Figure:
    """Builds a bar chart of missing values."""
    null_pct = df.isnull().mean() * 100
    null_pct = null_pct[null_pct > 0].sort_values(ascending=False)
    
    if null_pct.empty:
        # Show 'No Missing Values' message if everything is clean
        fig = go.Figure()
        fig.add_annotation(text="No Missing Values Detected", showarrow=False, font={"size": 20})
        fig.update_layout(title="Missing Values", **CHART_THEME)
        return fig

    fig = px.bar(
        x=null_pct.index, y=null_pct.values,
        labels={"x": "Column", "y": "Null %"},
        title="Missing Values by Column (%)",
        color=null_pct.values,
        color_continuous_scale="Reds"
    )
    fig.update_layout(**CHART_THEME)
    return fig

def build_prediction_results(y_true: Union[List, np.ndarray], y_pred: Union[List, np.ndarray], title: str = "Actual vs Predicted") -> Figure:
    """Builds scatter plot of actual vs predicted values."""
    fig = go.Figure()
    
    # Scatter
    fig.add_trace(go.Scatter(
        x=y_true, y=y_pred,
        mode='markers',
        marker=dict(color='#6366F1', opacity=0.6),
        name='Predictions'
    ))
    
    # Perfect line
    min_val = min(min(y_true), min(y_pred))
    max_val = max(max(y_true), max(y_pred))
    fig.add_trace(go.Scatter(
        x=[min_val, max_val], y=[min_val, max_val],
        mode='lines',
        line=dict(color='#10B981', dash='dash'),
        name='Perfect Match'
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Actual Values",
        yaxis_title="Predicted Values",
        **CHART_THEME
    )
    return fig

def build_residual_plot(y_true: Union[List, np.ndarray], y_pred: Union[List, np.ndarray]) -> Figure:
    """Builds residual plot."""
    residuals = np.array(y_true) - np.array(y_pred)
    fig = px.scatter(
        x=y_pred, y=residuals,
        labels={"x": "Predicted", "y": "Residuals"},
        title="Residual Plot",
        color_discrete_sequence=["#F59E0B"]
    )
    fig.add_hline(y=0, line_dash="dash", line_color="white")
    fig.update_layout(**CHART_THEME)
    return fig

def build_time_series_chart(df: pd.DataFrame, date_col: str, value_col: str) -> Optional[Figure]:
    """Builds a standard time-series line chart for a dataframe."""
    if date_col not in df.columns or value_col not in df.columns:
        return None
    fig = px.line(
        df.sort_values(date_col), 
        x=date_col, y=value_col,
        title=f"Trend: {value_col} over {date_col}",
        color_discrete_sequence=["#6366F1"]
    )
    fig.update_layout(**CHART_THEME)
    return fig

def build_forecast(history_dates: List, history_values: List, forecast_dates: List, forecast_values: List, lower_bound: List = None, upper_bound: List = None) -> Figure:
    """Builds time-series forecast chart with confidence bands."""
    fig = go.Figure()
    
    # History
    fig.add_trace(go.Scatter(
        x=history_dates, y=history_values,
        mode='lines', name='Historical',
        line=dict(color='#6366F1')
    ))
    
    # Confidence Band
    if lower_bound is not None and upper_bound is not None:
        fig.add_trace(go.Scatter(
            x=list(forecast_dates) + list(forecast_dates)[::-1],
            y=list(upper_bound) + list(lower_bound)[::-1],
            fill='toself',
            fillcolor='rgba(16, 185, 129, 0.2)',
            line=dict(color='rgba(255,255,255,0)'),
            hoverinfo="skip",
            showlegend=True,
            name='95% Confidence'
        ))
        
    # Forecast
    fig.add_trace(go.Scatter(
        x=forecast_dates, y=forecast_values,
        mode='lines', name='Forecast',
        line=dict(color='#10B981', width=3)
    ))
    
    fig.update_layout(
        title="Time Series Forecasting",
        **CHART_THEME
    )
    return fig
