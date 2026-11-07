"""Utility modules for DataMind."""

from datamind.utils.data_utils import load_csv, validate_csv, profile_dataframe, schema_summary
from datamind.utils.chart_utils import figures_to_base64, capture_figures

try:
    from datamind.utils.interactive_charts import auto_visualize, PLOTLY_AVAILABLE
except ImportError:
    auto_visualize = None
    PLOTLY_AVAILABLE = False

__all__ = [
    "load_csv",
    "validate_csv",
    "profile_dataframe",
    "schema_summary",
    "figures_to_base64",
    "capture_figures",
    "auto_visualize",
    "PLOTLY_AVAILABLE",
]
