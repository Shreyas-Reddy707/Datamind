"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Cpu, Database, HardDrive, Shield } from "lucide-react";

export default function SettingsPage() {
  const [memoryLimit, setMemoryLimit] = useState("512MB");
  const [threads, setThreads] = useState("2");
  const [enable3D, setEnable3D] = useState(true);

  return (
    <div className="min-h-screen bg-[#09090B] text-zinc-100 p-8 max-w-3xl mx-auto space-y-6">
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-2 text-xs font-mono text-zinc-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Dashboard
      </Link>

      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight text-white">Engine Settings</h1>
        <p className="text-xs font-mono text-zinc-400">
          DuckDB Vector Configuration &amp; Telemetry Limits
        </p>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-6 space-y-6 font-mono text-xs">
        <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
          <div>
            <span className="text-sm font-semibold text-white block">
              In-Memory Cache Ceiling
            </span>
            <span className="text-zinc-500 text-[11px]">
              Maximum RAM allocated per active DuckDB analytical worker
            </span>
          </div>
          <span className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-emerald-400 font-semibold">
            {memoryLimit}
          </span>
        </div>

        <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
          <div>
            <span className="text-sm font-semibold text-white block">
              Execution Threads
            </span>
            <span className="text-zinc-500 text-[11px]">
              Worker thread concurrency for Parquet scans
            </span>
          </div>
          <span className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-cyan-400 font-semibold">
            {threads} Threads
          </span>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-semibold text-white block">
              Hardware WebGL Acceleration
            </span>
            <span className="text-zinc-500 text-[11px]">
              Enable interactive 3D WebGL point cloud rendering in Plotly
            </span>
          </div>
          <input
            type="checkbox"
            checked={enable3D}
            onChange={(e) => setEnable3D(e.target.checked)}
            className="rounded border-zinc-700 text-emerald-500 focus:ring-0 bg-zinc-900 w-4 h-4"
          />
        </div>
      </div>
    </div>
  );
}
