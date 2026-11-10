"use client";

import React from "react";
import { BarChart3, Play, RefreshCw } from "lucide-react";
import { LabChartType } from "@/lib/types";
import { PlotlyCanvas } from "./PlotlyCanvas";

interface EmbeddedPlotlyStudioProps {
  title: string;
  columns: string[];
  chartType: LabChartType;
  xCol: string;
  yCol: string;
  colorCol: string;
  chartSpec: Record<string, unknown> | null;
  isLoading: boolean;
  error: string | null;
  xLabel?: string;
  yLabel?: string;
  onChangeChartType: (t: LabChartType) => void;
  onChangeXCol: (col: string) => void;
  onChangeYCol: (col: string) => void;
  onChangeColorCol: (col: string) => void;
  onGenerate: () => void;
}

export function EmbeddedPlotlyStudio({
  title,
  columns,
  chartType,
  xCol,
  yCol,
  colorCol,
  chartSpec,
  isLoading,
  error,
  xLabel = "Horizontal Axis (Group / Category)",
  yLabel = "Vertical Axis (Value to Measure)",
  onChangeChartType,
  onChangeXCol,
  onChangeYCol,
  onChangeColorCol,
  onGenerate,
}: EmbeddedPlotlyStudioProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <span className="text-xs font-mono font-semibold text-zinc-200 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-emerald-400" />
            {title}
          </span>

          <button
            type="button"
            onClick={onGenerate}
            disabled={isLoading}
            className="px-4 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-black font-semibold text-xs font-mono transition-colors flex items-center gap-1.5 shadow-sm"
          >
            {isLoading ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5 fill-black" />
            )}
            <span>Update Chart</span>
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-3 border-t border-zinc-800/80 font-mono text-xs">
          <div>
            <label className="block text-[10px] text-zinc-400 uppercase mb-1">
              Chart Style
            </label>
            <select
              value={chartType}
              onChange={(e) => onChangeChartType(e.target.value as LabChartType)}
              className="w-full px-2.5 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="bar">Bar Chart</option>
              <option value="scatter">Scatter Plot</option>
              <option value="line">Line Trend</option>
              <option value="box">Box Plot</option>
              <option value="histogram">Histogram</option>
              <option value="distribution">Distribution</option>
              <option value="heatmap">Heatmap</option>
              <option value="correlation">Correlation Matrix</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] text-zinc-400 uppercase mb-1">
              {xLabel}
            </label>
            <select
              value={xCol}
              onChange={(e) => onChangeXCol(e.target.value)}
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
              {yLabel}
            </label>
            <select
              value={yCol}
              onChange={(e) => onChangeYCol(e.target.value)}
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
              Color Grouping (Optional)
            </label>
            <select
              value={colorCol}
              onChange={(e) => onChangeColorCol(e.target.value)}
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

        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs font-mono text-rose-300">
            {error}
          </div>
        )}
      </div>

      {chartSpec ? (
        <PlotlyCanvas
          spec={chartSpec as any}
          title={`${chartType.toUpperCase()}: ${xCol || "Auto"}${yCol ? ` vs ${yCol}` : ""}`}
        />
      ) : (
        <div className="w-full h-80 rounded-xl border border-zinc-800 bg-zinc-950/40 flex flex-col items-center justify-center text-xs font-mono text-zinc-500 space-y-2">
          <BarChart3 className="w-8 h-8 text-zinc-700" />
          <p>Select dimensions above and click &quot;Generate Chart&quot;</p>
        </div>
      )}
    </div>
  );
}

