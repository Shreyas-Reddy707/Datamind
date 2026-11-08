"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { LabOverviewResponse } from "@/lib/types";
import { useWorkspaceStore } from "@/store/useWorkspaceStore";
import { LeftPanel } from "@/components/workspace/LeftPanel";
import { CenterLab } from "@/components/workspace/CenterLab";
import { RightChat } from "@/components/workspace/RightChat";
import { Database, AlertCircle, RefreshCw } from "lucide-react";

export default function WorkspaceIdePage() {
  const params = useParams();
  const router = useRouter();
  const fileId = params?.fileId as string;

  const { setActiveFileId, setActiveFile } = useWorkspaceStore();
  const [overview, setOverview] = useState<LabOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!fileId) return;
    setActiveFileId(fileId);
    loadWorkspace();
  }, [fileId]);

  const loadWorkspace = async () => {
    try {
      setIsLoading(true);
      setErrorMsg(null);
      const [overviewData, fileData] = await Promise.all([
        api.lab.overview(fileId),
        api.datasets.get(fileId).catch(() => null),
      ]);
      setOverview(overviewData);
      if (fileData) setActiveFile(fileData);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          router.push("/login");
          return;
        }
        setErrorMsg(err.message || "Failed to load dataset overview.");
      } else {
        setErrorMsg("Failed to connect to DataMind workspace engine.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#09090B] flex flex-col items-center justify-center space-y-4">
        <div className="w-12 h-12 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-emerald-400">
          <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-zinc-200">
            Mounting Parquet Slice into DuckDB Memory...
          </p>
          <p className="text-xs font-mono text-zinc-500 mt-1">
            Setting memory limit: 512MB // Threads: 2 // Read-only isolated
          </p>
        </div>
      </div>
    );
  }

  if (errorMsg) {
    return (
      <div className="min-h-screen bg-[#09090B] flex flex-col items-center justify-center p-6">
        <div className="max-w-md w-full p-6 rounded-2xl border border-rose-500/30 bg-rose-500/5 text-center space-y-4">
          <AlertCircle className="w-10 h-10 text-rose-400 mx-auto" />
          <h2 className="text-base font-semibold text-white">Workspace Load Error</h2>
          <p className="text-xs font-mono text-rose-300">{errorMsg}</p>
          <button
            onClick={() => router.push("/dashboard")}
            className="px-4 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-300 hover:text-white"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-[#09090B] text-zinc-100">
      {/* 3-Pane Spatial IDE Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel: Schema & Joins (280px) */}
        <LeftPanel overview={overview} fileId={fileId} />

        {/* Center Lab: Health, Forensics, Plotly Studio, AutoML, SQL (Flex-1) */}
        <CenterLab overview={overview} fileId={fileId} />

        {/* Right Chat: 3-Tier Multi-Agent Streaming Assistant (384px) */}
        <RightChat fileId={fileId} />
      </div>
    </div>
  );
}

