"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import { ChatEngineStatus } from "@/lib/types";

export default function SettingsPage() {
  const [enable3D, setEnable3D] = useState(true);
  const [aiStatus, setAiStatus] = useState<ChatEngineStatus | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem("datamind_enable_3d");
    if (saved !== null) {
      setEnable3D(saved === "true");
    }
    api.chat
      .status()
      .then((res) => setAiStatus(res))
      .catch(() => setAiStatus(null));
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
        <h1 className="text-2xl font-bold tracking-tight text-white">Workspace Preferences</h1>
        <p className="text-xs font-mono text-zinc-400">
          Visual experience, local AI assistant status, and high-speed data processing
        </p>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-6 space-y-6 font-mono text-xs">
        <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
          <div>
            <span className="text-sm font-semibold text-white block">
              High-Speed Data Engine
            </span>
            <span className="text-zinc-500 text-[11px]">
              Powers instant filtering, smart tables, and chart generation across large files
            </span>
          </div>
          <span className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-emerald-400 font-semibold">
            Ready (Fast Mode)
          </span>
        </div>

        <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
          <div>
            <span className="text-sm font-semibold text-white block">
              Local AI Status
            </span>
            <span className="text-zinc-500 text-[11px]">
              {aiStatus?.online
                ? `Connected to private local AI (${aiStatus.model})`
                : "Running instant built-in data engine (start Ollama anytime for open-ended Q&A)"}
            </span>
          </div>
          <span
            className={`px-2.5 py-1 rounded bg-zinc-900 border font-semibold ${
              aiStatus?.online
                ? "border-emerald-500/30 text-emerald-400"
                : "border-amber-500/30 text-amber-300"
            }`}
          >
            {aiStatus ? (aiStatus.online ? "Local AI Online" : "Built-In Fast Engine") : "Checking..."}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <label htmlFor="settings-webgl" className="cursor-pointer">
            <span className="text-sm font-semibold text-white block">
              3D Visual Effects &amp; Smooth Animations
            </span>
            <span className="text-zinc-500 text-[11px]">
              Enable interactive 3D charts and depth animations across your workspace
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
