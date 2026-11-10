"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Activity,
  Play,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Trophy,
  BarChart2,
  Clock,
  Sliders,
  TrendingUp,
  TrendingDown,
  Lightbulb,
} from "lucide-react";
import { api } from "@/lib/api";
import { safeFixed, toFiniteNumber } from "@/lib/format";
import {
  LabChartType,
  PredictionHistory,
  PredictDiagnoseResponse,
  PredictSimulateResponse,
  PredictTaskType,
} from "@/lib/types";
import { EmbeddedPlotlyStudio } from "./EmbeddedPlotlyStudio";

interface PredictionLabProps {
  fileId: string;
  columns: string[];
}

export function PredictionLab({ fileId, columns }: PredictionLabProps) {
  const [selectedTarget, setSelectedTarget] = useState<string>("");
  const [selectedTaskType, setSelectedTaskType] = useState<PredictTaskType>(null);
  const [diagnostics, setDiagnostics] = useState<PredictDiagnoseResponse | null>(null);
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [activeRun, setActiveRun] = useState<PredictionHistory | null>(null);
  const [history, setHistory] = useState<PredictionHistory[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // What-If Simulation & Embedded Driver Chart State
  const [simulation, setSimulation] = useState<PredictSimulateResponse | null>(null);
  const [simInputs, setSimInputs] = useState<Record<string, string | number>>({});
  const [isSimulating, setIsSimulating] = useState(false);
  const simDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [driverChartType, setDriverChartType] = useState<LabChartType>("bar");
  const [driverXCol, setDriverXCol] = useState<string>("");
  const [driverYCol, setDriverYCol] = useState<string>("");
  const [driverColorCol, setDriverColorCol] = useState<string>("");
  const [driverChartSpec, setDriverChartSpec] = useState<Record<string, unknown> | null>(null);
  const [isDriverChartLoading, setIsDriverChartLoading] = useState(false);
  const [driverChartError, setDriverChartError] = useState<string | null>(null);

  useEffect(() => {
    loadPredictionHistory();

    const candidateTarget =
      columns.find((c) => {
        const cl = c.toLowerCase();
        return (
          cl === "is_canceled" ||
          cl === "canceled" ||
          cl === "churn" ||
          cl === "target" ||
          cl === "label" ||
          cl.startsWith("is_") ||
          cl.endsWith("_churn") ||
          cl === "adr"
        );
      }) || (columns.length > 0 ? columns[columns.length - 1] : "");

    const targetToDiagnose = selectedTarget || candidateTarget;
    if (targetToDiagnose) {
      setSelectedTarget(targetToDiagnose);
    }

    // Auto-run diagnosis on load
    api.predict
      .diagnose(fileId, { target_col: targetToDiagnose || null })
      .then((res) => {
        setDiagnostics(res);
        if (res.suggested_target && !targetToDiagnose) {
          setSelectedTarget(res.suggested_target);
        }
      })
      .catch((err) => {
        console.error("Auto-diagnosis failed:", err);
      });
  }, [fileId, columns]);

  // Polling active prediction run
  useEffect(() => {
    if (!activeRun || activeRun.status === "completed" || activeRun.status === "failed") {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const updated = await api.predict.get(activeRun.id);
        setActiveRun(updated);
        if (updated.status === "completed" || updated.status === "failed") {
          setIsTraining(false);
          await loadPredictionHistory();
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [activeRun]);

  const runSimulation = async (
    inputsOverride?: Record<string, string | number>,
    targetOverride?: string | null,
    predIdOverride?: string | null,
    initializeChart = false
  ) => {
    try {
      setIsSimulating(true);
      const res = await api.predict.simulate(fileId, {
        prediction_id: predIdOverride !== undefined ? predIdOverride : activeRun?.status === "completed" ? activeRun.id : null,
        target_col: targetOverride !== undefined ? targetOverride : activeRun?.target_column || selectedTarget || null,
        inputs: inputsOverride ?? simInputs,
      });
      setSimulation(res);
      if (!inputsOverride) {
        const initInputs: Record<string, string | number> = {};
        res.feature_controls.forEach((ctrl) => {
          initInputs[ctrl.name] = ctrl.current_value;
        });
        setSimInputs(initInputs);
      }
      if (initializeChart && res.top_drivers?.length > 0) {
        const d1 = res.top_drivers[0];
        const d2 = res.top_drivers[1] || "";
        const target = res.target_column;
        const cType: LabChartType = "bar";
        setDriverChartType(cType);
        setDriverXCol(d1);
        setDriverYCol(target);
        setDriverColorCol(d2 !== d1 && d2 !== target ? d2 : "");
        generateDriverChart(cType, d1, target, d2 !== d1 && d2 !== target ? d2 : "");
      }
    } catch (err) {
      console.error("Simulation failed:", err);
    } finally {
      setIsSimulating(false);
    }
  };

  const generateDriverChart = async (
    overrideType?: LabChartType,
    overrideX?: string,
    overrideY?: string,
    overrideColor?: string
  ) => {
    const cType = overrideType ?? driverChartType;
    const xVal = overrideX !== undefined ? overrideX : driverXCol;
    const yVal = overrideY !== undefined ? overrideY : driverYCol;
    const colorVal = overrideColor !== undefined ? overrideColor : driverColorCol;
    try {
      setIsDriverChartLoading(true);
      setDriverChartError(null);
      const res = await api.lab.visualize(
        fileId,
        cType,
        xVal || undefined,
        yVal || undefined,
        colorVal || undefined
      );
      setDriverChartSpec((res as any)?.plotly_spec || (res as any)?.spec || res);
    } catch (err: any) {
      setDriverChartError(err.message || "Failed to generate predictive driver chart.");
    } finally {
      setIsDriverChartLoading(false);
    }
  };

  // Refresh What-If Simulation & Embedded Driver Chart whenever active completed run or target changes
  useEffect(() => {
    if (!fileId || columns.length === 0) return;
    const targetToUse = activeRun?.target_column || selectedTarget || null;
    const predIdToUse = activeRun?.status === "completed" ? activeRun.id : null;
    runSimulation({}, targetToUse, predIdToUse, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileId, activeRun?.id, activeRun?.status, selectedTarget]);

  const handleControlChange = (featureName: string, value: string | number) => {
    const nextInputs = { ...simInputs, [featureName]: value };
    setSimInputs(nextInputs);
    if (simDebounceRef.current) {
      clearTimeout(simDebounceRef.current);
    }
    simDebounceRef.current = setTimeout(() => {
      runSimulation(nextInputs, undefined, undefined, false);
    }, 120);
  };

  const handleApplyPreset = (presetInputs: Record<string, string | number>) => {
    setSimInputs(presetInputs);
    runSimulation(presetInputs, undefined, undefined, false);
  };

  const loadPredictionHistory = async () => {
    try {
      const runs = await api.predict.history(fileId);
      setHistory(runs);
      if (runs.length > 0 && !activeRun) {
        const preferred =
          runs.find((r) => r.status === "completed") ||
          runs.find((r) => r.status === "running" || r.status === "queued") ||
          runs[0];
        setActiveRun(preferred);
      }
    } catch (err) {
      console.error("Failed to load prediction history:", err);
    }
  };

  const handleDiagnose = async () => {
    try {
      setIsDiagnosing(true);
      setErrorMessage(null);
      const res = await api.predict.diagnose(fileId, {
        target_col: selectedTarget || null,
      });
      setDiagnostics(res);
      if (!selectedTarget && res.suggested_target) {
        setSelectedTarget(res.suggested_target);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to diagnose dataset readiness.");
    } finally {
      setIsDiagnosing(false);
    }
  };

  const handleStartTraining = async () => {
    try {
      setIsTraining(true);
      setErrorMessage(null);
      const run = await api.predict.run(fileId, {
        target_col: selectedTarget || null,
        task_type: selectedTaskType,
      });
      setActiveRun(run);
      if (run.status === "completed" || run.status === "failed") {
        setIsTraining(false);
        await loadPredictionHistory();
      }
    } catch (err: any) {
      setIsTraining(false);
      setErrorMessage(err.message || "Failed to launch training worker.");
    }
  };

  const rawLbJson = activeRun?.leaderboard_json;
  const rawLeaderboard = Array.isArray(rawLbJson)
    ? rawLbJson
    : Array.isArray(rawLbJson?.leaderboard)
      ? rawLbJson.leaderboard
      : [];

  const leaderboard = rawLeaderboard.map((item) => {
    const modelName = item.model_name ?? item.model ?? "Model";
    const metricName = item.metric_name ?? item.metric ?? "score";
    const cvMean = toFiniteNumber(
      item.cv_mean ?? item.mean_cv_score ?? item.score ?? item.inertia,
      0
    );
    const cvStd = toFiniteNumber(
      item.cv_std ?? item.std_cv_score ?? item.std,
      0
    );
    const trainTime =
      item.train_time_sec !== undefined &&
      item.train_time_sec !== null &&
      Number.isFinite(Number(item.train_time_sec))
        ? Number(item.train_time_sec)
        : null;

    return {
      modelName,
      metricName,
      cvMean,
      cvStd,
      trainTime,
    };
  });

  const testMetric =
    (!Array.isArray(rawLbJson) && rawLbJson?.test_metric) ||
    leaderboard[0]?.metricName ||
    "Metric";

  const rawFi = activeRun?.feature_importance_json;
  const featureImportancesList: Array<{ feature: string; importance: number }> =
    Array.isArray(rawFi)
      ? rawFi
          .map((entry) => ({
            feature: String(entry.feature ?? entry.name ?? "Feature"),
            importance: toFiniteNumber(entry.importance ?? entry.score, 0),
          }))
          .filter((entry) => entry.feature.length > 0)
      : rawFi && typeof rawFi === "object"
        ? Object.entries(rawFi).map(([feature, score]) => ({
            feature,
            importance: toFiniteNumber(score, 0),
          }))
        : [];

  return (
    <div className="space-y-6">
      {/* Top Header & Task Formulation */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-400" />
              Automated Machine Learning &amp; Benchmarking
            </h3>
            <p className="text-xs text-zinc-400 font-mono mt-0.5">
              Taskiq asynchronous workers // Stratified cross-validation // Scikit-Learn
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleDiagnose}
              disabled={isDiagnosing || isTraining}
              className="px-3 py-1.5 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-xs font-mono text-zinc-200 transition-colors flex items-center gap-1.5"
            >
              {isDiagnosing ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-cyan-400" />
              ) : (
                <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
              )}
              <span>Diagnose Readiness</span>
            </button>

            <button
              onClick={handleStartTraining}
              disabled={isTraining || isDiagnosing}
              className="px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-black text-xs font-semibold font-mono transition-colors flex items-center gap-1.5 shadow-md shadow-emerald-500/10"
            >
              {isTraining ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-black" />
              ) : (
                <Play className="w-3.5 h-3.5 text-black fill-black" />
              )}
              <span>{isTraining ? "Training Models..." : "Train Models"}</span>
            </button>
          </div>
        </div>

        {/* Configuration Selectors */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-3 border-t border-zinc-800/80">
          <div>
            <label className="block text-[11px] font-mono uppercase text-zinc-400 mb-1.5">
              Target Column (Predictand)
            </label>
            <select
              value={selectedTarget}
              onChange={(e) => setSelectedTarget(e.target.value)}
              className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-zinc-200 font-mono focus:outline-none focus:border-emerald-500"
            >
              <option value="">[Auto-Detect Optimal Target]</option>
              {columns.map((col) => (
                <option key={col} value={col}>
                  {col}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-mono uppercase text-zinc-400 mb-1.5">
              Task Formulation
            </label>
            <select
              value={selectedTaskType || ""}
              onChange={(e) =>
                setSelectedTaskType(
                  (e.target.value as PredictTaskType) || null
                )
              }
              className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-zinc-200 font-mono focus:outline-none focus:border-emerald-500"
            >
              <option value="">[Auto-Infer Classification vs Regression]</option>
              <option value="classification">Classification (Discrete Classes)</option>
              <option value="regression">Regression (Continuous Values)</option>
              <option value="clustering">Unsupervised Clustering</option>
              <option value="timeseries">Time-Series Forecast</option>
            </select>
          </div>
        </div>

        {errorMessage && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 font-mono">
            {errorMessage}
          </div>
        )}

        {history.length > 0 && (
          <div className="pt-3 border-t border-zinc-800/80 flex flex-wrap items-center gap-2 font-mono text-[11px]">
            <span className="text-zinc-500 uppercase tracking-wider flex items-center gap-1 mr-1">
              <Clock className="w-3 h-3" /> Runs:
            </span>
            {history.slice(0, 5).map((run) => {
              const isSelected = activeRun?.id === run.id;
              return (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => setActiveRun(run)}
                  className={`px-2.5 py-1 rounded-md border transition-colors flex items-center gap-1.5 ${
                    isSelected
                      ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
                      : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700"
                  }`}
                >
                  <span>{run.target_column || "clustering"}</span>
                  <span className="text-[10px] opacity-75">({run.status})</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Diagnostics Readiness Panel */}
      {diagnostics && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-medium text-zinc-300 flex items-center gap-2">
              {diagnostics.can_proceed ? (
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
              ) : (
                <span className="w-2 h-2 rounded-full bg-rose-400" />
              )}
              Readiness Status:{" "}
              {diagnostics.can_proceed ? (
                <span className="text-emerald-400">Ready for Training</span>
              ) : (
                <span className="text-rose-400">Blockers Detected</span>
              )}
            </span>

            {diagnostics.suggested_target && (
              <span className="text-xs font-mono text-zinc-400">
                Recommended Target:{" "}
                <span className="text-cyan-400 font-semibold">
                  {diagnostics.suggested_target}
                </span>
              </span>
            )}
          </div>

          {diagnostics.blockers.length > 0 && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 space-y-1">
              <span className="text-[11px] font-mono font-bold text-rose-400 uppercase">
                Critical Blockers:
              </span>
              <ul className="list-disc list-inside text-xs text-rose-300 space-y-0.5 font-mono">
                {diagnostics.blockers.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            </div>
          )}

          {diagnostics.warnings.length > 0 && (
            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 space-y-1">
              <span className="text-[11px] font-mono font-bold text-amber-400 uppercase">
                Warnings / Advisory:
              </span>
              <ul className="list-disc list-inside text-xs text-amber-300 space-y-0.5 font-mono">
                {diagnostics.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Target Leakage Protection Alert / Badge */}
      {((activeRun?.diagnostics_json as any)?.dropped_leakage_columns?.length > 0 ||
        (diagnostics?.dropped_leakage_columns && diagnostics.dropped_leakage_columns.length > 0)) && (
        <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1 font-mono text-xs">
            <div className="flex items-center gap-2">
              <span className="font-bold uppercase text-amber-400">Target Leakage Protection Active</span>
              <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-semibold border border-amber-500/30">
                {((activeRun?.diagnostics_json as any)?.dropped_leakage_columns || diagnostics?.dropped_leakage_columns || []).length} Column(s) Quarantined
              </span>
            </div>
            <p className="text-zinc-300 text-[11px] leading-relaxed">
              Autonomous data integrity quarantined target leakage columns with &gt;0.95 correlation / direct status mirror:{" "}
              <span className="text-amber-300 font-semibold">
                {((activeRun?.diagnostics_json as any)?.dropped_leakage_columns || diagnostics?.dropped_leakage_columns || []).join(", ")}
              </span>.
            </p>
          </div>
        </div>
      )}

      {/* Active Run Status Badge */}
      {activeRun && (activeRun.status === "queued" || activeRun.status === "running") && (
        <div className="p-4 rounded-xl border border-cyan-500/30 bg-cyan-500/5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <RefreshCw className="w-5 h-5 text-cyan-400 animate-spin" />
            <div>
              <p className="text-xs font-semibold text-white font-mono uppercase">
                Worker Job: {activeRun.status}...
              </p>
              <p className="text-[11px] text-zinc-400 font-mono">
                Optimizing hyperparameters across 5 cross-validation folds
              </p>
            </div>
          </div>
          <span className="text-xs font-mono text-cyan-400 bg-cyan-500/10 px-2.5 py-1 rounded border border-cyan-500/20">
            Task: {activeRun.task_type}
          </span>
        </div>
      )}

      {/* Failed Run Status Block */}
      {activeRun && activeRun.status === "failed" && (
        <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/5 flex items-start gap-3">
          <XCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="space-y-1 font-mono">
            <p className="text-xs font-semibold text-rose-300 uppercase">
              Model Training Failed
            </p>
            <p className="text-xs text-rose-200">
              {(activeRun as any).error_message ||
                (activeRun as any).diagnostics_json?.error ||
                "The AutoML worker encountered an unexpected failure during cross-validation training."}
            </p>
          </div>
        </div>
      )}

      {/* Results: Leaderboard & Feature Importance */}
      {activeRun && activeRun.status === "completed" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Leaderboard Table */}
          <div className="lg:col-span-7 rounded-xl border border-zinc-800 bg-zinc-950/70 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-mono uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                <Trophy className="w-4 h-4 text-amber-400" />
                Model Benchmark Leaderboard
              </h4>
              <span className="text-[11px] font-mono text-zinc-400">
                Primary Metric: <span className="text-emerald-400">{testMetric}</span>
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-500">
                    <th className="py-2 px-3">Rank</th>
                    <th className="py-2 px-3">Model Architecture</th>
                    <th className="py-2 px-3">CV Score</th>
                    <th className="py-2 px-3">Std Dev</th>
                    <th className="py-2 px-3">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60">
                  {leaderboard.map((item, index) => {
                    const isBest = item.modelName === activeRun.best_model_name;
                    return (
                      <tr
                        key={`${item.modelName}-${index}`}
                        className={isBest ? "bg-emerald-500/5 font-semibold" : "hover:bg-zinc-900/40"}
                      >
                        <td className="py-2 px-3 text-zinc-400">
                          {isBest ? (
                            <span className="inline-flex items-center gap-1 text-emerald-400 font-bold">
                              #1
                            </span>
                          ) : (
                            `#${index + 1}`
                          )}
                        </td>
                        <td className="py-2 px-3 text-white">
                          <div className="flex items-center gap-2">
                            <span>{item.modelName}</span>
                            {isBest && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                                BEST
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-2 px-3 text-emerald-400">
                          {safeFixed(item.cvMean, 4)}
                        </td>
                        <td className="py-2 px-3 text-zinc-400">
                          ±{safeFixed(item.cvStd, 4)}
                        </td>
                        <td className="py-2 px-3 text-zinc-500">
                          {item.trainTime !== null ? `${safeFixed(item.trainTime, 2)}s` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Feature Importance */}
          <div className="lg:col-span-5 rounded-xl border border-zinc-800 bg-zinc-950/70 p-5 space-y-4">
            <h4 className="text-xs font-mono uppercase tracking-wider text-zinc-300 flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-cyan-400" />
              Feature Importance Weights
            </h4>

            <div className="space-y-3 font-mono">
              {featureImportancesList.length > 0 ? (
                featureImportancesList
                  .slice()
                  .sort((a, b) => b.importance - a.importance)
                  .slice(0, 8)
                  .map(({ feature, importance }) => (
                    <div key={feature} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-zinc-300 truncate max-w-[180px]">{feature}</span>
                        <span className="text-cyan-400">{safeFixed(importance * 100, 1)}%</span>
                      </div>
                      <div className="w-full bg-zinc-900 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-cyan-500 h-1.5 rounded-full transition-all duration-500"
                          style={{ width: `${Math.max(0, Math.min(100, importance * 100))}%` }}
                        />
                      </div>
                    </div>
                  ))
              ) : (
                <p className="text-xs text-zinc-500">
                  No feature importance weights available for this run.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Executive Prediction Summary Banner */}
      {simulation && (
        <div className="rounded-xl border border-emerald-500/30 bg-gradient-to-br from-emerald-500/10 via-zinc-950/90 to-zinc-950 p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <h4 className="text-xs font-mono uppercase tracking-wider text-emerald-400 font-bold flex items-center gap-2">
              <Lightbulb className="w-4 h-4 text-emerald-400" />
              Executive Prediction Summary // What Happens &amp; Why
            </h4>
            <span className="text-[11px] font-mono text-zinc-400">
              Target: <span className="text-white font-semibold">{simulation.target_column}</span> ({simulation.task_type})
            </span>
          </div>

          <p className="text-xs font-mono text-zinc-200 leading-relaxed bg-zinc-900/60 p-3 rounded-lg border border-zinc-800">
            {simulation.executive_summary.what_is_predicted.replace(/\*\*/g, "")}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
            <div className="space-y-2 p-3.5 rounded-lg bg-zinc-900/50 border border-zinc-800/80">
              <span className="text-[11px] uppercase tracking-wider text-cyan-400 font-semibold block">
                Primary Drivers (Why It Happens)
              </span>
              <ul className="space-y-1.5 text-zinc-300 text-[11px] leading-relaxed">
                {simulation.executive_summary.primary_drivers.map((drv, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-cyan-400 font-bold mt-0.5">{idx + 1}.</span>
                    <span>{drv.replace(/\*\*|`/g, "")}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="space-y-2 p-3.5 rounded-lg bg-zinc-900/50 border border-zinc-800/80">
              <span className="text-[11px] uppercase tracking-wider text-emerald-400 font-semibold block">
                Actionable Levers (Options to Shift Outcome)
              </span>
              <ul className="space-y-1.5 text-zinc-300 text-[11px] leading-relaxed">
                {simulation.executive_summary.actionable_levers.map((lev, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-emerald-400 font-bold mt-0.5">&rarr;</span>
                    <span>{lev.replace(/`/g, "")}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Interactive "What-If" Scenario Outcome Simulator */}
      {simulation && simulation.feature_controls.length > 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-5 space-y-5">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-zinc-800/80 pb-4">
            <div>
              <h4 className="text-xs font-mono uppercase tracking-wider text-zinc-200 font-bold flex items-center gap-2">
                <Sliders className="w-4 h-4 text-emerald-400" />
                Interactive &quot;What-If&quot; Outcome Simulator
              </h4>
              <p className="text-[11px] font-mono text-zinc-400 mt-0.5">
                Adjust top weighted drivers below to simulate live predictions and factor attribution
              </p>
            </div>

            {/* Scenario Presets */}
            <div className="flex flex-wrap items-center gap-1.5">
              {simulation.presets.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => handleApplyPreset(preset.inputs)}
                  className="px-2.5 py-1 rounded-md border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 hover:border-emerald-500/40 text-[10px] font-mono text-zinc-300 transition-colors"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Left: Interactive Feature Sliders & Dropdowns */}
            <div className="lg:col-span-7 space-y-4">
              {simulation.feature_controls.map((ctrl) => {
                const val = simInputs[ctrl.name] ?? ctrl.current_value;
                return (
                  <div
                    key={ctrl.name}
                    className="p-3.5 rounded-lg border border-zinc-800/90 bg-zinc-900/50 space-y-2 font-mono"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="text-white font-semibold">{ctrl.name}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                          Weight {safeFixed(ctrl.weight * 100, 1)}%
                        </span>
                      </div>
                      <span className="text-emerald-400 font-bold">{String(val)}</span>
                    </div>

                    {ctrl.type === "numeric" ? (
                      <div className="space-y-1">
                        <input
                          type="range"
                          min={ctrl.min ?? 0}
                          max={ctrl.max ?? 100}
                          step={ctrl.step ?? 1}
                          value={Number(val)}
                          onChange={(e) => handleControlChange(ctrl.name, Number(e.target.value))}
                          className="w-full accent-emerald-500 cursor-pointer"
                        />
                        <div className="flex justify-between text-[10px] text-zinc-500">
                          <span>Min: {ctrl.min}</span>
                          <span>{ctrl.summary_hint}</span>
                          <span>Max: {ctrl.max}</span>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-1">
                        <select
                          value={String(val)}
                          onChange={(e) => handleControlChange(ctrl.name, e.target.value)}
                          className="w-full px-2.5 py-1.5 bg-zinc-950 border border-zinc-800 rounded-md text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
                        >
                          {(ctrl.options || []).map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                        {ctrl.summary_hint && (
                          <span className="text-[10px] text-zinc-500 block">
                            {ctrl.summary_hint}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Right: Outcome Gauge & Factor Contribution Breakdown */}
            <div className="lg:col-span-5 space-y-4">
              {/* Outcome Readout Card */}
              <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/70 space-y-3 font-mono">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] uppercase text-zinc-400">
                    Simulated Outcome ({simulation.target_column})
                  </span>
                  {isSimulating && (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                  )}
                </div>

                <div className="flex items-baseline justify-between gap-2">
                  <div>
                    <div className="text-3xl font-bold text-white">
                      {safeFixed(simulation.simulated_prediction.scalar, 1)}
                      <span className="text-base text-emerald-400 ml-0.5">{simulation.unit}</span>
                    </div>
                    {simulation.task_type === "classification" &&
                      simulation.simulated_prediction.predicted_class !== undefined && (
                        <span className="text-[11px] text-zinc-400 block mt-0.5">
                          Predicted Class:{" "}
                          <span className="text-cyan-400 font-semibold">
                            {simulation.simulated_prediction.predicted_class}
                          </span>{" "}
                          ({safeFixed(simulation.simulated_prediction.probability_pct, 1)}% confidence)
                        </span>
                      )}
                    {simulation.task_type !== "classification" &&
                      simulation.simulated_prediction.confidence_band !== undefined && (
                        <span className="text-[11px] text-zinc-400 block mt-0.5">
                          Confidence Band: ±{safeFixed(simulation.simulated_prediction.confidence_band, 2)}
                        </span>
                      )}
                  </div>

                  <div
                    className={`px-2.5 py-1 rounded-lg border text-xs font-semibold flex items-center gap-1 ${
                      simulation.delta > 0.05
                        ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
                        : simulation.delta < -0.05
                          ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                          : "bg-zinc-800 border-zinc-700 text-zinc-300"
                    }`}
                  >
                    {simulation.delta > 0.05 ? (
                      <TrendingUp className="w-3.5 h-3.5" />
                    ) : simulation.delta < -0.05 ? (
                      <TrendingDown className="w-3.5 h-3.5" />
                    ) : null}
                    <span>
                      {simulation.delta >= 0 ? "+" : ""}
                      {safeFixed(simulation.delta, 1)}
                      {simulation.unit} vs Baseline
                    </span>
                  </div>
                </div>

                <div className="w-full bg-zinc-950 rounded-full h-2 overflow-hidden border border-zinc-800">
                  <div
                    className="bg-emerald-500 h-2 transition-all duration-300"
                    style={{
                      width: `${
                        simulation.task_type === "classification"
                          ? Math.max(2, Math.min(100, simulation.simulated_prediction.scalar))
                          : 60
                      }%`,
                    }}
                  />
                </div>
              </div>

              {/* Factor Contribution Breakdown */}
              <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/70 space-y-3 font-mono">
                <span className="text-[11px] uppercase text-zinc-300 font-semibold block">
                  Factor Contribution Breakdown
                </span>
                <div className="space-y-2.5">
                  {simulation.factor_contributions.map((fc) => {
                    const maxAbs = Math.max(
                      1,
                      ...simulation.factor_contributions.map((x) => Math.abs(x.delta))
                    );
                    const pctWidth = Math.min(100, (Math.abs(fc.delta) / maxAbs) * 100);
                    return (
                      <div key={fc.feature} className="space-y-1 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="text-zinc-300 truncate max-w-[170px]">
                            {fc.feature} = {String(fc.current_value)}
                          </span>
                          <span
                            className={
                              fc.delta > 0.05
                                ? "text-amber-400"
                                : fc.delta < -0.05
                                  ? "text-emerald-400"
                                  : "text-zinc-500"
                            }
                          >
                            {fc.delta >= 0 ? "+" : ""}
                            {safeFixed(fc.delta, 2)}
                            {simulation.unit}
                          </span>
                        </div>
                        <div className="w-full bg-zinc-950 rounded-full h-1.5 overflow-hidden">
                          <div
                            className={`h-1.5 rounded-full transition-all duration-300 ${
                              fc.delta > 0.05
                                ? "bg-amber-500"
                                : fc.delta < -0.05
                                  ? "bg-emerald-500"
                                  : "bg-zinc-600"
                            }`}
                            style={{ width: `${Math.max(4, pctWidth)}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Embedded Predictive Outcome & Driver Impact Plotly Studio */}
      <EmbeddedPlotlyStudio
        title="Predictive Outcome & Top Driver Impact Studio (2D Vector & 3D WebGL)"
        columns={columns}
        chartType={driverChartType}
        xCol={driverXCol}
        yCol={driverYCol}
        colorCol={driverColorCol}
        chartSpec={driverChartSpec}
        isLoading={isDriverChartLoading}
        error={driverChartError}
        xLabel="Driver Feature (X)"
        yLabel="Target Outcome (Y)"
        onChangeChartType={setDriverChartType}
        onChangeXCol={setDriverXCol}
        onChangeYCol={setDriverYCol}
        onChangeColorCol={setDriverColorCol}
        onGenerate={() => generateDriverChart()}
      />
    </div>
  );
}

