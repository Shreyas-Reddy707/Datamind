"""
Prediction Agent for DataMind v4.0.
Coordinates ML tasks with the UniversalMLRunner.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, Optional, List
import pandas as pd
import streamlit as st

from datamind.tools.ml_runner import UniversalMLRunner
from datamind.tools.chart_builder import build_prediction_results, build_time_series_chart, build_distribution_chart
from datamind.tools.stats import compute_fast_stats, DatasetStats
from datamind.agent.diagnostic_agent import DiagnosticAgent

logger = logging.getLogger(__name__)

class PredictAgent:
    """Agent for ML prediction, clustering, and forecasting tasks."""

    def __init__(self, df: pd.DataFrame, stats: Optional[DatasetStats] = None):
        self.df = df
        self.stats = stats or compute_fast_stats(df)
        self.runner = UniversalMLRunner()

    def run_prediction_mission(self, target_col: Optional[str] = None, mode: str = "auto") -> Dict[str, Any]:
        """Validates and executes a predictive/ML mission."""
        
        # 1. Validation via Diagnostic Agent
        diagnostic = DiagnosticAgent(self.stats)
        diag_res = diagnostic.validate_for_prediction(self.df, target_col)
        
        if not diag_res["can_proceed"]:
            blocker_msg = "\n".join([f"- {b}" for b in diag_res["blockers"]])
            return {"success": False, "error": f"Mission Aborted. Blockers detected:\n{blocker_msg}"}

        # 2. Finalize target
        final_target = target_col or diag_res.get("suggested_target")
        
        # 3. Task Selection
        if mode == "auto":
            task = self.runner.auto_select_task(self.df, final_target)
        else:
            task = mode

        charts = []
        try:
            with st.spinner(f"Initiating {task.capitalize()} Mission..."):
                # 4. Preprocessing
                proc_data = self.runner.preprocess(self.df, final_target, task)
                
                # 5. Execution based on task
                if task == "classification":
                    res = self.runner.run_classification(
                        proc_data["X_train"], proc_data["X_test"], 
                        proc_data["y_train"], proc_data["y_test"], 
                        proc_data["feature_names"]
                    )
                    # Add Strategic Implication
                    accuracy_relativity = "high reliability" if res['test_accuracy'] > 0.8 else "moderate confidence" if res['test_accuracy'] > 0.6 else "exploratory utility"
                    narrative = f"### ✅ Classification Mission Complete\n\n"
                    narrative += f"- **Target Dimension**: `{final_target}`\n"
                    narrative += f"- **Best Model**: {res['best_model_name']}\n"
                    narrative += f"- **Test Accuracy**: {res['test_accuracy']:.1%}\n\n"
                    narrative += f"#### 💡 Strategic Implication\n"
                    narrative += f"The engine has detected discrete patterns in `{final_target}` with **{accuracy_relativity}**. "
                    narrative += "This model can be used to categorize future observations based on the current feature set."
                    # charts.append(build_prediction_results(res["y_test"], res["y_pred"], f"{final_target} Prediction"))

                elif task == "regression":
                    res = self.runner.run_regression(
                        proc_data["X_train"], proc_data["X_test"], 
                        proc_data["y_train"], proc_data["y_test"], 
                        proc_data["feature_names"]
                    )
                    # Add Strategic Implication
                    quality = "strong correlation" if res['test_r2'] > 0.7 else "identifiable trend" if res['test_r2'] > 0.4 else "weak signal"
                    narrative = f"### ✅ Regression Mission Complete\n\n"
                    narrative += f"- **Predicting**: `{final_target}`\n"
                    narrative += f"- **Best Model**: {res['best_model_name']}\n"
                    narrative += f"- **R² Score**: {res['test_r2']:.3f}\n\n"
                    narrative += f"#### 💡 Strategic Implication\n"
                    narrative += f"The dataset exhibits a **{quality}** regarding `{final_target}`. "
                    narrative += "While the model identifies the overall trajectory, local variance may still impact short-term accuracy."
                    # charts.append(build_prediction_results(res["y_test"], res["y_pred"], f"{final_target} Trend"))

                elif task == "clustering":
                    res = self.runner.run_clustering(self.df, proc_data["feature_names"])
                    narrative = f"### 🧩 Clustering Complete (k={res['optimal_k']})\n\n"
                    for i, d in res["cluster_descriptions"].items():
                        narrative += f"- **Cluster {i+1}**: {d['label']} (*{d['summary']}*)\n"

                elif task == "timeseries":
                    # Find date col
                    date_col = self.stats.column_types["datetime"][0]
                    res = self.runner.run_timeseries(self.df, date_col, final_target)
                    narrative = f"### 📈 Forecasting Complete\n\n- **Model**: {res['model_used']}\n- **Forecast Horizon**: 10 periods ahead.\n"

            return {
                "success": True,
                "response": narrative,
                "results": res,
                "figures": charts,
                "category": "simulation"
            }

        except Exception as e:
            logger.error(f"Prediction mission failed: {e}")
            return {"success": False, "error": f"Mission error: {str(e)}"}