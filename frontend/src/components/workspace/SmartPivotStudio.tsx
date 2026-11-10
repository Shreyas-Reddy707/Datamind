"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  ArrowDownUp,
  BarChart3,
  ChevronDown,
  ChevronUp,
  Code2,
  Download,
  Filter,
  GitMerge,
  Layers,
  Play,
  Plus,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Table as TableIcon,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { safeLocale } from "@/lib/format";
import {
  BuilderAggType,
  BuilderFilterOp,
  BuilderFilterSpec,
  BuilderMetricSpec,
  LabChartType,
  LabOverviewResponse,
  LabQueryPayload,
  LabQueryResponse,
  UserFile,
} from "@/lib/types";
import { useWorkspaceStore } from "@/store/useWorkspaceStore";

interface SmartPivotStudioProps {
  fileId: string;
  overview: LabOverviewResponse | null;
  onTurnIntoChart: (chartType: LabChartType, xCol: string, yCol?: string) => void;
}

interface SmartPreset {
  id: string;
  label: string;
  badge: string;
  payload: LabQueryPayload;
  groupBy: string[];
  metrics: BuilderMetricSpec[];
  filters: BuilderFilterSpec[];
  sortDir: "asc" | "desc";
  limit: number;
}

const AGG_LABELS: Array<{ value: BuilderAggType; label: string }> = [
  { value: "avg", label: "Average" },
  { value: "sum", label: "Total (Sum)" },
  { value: "count", label: "Count of Rows" },
  { value: "min", label: "Minimum" },
  { value: "max", label: "Maximum" },
  { value: "median", label: "Median" },
];

const FILTER_OP_LABELS: Array<{ value: BuilderFilterOp; label: string }> = [
  { value: "eq", label: "Equals" },
  { value: "neq", label: "Does Not Equal" },
  { value: "gt", label: "Greater Than" },
  { value: "lt", label: "Less Than" },
  { value: "contains", label: "Contains" },
  { value: "not_null", label: "Is Not Empty" },
];

export function SmartPivotStudio({
  fileId,
  overview,
  onTurnIntoChart,
}: SmartPivotStudioProps) {
  const { selectedJoinFileIds } = useWorkspaceStore();

  const allColumns = useMemo(
    () => (overview ? Object.keys(overview.schema.columns) : []),
    [overview]
  );
  const numericCols = useMemo(() => {
    if (overview?.profile?.numeric_columns?.length) {
      return overview.profile.numeric_columns;
    }
    if (!overview?.schema?.columns) return [];
    return allColumns.filter((c) => {
      const t = (overview.schema.columns[c]?.type || "").toUpperCase();
      return (
        t.includes("INT") ||
        t.includes("FLOAT") ||
        t.includes("DOUBLE") ||
        t.includes("NUMERIC") ||
        t.includes("DECIMAL")
      );
    });
  }, [overview, allColumns]);

  const categoricalCols = useMemo(() => {
    if (overview?.profile?.categorical_columns?.length) {
      return overview.profile.categorical_columns;
    }
    return allColumns.filter((c) => !numericCols.includes(c));
  }, [overview, allColumns, numericCols]);

  // Plain-English Bar
  const [questionInput, setQuestionInput] = useState("");

  // Visual Builder AST State
  const [groupByCols, setGroupByCols] = useState<string[]>([]);
  const [metrics, setMetrics] = useState<BuilderMetricSpec[]>([]);
  const [filters, setFilters] = useState<BuilderFilterSpec[]>([]);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [rowLimit, setRowLimit] = useState<number>(50);

  // Visual Join State
  const [workspaceFiles, setWorkspaceFiles] = useState<UserFile[]>([]);
  const [joinEnabled, setJoinEnabled] = useState(false);
  const [joinRightFileId, setJoinRightFileId] = useState<string>("");
  const [joinLeftCol, setJoinLeftCol] = useState<string>("");
  const [joinRightCol, setJoinRightCol] = useState<string>("");
  const [joinType, setJoinType] = useState<"inner" | "left">("inner");

  // Advanced Power Drawer (collapsed by default)
  const [showAdvancedSql, setShowAdvancedSql] = useState(false);
  const [editableSql, setEditableSql] = useState("");

  // Results & Latency
  const [result, setResult] = useState<LabQueryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasInitialized, setHasInitialized] = useState(false);

  // Load workspace files for visual join dropdown
  useEffect(() => {
    api.datasets
      .list()
      .then((files) => {
        const others = files.filter((f) => f.id !== fileId);
        setWorkspaceFiles(others);
        if (others.length > 0 && !joinRightFileId) {
          const preferred =
            others.find((f) => selectedJoinFileIds.includes(f.id)) || others[0];
          setJoinRightFileId(preferred.id);
        }
      })
      .catch(() => {
        setWorkspaceFiles([]);
      });
  }, [fileId, selectedJoinFileIds]);

  // Sync left-panel join file checkboxes
  useEffect(() => {
    if (selectedJoinFileIds.length > 0) {
      setJoinEnabled(true);
      setJoinRightFileId(selectedJoinFileIds[0]);
    }
  }, [selectedJoinFileIds]);

  const selectedRightFile = useMemo(
    () => workspaceFiles.find((f) => f.id === joinRightFileId) || null,
    [workspaceFiles, joinRightFileId]
  );

  const rightFileCols = useMemo(() => {
    const colsObj = selectedRightFile?.global_file?.schema_json?.columns;
    return colsObj ? Object.keys(colsObj) : [];
  }, [selectedRightFile]);

  // Auto-suggest matching join keys when join target file changes
  useEffect(() => {
    if (allColumns.length === 0 || rightFileCols.length === 0) return;
    const shared = allColumns.find((c) => rightFileCols.includes(c));
    if (shared) {
      setJoinLeftCol(shared);
      setJoinRightCol(shared);
    } else {
      if (!joinLeftCol || !allColumns.includes(joinLeftCol)) {
        setJoinLeftCol(allColumns[0]);
      }
      if (!joinRightCol || !rightFileCols.includes(joinRightCol)) {
        setJoinRightCol(rightFileCols[0]);
      }
    }
  }, [joinRightFileId, allColumns, rightFileCols]);

  // Dynamic 1-Click Smart Preset Pills based on actual dataset schema
  const presets = useMemo<SmartPreset[]>(() => {
    if (allColumns.length === 0) return [];
    const list: SmartPreset[] = [];
    const catStats = overview?.profile?.columns || {};

    const cleanCatCols = categoricalCols.filter(
      (c) => !c.toLowerCase().includes("date") && !c.toLowerCase().endsWith("_id")
    );
    const lowCardCat =
      cleanCatCols.find((c) => {
        const dc = catStats[c]?.distinct_count;
        return dc !== undefined && dc >= 2 && dc <= 12;
      }) || cleanCatCols[0] || categoricalCols[0];

    const secondCat =
      cleanCatCols.find((c) => c !== lowCardCat && (catStats[c]?.distinct_count ?? 99) <= 20) ||
      cleanCatCols.find((c) => c !== lowCardCat) ||
      lowCardCat;

    const topBreakdownCat =
      cleanCatCols.find((c) => {
        const dc = catStats[c]?.distinct_count ?? 0;
        return dc >= 5 && c !== lowCardCat;
      }) || secondCat || lowCardCat;

    const cleanNumCols = numericCols.filter(
      (c) => !c.toLowerCase().includes("id") && !c.toLowerCase().includes("year")
    );
    const primaryNum =
      cleanNumCols.find((c) => {
        const cl = c.toLowerCase();
        return (
          cl.includes("adr") ||
          cl.includes("price") ||
          cl.includes("revenue") ||
          cl.includes("amount") ||
          cl.includes("lead") ||
          cl.includes("total")
        );
      }) ||
      cleanNumCols[0] ||
      numericCols[0];

    if (lowCardCat) {
      const m: BuilderMetricSpec[] = [{ col: "*", agg: "count" }];
      if (primaryNum) m.push({ col: primaryNum, agg: "avg" });
      list.push({
        id: "summary-cat",
        label: `Summary by ${lowCardCat}`,
        badge: "Overview",
        groupBy: [lowCardCat],
        metrics: m,
        filters: [],
        sortDir: "desc",
        limit: 50,
        payload: {
          mode: "builder",
          group_by: [lowCardCat],
          metrics: m,
          filters: [],
          sort_dir: "desc",
          limit: 50,
        },
      });
    }

    if (secondCat && primaryNum) {
      const m: BuilderMetricSpec[] = [
        { col: primaryNum, agg: "avg" },
        { col: "*", agg: "count" },
      ];
      list.push({
        id: "avg-metric-by-cat",
        label: `Average ${primaryNum} by ${secondCat}`,
        badge: "Metric",
        groupBy: [secondCat],
        metrics: m,
        filters: [],
        sortDir: "desc",
        limit: 50,
        payload: {
          mode: "builder",
          group_by: [secondCat],
          metrics: m,
          filters: [],
          sort_dir: "desc",
          limit: 50,
        },
      });
    }

    if (topBreakdownCat) {
      const m: BuilderMetricSpec[] = [{ col: "*", agg: "count" }];
      if (primaryNum) m.push({ col: primaryNum, agg: "avg" });
      list.push({
        id: "top-10-cat",
        label: `Top 10 ${topBreakdownCat} breakdown`,
        badge: "Ranking",
        groupBy: [topBreakdownCat],
        metrics: m,
        filters: [],
        sortDir: "desc",
        limit: 10,
        payload: {
          mode: "builder",
          group_by: [topBreakdownCat],
          metrics: m,
          filters: [],
          sort_by: "total_rows",
          sort_dir: "desc",
          limit: 10,
        },
      });
    }

    const nullableCol =
      allColumns.find((c) => (catStats[c]?.null_percentage ?? 0) > 0) ||
      primaryNum ||
      allColumns[0];
    if (nullableCol) {
      const f: BuilderFilterSpec[] = [{ col: nullableCol, op: "not_null" }];
      list.push({
        id: "non-null-filter",
        label: `Filter non-null ${nullableCol}`,
        badge: "Clean Slice",
        groupBy: [],
        metrics: [],
        filters: f,
        sortDir: "desc",
        limit: 50,
        payload: {
          mode: "builder",
          group_by: [],
          metrics: [],
          filters: f,
          sort_dir: "desc",
          limit: 50,
        },
      });
    }

    return list;
  }, [allColumns, categoricalCols, numericCols, overview]);

  const executePayload = async (payload: LabQueryPayload) => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await api.lab.query(fileId, payload);
      setResult(res);
      if (res.generated_sql) {
        setEditableSql(res.generated_sql);
      }
    } catch (err: any) {
      setError(err?.message || "Could not build the requested table.");
    } finally {
      setIsLoading(false);
    }
  };

  // Run first sensible preset automatically on mount / dataset switch
  useEffect(() => {
    if (!hasInitialized && presets.length > 0) {
      const first = presets[0];
      setGroupByCols(first.groupBy);
      setMetrics(first.metrics);
      setFilters(first.filters);
      setSortDir(first.sortDir);
      setRowLimit(first.limit);
      setHasInitialized(true);
      executePayload(first.payload);
    }
  }, [presets, hasInitialized]);

  useEffect(() => {
    setHasInitialized(false);
    setResult(null);
  }, [fileId]);

  const runBuilderState = (
    overrideGroups = groupByCols,
    overrideMetrics = metrics,
    overrideFilters = filters,
    overrideSortDir = sortDir,
    overrideLimit = rowLimit
  ) => {
    const cleanFilters = overrideFilters.filter(
      (f) => f.col && (f.op === "not_null" || f.op === "is_null" || String(f.val ?? "").trim() !== "")
    );
    const payload: LabQueryPayload = {
      mode: "builder",
      group_by: overrideGroups,
      metrics: overrideMetrics,
      filters: cleanFilters,
      sort_dir: overrideSortDir,
      limit: overrideLimit,
      join_config:
        joinEnabled && joinRightFileId && joinLeftCol && joinRightCol
          ? {
              right_file_id: joinRightFileId,
              left_col: joinLeftCol,
              right_col: joinRightCol,
              join_type: joinType,
            }
          : null,
    };
    executePayload(payload);
  };

  const handleAskQuestion = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const q = questionInput.trim();
    if (!q) return;
    executePayload({
      mode: "question",
      question: q,
      limit: rowLimit,
      join_config:
        joinEnabled && joinRightFileId && joinLeftCol && joinRightCol
          ? {
              right_file_id: joinRightFileId,
              left_col: joinLeftCol,
              right_col: joinRightCol,
              join_type: joinType,
            }
          : null,
    });
  };

  const handlePresetClick = (preset: SmartPreset) => {
    setGroupByCols(preset.groupBy);
    setMetrics(preset.metrics);
    setFilters(preset.filters);
    setSortDir(preset.sortDir);
    setRowLimit(preset.limit);
    executePayload(preset.payload);
  };

  const toggleGroupColumn = (col: string) => {
    let next: string[];
    if (groupByCols.includes(col)) {
      next = groupByCols.filter((c) => c !== col);
    } else if (groupByCols.length >= 3) {
      next = [...groupByCols.slice(1), col];
    } else {
      next = [...groupByCols, col];
    }
    setGroupByCols(next);
    runBuilderState(next, metrics, filters, sortDir, rowLimit);
  };

  const handleResetRawRows = () => {
    setGroupByCols([]);
    setMetrics([]);
    runBuilderState([], [], filters, sortDir, rowLimit);
  };

  const handleAddMetric = () => {
    const defaultCol = numericCols[0] || "*";
    const next: BuilderMetricSpec[] = [
      ...metrics,
      { col: defaultCol, agg: defaultCol === "*" ? "count" : "avg" },
    ];
    setMetrics(next);
  };

  const handleAddFilter = () => {
    const defaultCol = allColumns[0] || "";
    if (!defaultCol) return;
    setFilters([...filters, { col: defaultCol, op: "eq", val: "" }]);
  };

  const handleExportCsv = () => {
    if (!result || result.columns.length === 0) return;
    const escCsv = (val: unknown): string => {
      if (val === null || val === undefined) return "";
      const s = String(val);
      if (/[",\n\r]/.test(s)) {
        return `"${s.replace(/"/g, '""')}"`;
      }
      return s;
    };
    const header = result.columns.map(escCsv).join(",");
    const body = result.rows.map((row) => row.map(escCsv).join(",")).join("\n");
    const csvContent = `${header}\n${body}`;
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const baseName = (overview?.filename || "datamind_table").replace(/\.[^.]+$/, "");
    link.href = url;
    link.download = `${baseName}_pivot.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleTurnIntoChart = () => {
    // Map the currently displayed result table dimensions directly into Forensic Lab Plotly Studio
    const validSet = new Set(allColumns);
    let xTarget = "";
    let yTarget = "";

    if (result?.columns?.length) {
      xTarget = result.columns.find((c) => validSet.has(c)) || "";
      for (const rc of result.columns) {
        const stripped = rc.replace(/^(avg|sum|min|max|median|count)_/, "");
        if (stripped !== xTarget && validSet.has(stripped)) {
          yTarget = stripped;
          break;
        }
      }
    }

    if (!xTarget) {
      xTarget = groupByCols[0] || allColumns[0] || "";
    }
    if (!yTarget) {
      const explicitMetricCol = metrics.find(
        (m) => m.col !== "*" && m.col !== xTarget && validSet.has(m.col)
      )?.col;
      yTarget = explicitMetricCol || numericCols.find((c) => c !== xTarget) || "";
    }

    const chartType: LabChartType =
      xTarget && yTarget ? "bar" : numericCols.includes(xTarget) ? "histogram" : "bar";
    onTurnIntoChart(chartType, xTarget, yTarget || undefined);
  };

  return (
    <div className="space-y-4">
      {/* PART 1: Ask in Plain English + 1-Click Preset Pills */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-white font-mono flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-emerald-400" />
              Ask for a Table in Plain English
            </h3>
            <p className="text-[11px] text-zinc-400 font-mono mt-0.5">
              Type any summary request below or click filters and groupings — zero SQL required
            </p>
          </div>
          {result?.execution_time_ms !== undefined && (
            <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded border border-emerald-500/20 self-start sm:self-auto">
              ⚡ {result.execution_time_ms}ms
            </span>
          )}
        </div>

        <form onSubmit={handleAskQuestion} className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={questionInput}
              onChange={(e) => setQuestionInput(e.target.value)}
              placeholder="Ask for any table or breakdown in plain English (e.g., 'Average adr by hotel and market_segment' or 'Top 10 countries by bookings')..."
              className="w-full pl-9 pr-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-zinc-100 font-mono placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500"
            />
          </div>
          <button
            type="submit"
            disabled={isLoading || !questionInput.trim()}
            className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-zinc-950 font-semibold text-xs font-mono transition-colors flex items-center justify-center gap-1.5 shrink-0 cursor-pointer"
          >
            {isLoading ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5 fill-zinc-950" />
            )}
            <span>Ask &amp; Build Table</span>
          </button>
        </form>

        {/* Auto-Generated 1-Click Smart Preset Pills */}
        {presets.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="text-[10px] font-mono uppercase text-zinc-500 mr-1">
              Quick Summary Tables (1-Click):
            </span>
            {presets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                disabled={isLoading}
                onClick={() => handlePresetClick(preset)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 hover:border-emerald-500/40 text-[11px] font-mono text-zinc-300 hover:text-white transition-colors cursor-pointer"
              >
                <span className="text-[9px] uppercase px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {preset.badge}
                </span>
                <span>{preset.label}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* PART 2: Visual Point-and-Click Table Builder (No Coding) */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 space-y-4">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Group By (Categories) */}
          <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/90 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono font-semibold text-zinc-200 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-emerald-400" />
                Group Rows By
              </span>
              <button
                type="button"
                onClick={handleResetRawRows}
                className={`text-[10px] font-mono px-2 py-0.5 rounded border transition-colors ${
                  groupByCols.length === 0
                    ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                    : "bg-zinc-900 text-zinc-400 border-zinc-700 hover:text-white"
                }`}
              >
                None (Show Raw Rows)
              </button>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {(categoricalCols.length > 0 ? categoricalCols : allColumns)
                .slice(0, 8)
                .map((col) => {
                  const selected = groupByCols.includes(col);
                  return (
                    <button
                      key={col}
                      type="button"
                      onClick={() => toggleGroupColumn(col)}
                      className={`px-2 py-1 rounded text-[11px] font-mono border transition-colors ${
                        selected
                          ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-300 font-semibold"
                          : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700"
                      }`}
                    >
                      {col}
                    </button>
                  );
                })}
            </div>

            {allColumns.length > 8 && (
              <div className="flex items-center gap-2 pt-1">
                <select
                  value=""
                  onChange={(e) => {
                    if (e.target.value) toggleGroupColumn(e.target.value);
                  }}
                  className="px-2 py-1 bg-zinc-950 border border-zinc-800 rounded text-[11px] font-mono text-zinc-300 focus:outline-none focus:border-emerald-500"
                >
                  <option value="">+ Pick any column to group...</option>
                  {allColumns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                {groupByCols.length > 0 && (
                  <span className="text-[10px] font-mono text-zinc-500">
                    Active: {groupByCols.join(" -> ")}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* What to Calculate (Metrics) */}
          <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/90 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono font-semibold text-zinc-200 flex items-center gap-1.5">
                <BarChart3 className="w-3.5 h-3.5 text-cyan-400" />
                Calculate
              </span>
              <button
                type="button"
                onClick={handleAddMetric}
                className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 hover:bg-zinc-800 text-cyan-300 border border-zinc-700 transition-colors"
              >
                <Plus className="w-3 h-3" />
                Add Metric
              </button>
            </div>

            {metrics.length === 0 ? (
              <p className="text-[11px] font-mono text-zinc-500 py-2">
                No summary metric selected — displaying raw rows (or row counts when grouped).
              </p>
            ) : (
              <div className="space-y-1.5">
                {metrics.map((m, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <select
                      value={m.agg}
                      onChange={(e) => {
                        const nextAgg = e.target.value as BuilderAggType;
                        const next = metrics.map((item, i) =>
                          i === idx
                            ? {
                                ...item,
                                agg: nextAgg,
                                col:
                                  nextAgg !== "count" && item.col === "*"
                                    ? numericCols[0] || allColumns[0] || "*"
                                    : item.col,
                              }
                            : item
                        );
                        setMetrics(next);
                      }}
                      className="px-2 py-1 bg-zinc-950 border border-zinc-800 rounded text-[11px] font-mono text-zinc-200 focus:outline-none focus:border-emerald-500"
                    >
                      {AGG_LABELS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>

                    <select
                      value={m.col}
                      onChange={(e) => {
                        const next = metrics.map((item, i) =>
                          i === idx ? { ...item, col: e.target.value } : item
                        );
                        setMetrics(next);
                      }}
                      className="flex-1 px-2 py-1 bg-zinc-950 border border-zinc-800 rounded text-[11px] font-mono text-zinc-200 focus:outline-none focus:border-emerald-500"
                    >
                      {m.agg === "count" && <option value="*">All Matching Rows (*)</option>}
                      {(m.agg === "count" ? allColumns : numericCols.length > 0 ? numericCols : allColumns).map(
                        (c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        )
                      )}
                    </select>

                    <button
                      type="button"
                      onClick={() => setMetrics(metrics.filter((_, i) => i !== idx))}
                      className="p-1 text-zinc-500 hover:text-rose-400 transition-colors"
                      title="Remove calculation"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Filter Rows + Visual Join Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Filters */}
          <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/90 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono font-semibold text-zinc-200 flex items-center gap-1.5">
                <Filter className="w-3.5 h-3.5 text-amber-400" />
                Filter Data
              </span>
              <button
                type="button"
                onClick={handleAddFilter}
                className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 hover:bg-zinc-800 text-amber-300 border border-zinc-700 transition-colors"
              >
                <Plus className="w-3 h-3" />
                Add Filter
              </button>
            </div>

            {filters.length === 0 ? (
              <p className="text-[11px] font-mono text-zinc-500">
                No active row filters. Click &quot;+ Add Filter&quot; to narrow down values.
              </p>
            ) : (
              <div className="space-y-1.5">
                {filters.map((flt, idx) => (
                  <div key={idx} className="flex flex-wrap sm:flex-nowrap items-center gap-1.5">
                    <select
                      value={flt.col}
                      onChange={(e) => {
                        setFilters(
                          filters.map((item, i) =>
                            i === idx ? { ...item, col: e.target.value } : item
                          )
                        );
                      }}
                      className="px-2 py-1 bg-zinc-950 border border-zinc-800 rounded text-[11px] font-mono text-zinc-200 max-w-[140px]"
                    >
                      {allColumns.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>

                    <select
                      value={flt.op}
                      onChange={(e) => {
                        setFilters(
                          filters.map((item, i) =>
                            i === idx
                              ? { ...item, op: e.target.value as BuilderFilterOp }
                              : item
                          )
                        );
                      }}
                      className="px-2 py-1 bg-zinc-950 border border-zinc-800 rounded text-[11px] font-mono text-zinc-200"
                    >
                      {FILTER_OP_LABELS.map((op) => (
                        <option key={op.value} value={op.value}>
                          {op.label}
                        </option>
                      ))}
                    </select>

                    {flt.op !== "not_null" && flt.op !== "is_null" && (
                      <input
                        type="text"
                        value={String(flt.val ?? "")}
                        onChange={(e) => {
                          setFilters(
                            filters.map((item, i) =>
                              i === idx ? { ...item, val: e.target.value } : item
                            )
                          );
                        }}
                        placeholder="Value..."
                        className="flex-1 min-w-[90px] px-2 py-1 bg-zinc-950 border border-zinc-800 rounded text-[11px] font-mono text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
                      />
                    )}

                    <button
                      type="button"
                      onClick={() => setFilters(filters.filter((_, i) => i !== idx))}
                      className="p-1 text-zinc-500 hover:text-rose-400 transition-colors"
                      title="Remove filter"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Combine With Another File (Visual Join) & Sort/Limit Controls */}
          <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/90 space-y-2.5 flex flex-col justify-between">
            {workspaceFiles.length > 0 ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono font-semibold text-zinc-200 flex items-center gap-1.5">
                    <GitMerge className="w-3.5 h-3.5 text-emerald-400" />
                    Combine With Another File (Visual Join)
                  </span>
                  <label className="inline-flex items-center gap-1.5 text-[10px] font-mono text-zinc-400 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={joinEnabled}
                      onChange={(e) => setJoinEnabled(e.target.checked)}
                      className="rounded border-zinc-700 bg-zinc-900 text-emerald-500"
                    />
                    Enable Join
                  </label>
                </div>

                {joinEnabled && (
                  <div className="space-y-1.5 text-[11px] font-mono">
                    <div className="flex items-center gap-2">
                      <select
                        value={joinType}
                        onChange={(e) => setJoinType(e.target.value as "inner" | "left")}
                        className="px-2 py-1 bg-zinc-950 border border-zinc-800 rounded text-zinc-200"
                      >
                        <option value="inner">Matching Rows Only</option>
                        <option value="left">Keep All Primary Rows</option>
                      </select>
                      <select
                        value={joinRightFileId}
                        onChange={(e) => setJoinRightFileId(e.target.value)}
                        className="flex-1 px-2 py-1 bg-zinc-950 border border-zinc-800 rounded text-zinc-200"
                      >
                        {workspaceFiles.map((wf) => (
                          <option key={wf.id} value={wf.id}>
                            {wf.display_name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="flex items-center gap-1.5 text-[10px] text-zinc-400">
                      <span>Match</span>
                      <select
                        value={joinLeftCol}
                        onChange={(e) => setJoinLeftCol(e.target.value)}
                        className="flex-1 px-2 py-1 bg-zinc-950 border border-zinc-800 rounded text-[11px] text-zinc-200"
                      >
                        {allColumns.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                      <span>with</span>
                      <select
                        value={joinRightCol}
                        onChange={(e) => setJoinRightCol(e.target.value)}
                        className="flex-1 px-2 py-1 bg-zinc-950 border border-zinc-800 rounded text-[11px] text-zinc-200"
                      >
                        {rightFileCols.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-[11px] font-mono text-zinc-500">
                Upload a second dataset in the sidebar anytime to visually combine files by matching columns.
              </div>
            )}

            {/* Sort, Limit & Update Table */}
            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-zinc-800/80">
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1">
                  <ArrowDownUp className="w-3.5 h-3.5 text-zinc-500" />
                  <select
                    value={sortDir}
                    onChange={(e) => {
                      const nextDir = e.target.value as "asc" | "desc";
                      setSortDir(nextDir);
                      runBuilderState(groupByCols, metrics, filters, nextDir, rowLimit);
                    }}
                    className="px-2 py-1 bg-zinc-950 border border-zinc-800 rounded text-[11px] font-mono text-zinc-300"
                  >
                    <option value="desc">Sort Highest First</option>
                    <option value="asc">Sort Lowest First</option>
                  </select>
                </div>

                <select
                  value={rowLimit}
                  onChange={(e) => {
                    const nextLim = Number(e.target.value);
                    setRowLimit(nextLim);
                    runBuilderState(groupByCols, metrics, filters, sortDir, nextLim);
                  }}
                  className="px-2 py-1 bg-zinc-950 border border-zinc-800 rounded text-[11px] font-mono text-zinc-300"
                >
                  <option value={25}>Show 25 rows</option>
                  <option value={50}>Show 50 rows</option>
                  <option value={100}>Show 100 rows</option>
                </select>
              </div>

              <button
                type="button"
                disabled={isLoading}
                onClick={() => runBuilderState()}
                className="px-3.5 py-1.5 rounded-lg bg-zinc-100 hover:bg-white disabled:opacity-50 text-zinc-950 font-semibold text-xs font-mono transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                {isLoading ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <TableIcon className="w-3.5 h-3.5" />
                )}
                <span>Update Table</span>
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs font-mono text-rose-300">
            {error}
          </div>
        )}
      </div>

      {/* PART 3: Interactive Results Table + Action Bar */}
      {result && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 space-y-3">
          {/* Plain-English Takeaway Banner */}
          {result.explanation && (
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs font-mono text-emerald-200 flex items-center justify-between gap-3">
              <span>{result.explanation}</span>
              <span className="text-[11px] text-emerald-400 shrink-0">
                {safeLocale(result.row_count, "0")} rows
              </span>
            </div>
          )}

          {/* Action Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={handleTurnIntoChart}
                className="px-3 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300 font-semibold text-xs font-mono transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                <BarChart3 className="w-3.5 h-3.5" />
                <span>Turn Table into Chart</span>
              </button>

              <button
                type="button"
                onClick={handleExportCsv}
                className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-zinc-200 text-xs font-mono transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                <Download className="w-3.5 h-3.5 text-cyan-400" />
                <span>Download CSV</span>
              </button>
            </div>

            <button
              type="button"
              onClick={() => setShowAdvancedSql((v) => !v)}
              className="px-2.5 py-1 rounded-md bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-[11px] font-mono text-zinc-400 hover:text-zinc-200 transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <Code2 className="w-3.5 h-3.5" />
              <span>Advanced: View Generated Query</span>
              {showAdvancedSql ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
            </button>
          </div>

          {/* Collapsible Advanced SQL Drawer (Hidden by Default) */}
          {showAdvancedSql && (
            <div className="p-3 rounded-lg bg-zinc-900/80 border border-zinc-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono uppercase text-zinc-400">
                  Underlying Vectorized DuckDB Query (Power View)
                </span>
                <button
                  type="button"
                  disabled={isLoading || !editableSql.trim()}
                  onClick={() =>
                    executePayload({
                      mode: "sql",
                      sql: editableSql,
                      limit: rowLimit,
                    })
                  }
                  className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[10px] font-mono text-cyan-300 border border-zinc-700 cursor-pointer"
                >
                  Run Edited SQL
                </button>
              </div>
              <textarea
                value={editableSql}
                onChange={(e) => setEditableSql(e.target.value)}
                rows={4}
                className="w-full p-2.5 bg-zinc-950 border border-zinc-800 rounded text-[11px] text-zinc-200 font-mono focus:outline-none focus:border-cyan-500"
              />
            </div>
          )}

          {/* Data Grid */}
          <div className="overflow-x-auto border border-zinc-800 rounded-lg max-h-96">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-zinc-900 sticky top-0 border-b border-zinc-800 z-10">
                <tr>
                  <th className="py-2.5 px-3 font-semibold text-zinc-500 w-10 text-center">
                    #
                  </th>
                  {result.columns.map((c) => (
                    <th key={c} className="py-2.5 px-3 font-semibold text-zinc-200">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {result.rows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={result.columns.length + 1}
                      className="py-8 text-center text-zinc-500"
                    >
                      No matching rows found for the current criteria.
                    </td>
                  </tr>
                ) : (
                  result.rows.map((row, i) => (
                    <tr key={i} className="hover:bg-zinc-900/40 transition-colors">
                      <td className="py-2 px-3 text-zinc-600 text-center text-[11px]">
                        {i + 1}
                      </td>
                      {row.map((val, cellIdx) => (
                        <td
                          key={cellIdx}
                          className="py-2 px-3 text-zinc-300 truncate max-w-[240px]"
                        >
                          {val !== null && val !== undefined ? (
                            typeof val === "number" ? (
                              val.toLocaleString(undefined, { maximumFractionDigits: 4 })
                            ) : (
                              String(val)
                            )
                          ) : (
                            <span className="text-zinc-600 italic">null</span>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
