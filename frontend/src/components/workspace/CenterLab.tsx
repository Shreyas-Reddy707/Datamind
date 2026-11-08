"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Download,
  FileCode,
  FileText,
  Play,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Table as TableIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  LabChartType,
  LabOverviewResponse,
} from "@/lib/types";
import { QualityGauge3D } from "@/components/spatial/QualityGauge3D";
import { PlotlyCanvas } from "./PlotlyCanvas";
import { PredictionLab } from "./PredictionLab";
import { useWorkspaceStore, LabTab } from "@/store/useWorkspaceStore";

interface CenterLabProps {
  overview: LabOverviewResponse | null;
  fileId: string;
}

export function CenterLab({ overview, fileId }: CenterLabProps) {
  const {
    activeLabTab,
    setActiveLabTab,
    injectedArtifact,
    selectedJoinFileIds,
  } = useWorkspaceStore();

  // Visualization state
  const [selectedChartType, setSelectedChartType] = useState<LabChartType>("distribution");
  const [xCol, setXCol] = useState<string>("");
  const [yCol, setYCol] = useState<string>("");
  const [colorCol, setColorCol] = useState<string>("");
  const [chartSpec, setChartSpec] = useState<Record<string, unknown> | null>(null);
  const [isChartLoading, setIsChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);

  // SQL State
  const [sqlQuery, setSqlQuery] = useState<string>("SELECT * FROM dataset LIMIT 20;");
  const [sqlResults, setSqlResults] = useState<{
    columns: string[];
    rows: unknown[][];
    row_count: number;
  } | null>(null);
  const [sqlLatencyMs, setSqlLatencyMs] = useState<number | null>(null);
  const [isSqlExecuting, setIsSqlExecuting] = useState(false);
  const [sqlError, setSqlError] = useState<string | null>(null);

  // Forensic State
  const [forensicReport, setForensicReport] = useState<{
    findings: Array<Record<string, unknown>>;
    report: string;
  } | null>(null);
  const [isForensicLoading, setIsForensicLoading] = useState(false);

  // Preview data state
  const [previewData, setPreviewData] = useState<{
    columns: string[];
    data: Record<string, unknown>[];
  } | null>(null);

  // Columns list
  const columns = overview ? Object.keys(overview.schema.columns) : [];

  // Initialize defaults
  useEffect(() => {
    if (columns.length > 0 && !xCol) {
      setXCol(columns[0]);
      if (columns.length > 1) {
        setYCol(columns[1]);
      }
    }
  }, [columns]);

  // Handle injected artifact
  useEffect(() => {
    if (injectedArtifact && injectedArtifact.type === "chart") {
      setChartSpec(injectedArtifact.data as Record<string, unknown>);
    }
  }, [injectedArtifact]);

  // Load preview data on mount
  useEffect(() => {
    api.lab.preview(fileId, 25).then(setPreviewData).catch(console.error);
  }, [fileId]);

  // Load forensics when tab clicked
  useEffect(() => {
    if (activeLabTab === "forensic" && !forensicReport && !isForensicLoading) {
      loadForensicData();
    }
  }, [activeLabTab]);

  const loadForensicData = async () => {
    try {
      setIsForensicLoading(true);
      const res = await api.lab.forensic(fileId);
      setForensicReport(res);
    } catch (err) {
      console.error("Forensic analysis failed:", err);
    } finally {
      setIsForensicLoading(false);
    }
  };

  const handleGenerateChart = async () => {
    try {
      setIsChartLoading(true);
      setChartError(null);
      const res = await api.lab.visualize(
        fileId,
        selectedChartType,
        xCol || undefined,
        yCol || undefined,
        colorCol || undefined
      );
      setChartSpec(res.plotly_spec);
    } catch (err: any) {
      console.error("Chart generation failed:", err);
      setChartError(err.message || "Failed to generate chart visualization.");
    } finally {
      setIsChartLoading(false);
    }
  };

  const handleExecuteSql = async () => {
    try {
      setIsSqlExecuting(true);
      setSqlError(null);
      const startTime = performance.now();
      const res = await api.lab.query(fileId, sqlQuery, selectedJoinFileIds);
      const endTime = performance.now();
      setSqlLatencyMs(Math.round(endTime - startTime));
      setSqlResults(res);
    } catch (err: any) {
      setSqlError(err.message || "SQL execution failed.");
    } finally {
      setIsSqlExecuting(false);
    }
  };

  const handlePrintExport = () => {
    window.print();
  };

  const tabs: Array<{ id: LabTab; label: string; icon: any }> = [
    { id: "overview", label: "Overview & Health", icon: TableIcon },
    { id: "forensic", label: "Forensic Diagnostics", icon: ShieldAlert },
    { id: "viz", label: "Plotly Studio", icon: BarChart3 },
    { id: "predict", label: "AutoML Lab", icon: Activity },
    { id: "sql", label: "DuckDB SQL", icon: FileCode },
  ];

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#09090B]">
      {/* Tab Navigation & Export Bar */}
      <div className="h-12 border-b border-zinc-800/80 px-6 flex items-center justify-between shrink-0 bg-zinc-950/40">
        <div className="flex items-center gap-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeLabTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveLabTab(tab.id)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono transition-all ${
                  isActive
                    ? "bg-zinc-800 text-white font-semibold border border-zinc-700 shadow-sm"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
                }`}
              >
                <Icon
                  className={`w-3.5 h-3.5 ${
                    isActive ? "text-emerald-400" : "text-zinc-500"
                  }`}
                />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        <button
          onClick={handlePrintExport}
          className="flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-mono text-zinc-400 hover:text-white border border-zinc-800 hover:border-zinc-700 transition-colors"
          title="Export current analytical view as PDF or print briefing"
        >
          <Download className="w-3.5 h-3.5 text-emerald-400" />
          <span>Export Briefing</span>
        </button>
      </div>

      {/* Main Tab View Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* TAB 1: OVERVIEW & HEALTH */}
        {activeLabTab === "overview" && (
          <div className="space-y-6">
            {/* Top Row: 3D Gauge & Summary */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
              <div className="lg:col-span-4">
                <QualityGauge3D
                  score={overview?.profile?.health_score ?? null}
                  rowCount={overview?.row_count}
                  colCount={overview?.column_count}
                />
              </div>

              <div className="lg:col-span-8 rounded-xl border border-zinc-800 bg-zinc-950/70 p-5 flex flex-col justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-white font-mono flex items-center gap-2">
                    <FileText className="w-4 h-4 text-emerald-400" />
                    Dataset Structural Profile
                  </h3>
                  <p className="text-xs text-zinc-400 font-mono mt-1">
                    Parquet Vectorized Instance // Mounted in DuckDB Engine
                  </p>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6">
                    <div className="p-3 bg-zinc-900/60 rounded-lg border border-zinc-800">
                      <span className="text-[10px] font-mono text-zinc-500 uppercase block">
                        Numeric Features
                      </span>
                      <span className="text-lg font-mono font-bold text-cyan-400">
                        {overview?.profile?.numeric_columns?.length ?? 0}
                      </span>
                    </div>

                    <div className="p-3 bg-zinc-900/60 rounded-lg border border-zinc-800">
                      <span className="text-[10px] font-mono text-zinc-500 uppercase block">
                        Categorical Features
                      </span>
                      <span className="text-lg font-mono font-bold text-emerald-400">
                        {overview?.profile?.categorical_columns?.length ?? 0}
                      </span>
                    </div>

                    <div className="p-3 bg-zinc-900/60 rounded-lg border border-zinc-800">
                      <span className="text-[10px] font-mono text-zinc-500 uppercase block">
                        Ref Deduplication
                      </span>
                      <span className="text-lg font-mono font-bold text-amber-400">
                        {overview?.ref_count ?? 1}x
                      </span>
                    </div>

                    <div className="p-3 bg-zinc-900/60 rounded-lg border border-zinc-800">
                      <span className="text-[10px] font-mono text-zinc-500 uppercase block">
                        DuckDB Threads
                      </span>
                      <span className="text-lg font-mono font-bold text-zinc-200">
                        2 (512MB RAM)
                      </span>
                    </div>
                  </div>
                </div>

                {overview?.profile?.cleaning_recommendations &&
                  overview.profile.cleaning_recommendations.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-zinc-800/80">
                      <span className="text-xs font-mono font-semibold text-zinc-300 block mb-2">
                        Automated Cleansing Recommendations:
                      </span>
                      <div className="space-y-1.5 font-mono text-xs">
                        {overview.profile.cleaning_recommendations.slice(0, 3).map((rec, i) => (
                          <div
                            key={i}
                            className="p-2 rounded bg-zinc-900/40 border border-zinc-800/80 flex items-center justify-between text-zinc-300"
                          >
                            <span>
                              <span className="text-emerald-400 font-semibold">{rec.column}:</span>{" "}
                              {rec.issue}
                            </span>
                            <span className="text-[11px] text-zinc-400">{rec.remediation}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
              </div>
            </div>

            {/* Preview Data Table */}
            {previewData && (
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-mono uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                    <TableIcon className="w-4 h-4 text-emerald-400" />
                    Parquet Vector Slice Preview (First {previewData.data.length} Rows)
                  </h4>
                  <span className="text-[11px] font-mono text-zinc-500">
                    Showing {previewData.columns.length} columns
                  </span>
                </div>

                <div className="overflow-x-auto border border-zinc-800 rounded-lg max-h-72">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-zinc-900 sticky top-0 border-b border-zinc-800">
                      <tr>
                        {previewData.columns.map((c) => (
                          <th key={c} className="py-2.5 px-3 font-semibold text-zinc-300 truncate">
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60">
                      {previewData.data.map((row, i) => (
                        <tr key={i} className="hover:bg-zinc-900/40">
                          {previewData.columns.map((c) => (
                            <td key={c} className="py-2 px-3 text-zinc-400 truncate max-w-[200px]">
                              {String(row[c] ?? "—")}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: FORENSIC DIAGNOSTICS */}
        {activeLabTab === "forensic" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-rose-400" />
                  Forensic Integrity &amp; Statistical Anomaly Scan
                </h3>
                <p className="text-xs text-zinc-400 font-mono mt-0.5">
                  Benford&apos;s Law verification // Null pattern clusters // Outlier bounds
                </p>
              </div>

              <button
                onClick={loadForensicData}
                disabled={isForensicLoading}
                className="px-3 py-1.5 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-xs font-mono text-zinc-200 transition-colors flex items-center gap-1.5"
              >
                <RefreshCw
                  className={`w-3.5 h-3.5 ${isForensicLoading ? "animate-spin text-emerald-400" : ""}`}
                />
                <span>Re-run Scan</span>
              </button>
            </div>

            {isForensicLoading ? (
              <div className="p-12 text-center text-xs font-mono text-zinc-500">
                [Computing Benford&apos;s Law distributions and outlier matrices in DuckDB...]
              </div>
            ) : forensicReport ? (
              <div className="space-y-6">
                {/* Findings List */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {forensicReport.findings.map((finding, i) => (
                    <div
                      key={i}
                      className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono font-bold text-amber-400 uppercase">
                          {String(finding.title || finding.metric || "Diagnostic Finding")}
                        </span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 text-zinc-400 border border-zinc-800">
                          {String(finding.severity || "MEDIUM")}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-300 leading-relaxed font-mono">
                        {String(finding.description || finding.insight || JSON.stringify(finding))}
                      </p>
                    </div>
                  ))}
                </div>

                {/* Full Forensic Briefing Markdown / Text */}
                {forensicReport.report && (
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-6 space-y-3">
                    <h4 className="text-xs font-mono uppercase tracking-wider text-zinc-400">
                      Senior Forensic Audit Briefing
                    </h4>
                    <div className="text-xs font-mono text-zinc-300 leading-relaxed whitespace-pre-wrap bg-zinc-900/60 p-4 rounded-lg border border-zinc-800/80">
                      {forensicReport.report}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-12 text-center text-xs font-mono text-zinc-500">
                Click &quot;Re-run Scan&quot; to execute forensic integrity checks.
              </div>
            )}
          </div>
        )}

        {/* TAB 3: PLOTLY STUDIO */}
        {activeLabTab === "viz" && (
          <div className="space-y-6">
            {/* Chart Control Bar */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <span className="text-xs font-mono font-semibold text-zinc-200 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-emerald-400" />
                  Vector Chart Studio (2D Vector &amp; 3D WebGL)
                </span>

                <button
                  onClick={handleGenerateChart}
                  disabled={isChartLoading}
                  className="px-4 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-black font-semibold text-xs font-mono transition-colors flex items-center gap-1.5 shadow-sm"
                >
                  {isChartLoading ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Play className="w-3.5 h-3.5 fill-black" />
                  )}
                  <span>Generate Chart</span>
                </button>
              </div>

              {/* Variable Selectors */}
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-3 border-t border-zinc-800/80 font-mono text-xs">
                <div>
                  <label className="block text-[10px] text-zinc-400 uppercase mb-1">
                    Chart Type
                  </label>
                  <select
                    value={selectedChartType}
                    onChange={(e) => setSelectedChartType(e.target.value as LabChartType)}
                    className="w-full px-2.5 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="distribution">Distribution</option>
                    <option value="histogram">Histogram</option>
                    <option value="bar">Bar Chart</option>
                    <option value="scatter">Scatter Plot</option>
                    <option value="line">Line Trend</option>
                    <option value="heatmap">Heatmap</option>
                    <option value="correlation">Correlation Matrix</option>
                    <option value="box">Box Plot</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[10px] text-zinc-400 uppercase mb-1">
                    X Axis Column
                  </label>
                  <select
                    value={xCol}
                    onChange={(e) => setXCol(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="">[Auto-Select]</option>
                    {columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[10px] text-zinc-400 uppercase mb-1">
                    Y Axis Column
                  </label>
                  <select
                    value={yCol}
                    onChange={(e) => setYCol(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="">[Optional / Auto]</option>
                    {columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[10px] text-zinc-400 uppercase mb-1">
                    Color Hue Group
                  </label>
                  <select
                    value={colorCol}
                    onChange={(e) => setColorCol(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="">[None]</option>
                    {columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {chartError && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs font-mono text-rose-300">
                  {chartError}
                </div>
              )}
            </div>

            {/* Plotly Canvas Container */}
            {chartSpec ? (
              <PlotlyCanvas
                spec={chartSpec as any}
                title={`${selectedChartType.toUpperCase()}: ${xCol}${yCol ? ` vs ${yCol}` : ""}`}
              />
            ) : (
              <div className="w-full h-80 rounded-xl border border-zinc-800 bg-zinc-950/40 flex flex-col items-center justify-center text-xs font-mono text-zinc-500 space-y-2">
                <BarChart3 className="w-8 h-8 text-zinc-700" />
                <p>Select dimensions above and click &quot;Generate Chart&quot;</p>
              </div>
            )}
          </div>
        )}

        {/* TAB 4: PREDICTION LAB */}
        {activeLabTab === "predict" && (
          <PredictionLab fileId={fileId} columns={columns} />
        )}

        {/* TAB 5: DUCKDB SQL SANDBOX */}
        {activeLabTab === "sql" && (
          <div className="space-y-4">
            <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-semibold text-zinc-200 flex items-center gap-2">
                  <FileCode className="w-4 h-4 text-cyan-400" />
                  DuckDB In-Memory Analytical SQL Sandbox
                </span>

                <div className="flex items-center gap-3">
                  {sqlLatencyMs !== null && (
                    <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                      ⚡ {sqlLatencyMs}ms
                    </span>
                  )}

                  <button
                    onClick={handleExecuteSql}
                    disabled={isSqlExecuting}
                    className="px-3.5 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-600 disabled:opacity-50 text-black font-semibold text-xs font-mono transition-colors flex items-center gap-1.5 shadow-sm"
                  >
                    {isSqlExecuting ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Play className="w-3.5 h-3.5 fill-black" />
                    )}
                    <span>Run Query (Ctrl+Enter)</span>
                  </button>
                </div>
              </div>

              {/* SQL Textarea */}
              <textarea
                value={sqlQuery}
                onChange={(e) => setSqlQuery(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                    e.preventDefault();
                    if (!isSqlExecuting) {
                      handleExecuteSql();
                    }
                  }
                }}
                rows={5}
                className="w-full p-3 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-zinc-100 font-mono focus:outline-none focus:border-cyan-500 leading-relaxed selection:bg-cyan-500/20"
                placeholder="SELECT column_a, COUNT(*) FROM dataset GROUP BY column_a;"
              />

              {sqlError && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs font-mono text-rose-300">
                  {sqlError}
                </div>
              )}
            </div>

            {/* SQL Results Grid */}
            {sqlResults && (
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 space-y-3">
                <div className="flex items-center justify-between text-xs font-mono text-zinc-400">
                  <span>Returned {sqlResults.row_count} rows</span>
                  <span>DuckDB Vectorized Pipeline</span>
                </div>

                <div className="overflow-x-auto border border-zinc-800 rounded-lg max-h-80">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-zinc-900 sticky top-0 border-b border-zinc-800">
                      <tr>
                        {sqlResults.columns.map((c) => (
                          <th key={c} className="py-2.5 px-3 font-semibold text-zinc-300">
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60">
                      {sqlResults.rows.map((row, i) => (
                        <tr key={i} className="hover:bg-zinc-900/40">
                          {row.map((val, cellIdx) => (
                            <td key={cellIdx} className="py-2 px-3 text-zinc-400 truncate max-w-[200px]">
                              {String(val ?? "NULL")}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

