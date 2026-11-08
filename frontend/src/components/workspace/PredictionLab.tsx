"use client";

import React, { useEffect, useState } from "react";
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
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  PredictionHistory,
  PredictDiagnoseResponse,
  PredictTaskType,
} from "@/lib/types";

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

  useEffect(() => {
    loadPredictionHistory();
  }, [fileId]);

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

  const loadPredictionHistory = async () => {
    try {
      const runs = await api.predict.history(fileId);
      setHistory(runs);
      if (runs.length > 0 && !activeRun) {
        setActiveRun(runs[0]);
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
    } catch (err: any) {
      setIsTraining(false);
      setErrorMessage(err.message || "Failed to launch training worker.");
    }
  };

  const leaderboard = activeRun?.leaderboard_json?.leaderboard || [];
  const testMetric = activeRun?.leaderboard_json?.test_metric || "Metric";
  const featureImportances = activeRun?.feature_importance_json || {};

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
                    const isBest = item.model === activeRun.best_model_name;
                    return (
                      <tr
                        key={item.model}
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
                        <td className="py-2 px-3 text-white flex items-center gap-2">
                          <span>{item.model}</span>
                          {isBest && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                              BEST
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-3 text-emerald-400">
                          {item.cv_mean.toFixed(4)}
                        </td>
                        <td className="py-2 px-3 text-zinc-400">
                          ±{item.cv_std.toFixed(4)}
                        </td>
                        <td className="py-2 px-3 text-zinc-500">
                          {item.train_time_sec ? `${item.train_time_sec.toFixed(2)}s` : "—"}
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
              {Object.entries(featureImportances)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 8)
                .map(([feat, score]) => (
                  <div key={feat} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="text-zinc-300 truncate max-w-[180px]">{feat}</span>
                      <span className="text-cyan-400">{(score * 100).toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-zinc-900 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-cyan-500 h-1.5 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(100, score * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
