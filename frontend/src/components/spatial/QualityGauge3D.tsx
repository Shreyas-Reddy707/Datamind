"use client";

import React from "react";

interface QualityGauge3DProps {
  score?: number | null; // 0 to 100, or null/undefined if unavailable
  rowCount?: number;
  colCount?: number;
  nullPct?: number;
}

export function QualityGauge3D({
  score,
  rowCount,
  colCount,
  nullPct,
}: QualityGauge3DProps) {
  const isAvailable = score !== undefined && score !== null && !isNaN(score);
  const clampedScore = isAvailable ? Math.max(0, Math.min(100, Math.round(score))) : null;

  // Color selection
  let color = "#71717A"; // Zinc for unavailable
  let label = "Unavailable";
  let statusBadgeBg = "bg-zinc-800 text-zinc-400 border-zinc-700";

  if (clampedScore !== null) {
    if (clampedScore < 50) {
      color = "#F43F5E"; // Rose
      label = "Needs Cleansing";
      statusBadgeBg = "bg-rose-500/10 text-rose-400 border-rose-500/20";
    } else if (clampedScore < 80) {
      color = "#F59E0B"; // Amber
      label = "Adequate Quality";
      statusBadgeBg = "bg-amber-500/10 text-amber-400 border-amber-500/20";
    } else {
      color = "#10B981"; // Emerald
      label = "Production Grade";
      statusBadgeBg = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    }
  }

  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset =
    clampedScore !== null ? circumference - (clampedScore / 100) * circumference : circumference;

  return (
    <div className="flex flex-col items-center justify-center p-6 bg-zinc-900/60 border border-zinc-800 rounded-xl relative overflow-hidden">
      {/* Specular ambient top glow */}
      <div
        className="absolute -top-12 left-1/2 -translate-x-1/2 w-48 h-24 blur-3xl opacity-20 pointer-events-none rounded-full"
        style={{ backgroundColor: color }}
      />

      <div className="relative flex items-center justify-center">
        <svg className="w-36 h-36 transform -rotate-90">
          {/* Background Track */}
          <circle
            cx="72"
            cy="72"
            r={radius}
            stroke="#27272A"
            strokeWidth="8"
            fill="transparent"
          />
          {/* Animated Progress Arc */}
          <circle
            cx="72"
            cy="72"
            r={radius}
            stroke={color}
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="transparent"
            className="transition-all duration-1000 ease-out"
          />
        </svg>

        {/* Inner Score Readout */}
        <div className="absolute flex flex-col items-center justify-center text-center">
          <span className="text-3xl font-mono font-bold tracking-tight text-white">
            {clampedScore !== null ? clampedScore : "—"}
          </span>
          <span className="text-[10px] uppercase font-mono tracking-wider text-zinc-400">
            / 100
          </span>
        </div>
      </div>

      <div className="mt-4 flex flex-col items-center text-center gap-1">
        <span
          className={`px-2.5 py-0.5 text-xs font-medium rounded-full border ${statusBadgeBg}`}
        >
          {label}
        </span>
        <p className="text-xs text-zinc-400 mt-1">Dataset Health &amp; Integrity</p>
      </div>

      {/* Sub-metrics Breakdown */}
      {(rowCount !== undefined || colCount !== undefined || nullPct !== undefined) && (
        <div className="grid grid-cols-3 gap-2 w-full mt-5 pt-4 border-t border-zinc-800/80 text-center font-mono">
          <div>
            <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">
              Rows
            </span>
            <span className="text-xs font-semibold text-zinc-200">
              {rowCount?.toLocaleString() ?? "—"}
            </span>
          </div>
          <div>
            <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">
              Cols
            </span>
            <span className="text-xs font-semibold text-zinc-200">
              {colCount ?? "—"}
            </span>
          </div>
          <div>
            <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">
              Nulls
            </span>
            <span className="text-xs font-semibold text-zinc-200">
              {nullPct !== undefined && nullPct !== null ? `${nullPct.toFixed(1)}%` : "—"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
