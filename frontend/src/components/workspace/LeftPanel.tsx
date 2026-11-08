"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Columns,
  Hash,
  Type,
  Calendar,
  Layers,
  Sparkles,
  Link2,
  Trash2,
  ChevronDown,
  ChevronRight,
  Brain,
} from "lucide-react";
import { api } from "@/lib/api";
import { AnalysisMemory, LabOverviewResponse, UserFile } from "@/lib/types";
import { useWorkspaceStore } from "@/store/useWorkspaceStore";

interface LeftPanelProps {
  overview: LabOverviewResponse | null;
  fileId: string;
}

export function LeftPanel({ overview, fileId }: LeftPanelProps) {
  const {
    selectedJoinFileIds,
    toggleJoinFileId,
    injectArtifact,
  } = useWorkspaceStore();

  const [workspaceFiles, setWorkspaceFiles] = useState<UserFile[]>([]);
  const [memories, setMemories] = useState<AnalysisMemory[]>([]);
  const [isSchemaOpen, setIsSchemaOpen] = useState(true);
  const [isJoinsOpen, setIsJoinsOpen] = useState(true);
  const [isMemoriesOpen, setIsMemoriesOpen] = useState(false);

  useEffect(() => {
    loadSidebarData();
  }, [fileId]);

  const loadSidebarData = async () => {
    try {
      const [files, mems] = await Promise.all([
        api.datasets.list().catch(() => []),
        api.memory.list(fileId).catch(() => []),
      ]);
      setWorkspaceFiles(files.filter((f) => f.id !== fileId));
      setMemories(mems);
    } catch (err) {
      console.error("Failed to load left panel data:", err);
    }
  };

  const handleDeleteMemory = async (e: React.MouseEvent, memoryId: string) => {
    e.stopPropagation();
    try {
      await api.memory.delete(memoryId);
      setMemories((prev) => prev.filter((m) => m.id !== memoryId));
    } catch (err) {
      console.error("Failed to delete memory:", err);
    }
  };

  const columns = overview?.schema?.columns || {};

  return (
    <aside className="w-72 border-r border-zinc-800/80 bg-zinc-950/70 flex flex-col h-full overflow-hidden select-none">
      {/* Top Header */}
      <div className="p-4 border-b border-zinc-800/80 flex items-center justify-between">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Dashboard</span>
        </Link>
        <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
          RAM CACHED
        </span>
      </div>

      {/* Dataset Overview Summary */}
      <div className="p-4 border-b border-zinc-800/80 space-y-1">
        <h2
          className="text-sm font-semibold text-white truncate"
          title={overview?.filename || "Dataset"}
        >
          {overview?.filename || "Loading schema..."}
        </h2>
        <div className="flex items-center gap-3 text-[11px] font-mono text-zinc-400">
          <span>{overview?.row_count?.toLocaleString() ?? 0} Rows</span>
          <span>•</span>
          <span>{overview?.column_count ?? 0} Columns</span>
        </div>
      </div>

      {/* Accordion Sections */}
      <div className="flex-1 overflow-y-auto divide-y divide-zinc-800/60 text-xs">
        {/* Section 1: Columns Schema Explorer */}
        <div>
          <button
            onClick={() => setIsSchemaOpen(!isSchemaOpen)}
            className="w-full px-4 py-3 flex items-center justify-between text-zinc-300 hover:bg-zinc-900/50 transition-colors font-mono font-medium"
          >
            <span className="flex items-center gap-2">
              <Columns className="w-3.5 h-3.5 text-emerald-400" />
              Column Schema ({Object.keys(columns).length})
            </span>
            {isSchemaOpen ? (
              <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />
            )}
          </button>

          {isSchemaOpen && (
            <div className="px-3 pb-3 space-y-1">
              {Object.entries(columns).map(([colName, rawMeta]) => {
                const meta = rawMeta as { type?: string; dtype?: string };
                const profile = overview?.profile?.columns?.[colName];
                const typeStr = (meta?.type || meta?.dtype || "text").toUpperCase();
                const isNumeric =
                  typeStr.includes("INT") ||
                  typeStr.includes("FLOAT") ||
                  typeStr.includes("DOUBLE") ||
                  typeStr.includes("NUMERIC");
                const isDate = typeStr.includes("TIME") || typeStr.includes("DATE");

                return (
                  <div
                    key={colName}
                    className="p-2 rounded-lg hover:bg-zinc-900/70 border border-transparent hover:border-zinc-800 flex items-center justify-between gap-2 group transition-all"
                  >
                    <div className="flex items-center gap-2 truncate">
                      {isNumeric ? (
                        <Hash className="w-3 h-3 text-cyan-400 shrink-0" />
                      ) : isDate ? (
                        <Calendar className="w-3 h-3 text-amber-400 shrink-0" />
                      ) : (
                        <Type className="w-3 h-3 text-emerald-400 shrink-0" />
                      )}
                      <span className="text-zinc-200 font-mono text-xs truncate" title={colName}>
                        {colName}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {profile && profile.null_percentage > 0 && (
                        <span className="text-[10px] font-mono text-rose-400 bg-rose-500/10 px-1 rounded">
                          {profile.null_percentage.toFixed(0)}% null
                        </span>
                      )}
                      <span className="text-[9px] font-mono text-zinc-500 uppercase">
                        {typeStr.split("(")[0]}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Section 2: Multi-File Relational Joins */}
        <div>
          <button
            onClick={() => setIsJoinsOpen(!isJoinsOpen)}
            className="w-full px-4 py-3 flex items-center justify-between text-zinc-300 hover:bg-zinc-900/50 transition-colors font-mono font-medium"
          >
            <span className="flex items-center gap-2">
              <Link2 className="w-3.5 h-3.5 text-cyan-400" />
              Multi-File SQL Joins ({selectedJoinFileIds.length})
            </span>
            {isJoinsOpen ? (
              <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />
            )}
          </button>

          {isJoinsOpen && (
            <div className="px-3 pb-3 space-y-1.5">
              <p className="text-[11px] text-zinc-500 font-mono px-1">
                Select datasets to mount into the DuckDB query sandbox for relational joins:
              </p>
              {workspaceFiles.length === 0 ? (
                <div className="text-[11px] text-zinc-600 font-mono p-2">
                  No other datasets uploaded.
                </div>
              ) : (
                workspaceFiles.map((wf) => {
                  const isChecked = selectedJoinFileIds.includes(wf.id);
                  return (
                    <label
                      key={wf.id}
                      className={`flex items-center gap-2.5 p-2 rounded-lg cursor-pointer border transition-colors ${
                        isChecked
                          ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-300"
                          : "border-zinc-800/80 hover:bg-zinc-900/60 text-zinc-400"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleJoinFileId(wf.id)}
                        className="rounded border-zinc-700 text-cyan-500 focus:ring-0 bg-zinc-900"
                      />
                      <span className="font-mono text-xs truncate flex-1" title={wf.display_name}>
                        {wf.display_name}
                      </span>
                    </label>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* Section 3: Episodic Memory */}
        <div>
          <button
            onClick={() => setIsMemoriesOpen(!isMemoriesOpen)}
            className="w-full px-4 py-3 flex items-center justify-between text-zinc-300 hover:bg-zinc-900/50 transition-colors font-mono font-medium"
          >
            <span className="flex items-center gap-2">
              <Brain className="w-3.5 h-3.5 text-emerald-400" />
              Episodic Memory ({memories.length})
            </span>
            {isMemoriesOpen ? (
              <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />
            )}
          </button>

          {isMemoriesOpen && (
            <div className="px-3 pb-3 space-y-2">
              <p className="text-[11px] text-zinc-500 font-mono px-1">
                Recalled findings from pgvector semantic memory:
              </p>
              {memories.length === 0 ? (
                <div className="text-[11px] text-zinc-600 font-mono p-2">
                  No saved discoveries yet. Ask questions in chat to persist insights.
                </div>
              ) : (
                memories.map((m) => (
                  <div
                    key={m.id}
                    onClick={() => {
                      if (m.plotly_spec_json) {
                        injectArtifact({ type: "chart", data: m.plotly_spec_json });
                      }
                    }}
                    className="p-2.5 rounded-lg border border-zinc-800 bg-zinc-900/60 hover:border-zinc-700 cursor-pointer space-y-1 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono text-emerald-400 uppercase">
                        {m.agent_type}
                      </span>
                      <button
                        onClick={(e) => handleDeleteMemory(e, m.id)}
                        className="text-zinc-500 hover:text-rose-400 transition-colors"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                    <p className="text-xs text-zinc-200 line-clamp-2">{m.finding_text}</p>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

