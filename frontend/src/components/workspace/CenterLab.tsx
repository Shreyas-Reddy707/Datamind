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
import { safeLocale } from "@/lib/format";
import {
  LabChartType,
  LabOverviewResponse,
} from "@/lib/types";
import { QualityGauge3D } from "@/components/spatial/QualityGauge3D";
import { EmbeddedPlotlyStudio } from "./EmbeddedPlotlyStudio";
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
    requestedChartOverride,
    setRequestedChartOverride,
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
    total_rows?: number;
  } | null>(null);
  const [previewSearch, setPreviewSearch] = useState("");
  const [previewLimit, setPreviewLimit] = useState(25);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  // Columns list
  const columns = overview ? Object.keys(overview.schema.columns) : [];

  // Auto-Select Default Best Settings & Generate Chart Per Uploaded File
  useEffect(() => {
    if (!overview || !overview.schema?.columns) return;
    const cols = overview.schema.columns;
    const colNames = Object.keys(cols);
    if (colNames.length === 0) return;

    const profile = overview.profile;
    const numCols = profile?.numeric_columns?.length
      ? profile.numeric_columns
      : colNames.filter((c) => {
          const t = (cols[c]?.type || "").toUpperCase();
          return (
            t.includes("INT") ||
            t.includes("FLOAT") ||
            t.includes("DOUBLE") ||
            t.includes("NUMERIC")
          );
        });

    const catCols = profile?.categorical_columns?.length
      ? profile.categorical_columns
      : colNames.filter((c) => !numCols.includes(c));

    // 1. Look for low-to-medium cardinality categorical column (2-20 distinct values)
    let bestCatCol = catCols.find((c) => {
      const dc = profile?.columns?.[c]?.distinct_count;
      return dc !== undefined ? dc >= 2 && dc <= 20 : false;
    });

    if (!bestCatCol && catCols.length > 0) {
      bestCatCol =
        catCols.find(
          (c) =>
            !c.toLowerCase().includes("id") &&
            !c.toLowerCase().includes("date")
        ) || catCols[0];
    }

    // Look for a numeric metric column (e.g. adr, lead_time, price, amount, sales)
    let bestNumCol =
      numCols.find((c) => {
        const cl = c.toLowerCase();
        return (
          !cl.includes("id") &&
          !cl.includes("year") &&
          !cl.includes("is_") &&
          (cl.includes("adr") ||
            cl.includes("time") ||
            cl.includes("price") ||
            cl.includes("amount") ||
            cl.includes("score") ||
            cl.includes("total") ||
            cl.includes("val"))
        );
      }) || numCols[0];

    let targetChartType: LabChartType = "distribution";
    let targetX = colNames[0];
    let targetY = "";

    if (bestCatCol && bestNumCol) {
      targetChartType = "bar";
      targetX = bestCatCol;
      targetY = bestNumCol;
    } else if (numCols.length >= 2) {
      targetChartType = "heatmap";
      targetX = numCols[0];
      targetY = numCols[1];
    } else if (numCols.length === 1) {
      targetChartType = "distribution";
      targetX = numCols[0];
    }

    setSelectedChartType(targetChartType);
    setXCol(targetX);
    setYCol(targetY);

    // Auto-trigger visualize on initial load or dataset switch
    api.lab
      .visualize(
        fileId,
        targetChartType,
        targetX || undefined,
        targetY || undefined
      )
      .then((res) => {
        const specToSet =
          (res as any)?.plotly_spec || (res as any)?.spec || res;
        setChartSpec(specToSet);
      })
      .catch((err) => {
        console.error("Auto-visualization load failed:", err);
      });
  }, [fileId, overview]);

  // Handle injected artifact
  useEffect(() => {
    if (injectedArtifact && injectedArtifact.type === "chart") {
      setChartSpec(injectedArtifact.data as Record<string, unknown>);
    }
  }, [injectedArtifact]);

  // Handle agentic chart override from chat ui_action
  useEffect(() => {
    if (!requestedChartOverride) return;
    const { chart_type, x_col, y_col, color_col } = requestedChartOverride;
    const nextType = chart_type || "bar";
    const nextX = x_col ?? xCol;
    const nextY = y_col ?? "";
    const nextColor = color_col ?? "";
    setSelectedChartType(nextType);
    setXCol(nextX);
    setYCol(nextY);
    setColorCol(nextColor);
    setRequestedChartOverride(null);
    handleGenerateChart(nextType, nextX, nextY, nextColor);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestedChartOverride?.nonce]);

  const loadPreviewData = async (limit = previewLimit, search = previewSearch) => {
    try {
      setIsPreviewLoading(true);
      const res = await api.lab.preview(fileId, limit, search);
      setPreviewData(res);
    } catch (err) {
      console.error("Failed to load preview data:", err);
    } finally {
      setIsPreviewLoading(false);
    }
  };

  // Load preview data on mount
  useEffect(() => {
    loadPreviewData(previewLimit, "");
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

  const handleGenerateChart = async (
    overrideType?: LabChartType,
    overrideX?: string,
    overrideY?: string,
    overrideColor?: string
  ) => {
    const ctype = overrideType ?? selectedChartType;
    const xVal = overrideX !== undefined ? overrideX : xCol;
    const yVal = overrideY !== undefined ? overrideY : yCol;
    const colorVal = overrideColor !== undefined ? overrideColor : colorCol;
    try {
      setIsChartLoading(true);
      setChartError(null);
      const res = await api.lab.visualize(
        fileId,
        ctype,
        xVal || undefined,
        yVal || undefined,
        colorVal || undefined
      );
      const specToSet = (res as any)?.plotly_spec || (res as any)?.spec || res;
      setChartSpec(specToSet);
    } catch (err: any) {
      console.error("Chart generation failed:", err);
      setChartError(err.message || "Failed to generate chart visualization.");
    } finally {
      setIsChartLoading(false);
    }
  };

  const extractFindingColumns = (finding: Record<string, unknown>): string[] => {
    const text = `${String(finding.title || "")} ${String(finding.description || "")} ${String(finding.insight || "")}`.toLowerCase();
    const matched = columns.filter((col) => {
      const escaped = col.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return new RegExp(`(^|[^a-z0-9_])${escaped}([^a-z0-9_]|$)`, "i").test(text);
    });
    return matched.slice(0, 3);
  };

  const handleInspectFindingEvidence = (finding: Record<string, unknown>, explicitCol?: string) => {
    const matched = extractFindingColumns(finding);
    const primary = explicitCol || matched[0];
    const secondary = matched.find((c) => c !== primary) || "";
    const numCols = overview?.profile?.numeric_columns || [];

    let nextType: LabChartType = "distribution";
    let nextX = primary || xCol;
    let nextY = secondary;

    if (primary && secondary) {
      const pNum = numCols.includes(primary);
      const sNum = numCols.includes(secondary);
      nextType = pNum && sNum ? "scatter" : "bar";
    } else if (primary) {
      const pNum = numCols.includes(primary);
      nextType = pNum ? "histogram" : "bar";
      nextY = "";
    } else if (numCols.length >= 2) {
      nextType = "heatmap";
      nextX = numCols[0];
      nextY = numCols[1];
    }

    setSelectedChartType(nextType);
    setXCol(nextX);
    setYCol(nextY);
    handleGenerateChart(nextType, nextX, nextY, "");
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
    { id: "overview", label: "Overview & Data Explorer", icon: TableIcon },
    { id: "forensic", label: "Forensic Analytics Lab", icon: ShieldAlert },
    { id: "predict", label: "Predictive AutoML Lab", icon: Activity },
    { id: "sql", label: "DuckDB SQL Sandbox", icon: FileCode },
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

            {/* Interactive Data Explorer / Row Values Table */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <TableIcon className="w-4 h-4 text-emerald-400" />
                  <h4 className="text-xs font-mono uppercase tracking-wider text-zinc-300 font-semibold">
                    Interactive Data Explorer
                  </h4>
                  {previewData?.total_rows !== undefined && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 text-zinc-400 border border-zinc-800">
                      {safeLocale(previewData.total_rows, "0")} Rows Total
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      placeholder="Search values..."
                      value={previewSearch}
                      onChange={(e) => setPreviewSearch(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          loadPreviewData(previewLimit, previewSearch);
                        }
                      }}
                      className="pl-8 pr-3 py-1 bg-zinc-900 border border-zinc-800 rounded-md text-xs font-mono text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500 w-36 sm:w-48"
                    />
                  </div>

                  <select
                    value={previewLimit}
                    onChange={(e) => {
                      const newLimit = Number(e.target.value);
                      setPreviewLimit(newLimit);
                      loadPreviewData(newLimit, previewSearch);
                    }}
                    className="px-2 py-1 bg-zinc-900 border border-zinc-800 rounded-md text-xs font-mono text-zinc-300 focus:outline-none focus:border-emerald-500"
                  >
                    <option value={25}>25 rows</option>
                    <option value={50}>50 rows</option>
                    <option value={100}>100 rows</option>
                  </select>

                  <button
                    onClick={() => loadPreviewData(previewLimit, previewSearch)}
                    disabled={isPreviewLoading}
                    className="p-1.5 rounded-md bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-zinc-400 hover:text-white transition-colors disabled:opacity-50"
                    title="Refresh table"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isPreviewLoading ? "animate-spin text-emerald-400" : ""}`} />
                  </button>
                </div>
              </div>

              {isPreviewLoading && !previewData ? (
                <div className="p-8 text-center text-xs font-mono text-zinc-500 flex items-center justify-center gap-2">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                  Loading vectorized row slice...
                </div>
              ) : previewData && previewData.data.length > 0 ? (
                <div className="overflow-x-auto border border-zinc-800 rounded-lg max-h-80">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-zinc-900 sticky top-0 border-b border-zinc-800 z-10">
                      <tr>
                        <th className="py-2 px-3 font-semibold text-zinc-500 w-12 text-center">#</th>
                        {previewData.columns.map((c) => (
                          <th key={c} className="py-2.5 px-3 font-semibold text-zinc-300 truncate">
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60">
                      {previewData.data.map((row, i) => (
                        <tr key={i} className="hover:bg-zinc-900/40 transition-colors">
                          <td className="py-2 px-3 text-zinc-600 text-center font-mono text-[11px]">{i + 1}</td>
                          {previewData.columns.map((c) => (
                            <td key={c} className="py-2 px-3 text-zinc-300 truncate max-w-[220px]">
                              {row[c] !== null && row[c] !== undefined ? String(row[c]) : <span className="text-zinc-600 italic">null</span>}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="p-8 text-center text-xs font-mono text-zinc-500 border border-dashed border-zinc-800 rounded-lg">
                  No matching row records found.
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: FORENSIC ANALYTICS LAB & EMBEDDED PLOTLY STUDIO */}
        {activeLabTab === "forensic" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-rose-400" />
                  Forensic Analytics &amp; Visual Evidence Lab
                </h3>
                <p className="text-xs text-zinc-400 font-mono mt-0.5">
                  Context &rarr; Finding &rarr; Evidence &rarr; Implication // Click any finding or column pill to render evidence
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
                  {forensicReport.findings.map((finding, i) => {
                    const matchedCols = extractFindingColumns(finding);
                    return (
                      <div
                        key={i}
                        onClick={() => handleInspectFindingEvidence(finding)}
                        className="rounded-xl border border-zinc-800 hover:border-emerald-500/40 bg-zinc-950/70 p-4 space-y-2.5 cursor-pointer transition-all group"
                        title="Click to plot supporting visual evidence in Plotly Studio below"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-mono font-bold text-amber-400 uppercase group-hover:text-emerald-400 transition-colors">
                            {String(finding.title || finding.metric || "Diagnostic Finding")}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 text-zinc-400 border border-zinc-800">
                            {String(finding.severity || "MEDIUM")}
                          </span>
                        </div>
                        <p className="text-xs text-zinc-300 leading-relaxed font-mono">
                          {String(finding.description || finding.insight || JSON.stringify(finding))}
                        </p>
                        {matchedCols.length > 0 && (
                          <div className="flex flex-wrap items-center gap-1.5 pt-1">
                            <span className="text-[10px] font-mono text-zinc-500">Visualize:</span>
                            {matchedCols.map((col) => (
                              <button
                                key={col}
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleInspectFindingEvidence(finding, col);
                                }}
                                className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
                              >
                                {col}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Embedded Interactive Analytical Plotly Studio */}
                <EmbeddedPlotlyStudio
                  title="Forensic Interactive Plotly Studio (2D Vector & 3D WebGL)"
                  columns={columns}
                  chartType={selectedChartType}
                  xCol={xCol}
                  yCol={yCol}
                  colorCol={colorCol}
                  chartSpec={chartSpec}
                  isLoading={isChartLoading}
                  error={chartError}
                  onChangeChartType={setSelectedChartType}
                  onChangeXCol={setXCol}
                  onChangeYCol={setYCol}
                  onChangeColorCol={setColorCol}
                  onGenerate={() => handleGenerateChart()}
                />

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
              <div className="space-y-6">
                <div className="p-8 text-center text-xs font-mono text-zinc-500 rounded-xl border border-dashed border-zinc-800">
                  Click &quot;Re-run Scan&quot; to execute forensic integrity checks, or explore visualizations below.
                </div>
                <EmbeddedPlotlyStudio
                  title="Forensic Interactive Plotly Studio (2D Vector & 3D WebGL)"
                  columns={columns}
                  chartType={selectedChartType}
                  xCol={xCol}
                  yCol={yCol}
                  colorCol={colorCol}
                  chartSpec={chartSpec}
                  isLoading={isChartLoading}
                  error={chartError}
                  onChangeChartType={setSelectedChartType}
                  onChangeXCol={setXCol}
                  onChangeYCol={setYCol}
                  onChangeColorCol={setColorCol}
                  onGenerate={() => handleGenerateChart()}
                />
              </div>
            )}
          </div>
        )}

        {/* TAB 3: PREDICTIVE AUTOML LAB */}
        {activeLabTab === "predict" && (
          <PredictionLab fileId={fileId} columns={columns} />
        )}

        {/* TAB 4: DUCKDB SQL SANDBOX */}
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

