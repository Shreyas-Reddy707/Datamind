"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function SettingsPage() {
  const [enable3D, setEnable3D] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem("datamind_enable_3d");
    if (saved !== null) {
      setEnable3D(saved === "true");
    }
  }, []);

  const handleToggle3D = (checked: boolean) => {
    setEnable3D(checked);
    localStorage.setItem("datamind_enable_3d", String(checked));
  };

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
              Allocated RAM per active DuckDB analytical worker (Server Configured)
            </span>
          </div>
          <span className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-emerald-400 font-semibold">
            512MB
          </span>
        </div>

        <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
          <div>
            <span className="text-sm font-semibold text-white block">
              Execution Threads
            </span>
            <span className="text-zinc-500 text-[11px]">
              Worker thread concurrency for Parquet scans (Server Configured)
            </span>
          </div>
          <span className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-cyan-400 font-semibold">
            2 Threads
          </span>
        </div>

        <div className="flex items-center justify-between">
          <label htmlFor="settings-webgl" className="cursor-pointer">
            <span className="text-sm font-semibold text-white block">
              Hardware WebGL Acceleration
            </span>
            <span className="text-zinc-500 text-[11px]">
              Enable interactive 3D WebGL point cloud rendering in Plotly
            </span>
          </label>
          <input
            id="settings-webgl"
            type="checkbox"
            checked={enable3D}
            onChange={(e) => handleToggle3D(e.target.checked)}
            className="rounded border-zinc-700 text-emerald-500 focus:ring-0 bg-zinc-900 w-4 h-4 cursor-pointer"
          />
        </div>
      </div>
    </div>
  );
}
