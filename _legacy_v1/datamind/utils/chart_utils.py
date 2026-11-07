"""
Utilities to capture matplotlib / seaborn figures as base64 PNG strings.
"""

from __future__ import annotations

import base64
import io
from typing import Any

import matplotlib  # type: ignore[import-untyped]
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt  # type: ignore[import-untyped]


def figure_to_base64(fig: plt.Figure) -> str:
    """Convert a single matplotlib Figure to a base64-encoded PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    buf.close()
    return encoded


def figures_to_base64(figures: list[plt.Figure]) -> list[str]:
    """Convert a list of matplotlib Figures to base64 PNG strings."""
    results = []
    for fig in figures:
        try:
            results.append(figure_to_base64(fig))
        except Exception:
            pass  # skip broken figures
    return results


def capture_figures(namespace: dict[str, Any]) -> list[str]:
    """
    Scan an exec namespace for matplotlib Figure objects and convert them to base64.

    Also captures any figures registered with pyplot's figure manager.
    Closes all figures after capture to free memory.

    Args:
        namespace: The namespace dict from exec().

    Returns:
        List of base64 PNG strings.
    """
    collected_figures: list[plt.Figure] = []

    # 1. Collect figures from pyplot's figure manager
    fig_nums = plt.get_fignums()
    for num in fig_nums:
        fig = plt.figure(num)
        if fig not in collected_figures:
            collected_figures.append(fig)

    # 2. Scan namespace for any Figure objects not in the manager
    for val in namespace.values():
        if isinstance(val, plt.Figure) and val not in collected_figures:
            collected_figures.append(val)

    # 3. Convert to base64
    encoded = figures_to_base64(collected_figures)

    # 4. Close all figures to free memory
    plt.close("all")

    return encoded
