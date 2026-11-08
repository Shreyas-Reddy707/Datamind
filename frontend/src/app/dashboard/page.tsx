"use client";

import React, { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Database,
  Upload,
  FileSpreadsheet,
  Trash2,
  ExternalLink,
  LogOut,
  User as UserIcon,
  HardDrive,
  RefreshCw,
  AlertCircle,
  FileText,
  Search,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { User, UserFile } from "@/lib/types";
import { TiltCard3D } from "@/components/spatial/TiltCard3D";

export default function DashboardPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [user, setUser] = useState<User | null>(null);
  const [datasets, setDatasets] = useState<UserFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setIsLoading(true);
      const [userData, filesData] = await Promise.all([
        api.auth.me().catch(() => null),
        api.datasets.list().catch(() => []),
      ]);

      if (!userData) {
        router.push("/login");
        return;
      }

      setUser(userData);
      setDatasets(filesData);
    } catch (err) {
      console.error("Dashboard load failed:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    setUploadError(null);
    setUploadSuccess(null);

    // Frontend validation: 50MB size cap
    const MAX_SIZE = 50 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      setUploadError("File exceeds the 50MB maximum upload limit.");
      return;
    }

    // Check extension
    const validExts = [".csv", ".xlsx", ".xls", ".parquet"];
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!validExts.includes(ext)) {
      setUploadError("Unsupported format. Please upload CSV, Excel (.xlsx), or Parquet files.");
      return;
    }

    try {
      setIsUploading(true);
      const uploadedFile = await api.datasets.upload(file);
      setUploadSuccess(`Ingested "${uploadedFile.display_name}" successfully.`);
      await loadDashboardData();
    } catch (err) {
      if (err instanceof ApiError) {
        setUploadError(err.message || "Failed to process file.");
      } else {
        setUploadError("Upload failed. Verify server connection.");
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (fileId: string, displayName: string) => {
    if (!window.confirm(`Delete "${displayName}" from your workspace?`)) return;

    try {
      await api.datasets.delete(fileId);
      setDatasets((prev) => prev.filter((d) => d.id !== fileId));
    } catch (err) {
      console.error("Delete failed:", err);
      alert("Failed to delete dataset.");
    }
  };

  const handleLogout = async () => {
    await api.auth.logout();
    router.push("/login");
  };

  const filteredDatasets = datasets.filter((d) =>
    d.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    d.global_file.detected_domain?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-[#09090B] text-zinc-100 flex flex-col">
      {/* Top Industrial Header */}
      <header className="border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
                <Database className="w-4 h-4 text-emerald-400" />
              </div>
              <span className="font-mono text-base font-bold tracking-tight text-white">
                DataMind<span className="text-emerald-400">.v2</span>
              </span>
            </Link>
            <span className="hidden sm:inline-block text-zinc-600 font-mono text-xs">/</span>
            <span className="hidden sm:inline-block text-xs font-mono text-zinc-400">
              Workspace Dashboard
            </span>
          </div>

          <div className="flex items-center gap-4">
            {user && (
              <div className="flex items-center gap-2 text-xs font-mono text-zinc-300 bg-zinc-900 border border-zinc-800 px-3 py-1.5 rounded-lg">
                <UserIcon className="w-3.5 h-3.5 text-emerald-400" />
                <span className="max-w-[150px] truncate">{user.email}</span>
                <span className="text-zinc-600">|</span>
                <span className="text-zinc-400 uppercase text-[10px]">{user.role}</span>
              </div>
            )}
            <button
              onClick={handleLogout}
              className="p-2 text-zinc-400 hover:text-rose-400 hover:bg-zinc-900 rounded-lg transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-8 space-y-8">
        {/* Upload Zone */}
        <section>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              const file = e.dataTransfer.files?.[0];
              if (file) handleFileUpload(file);
            }}
            onClick={() => fileInputRef.current?.click()}
            className={`cursor-pointer relative rounded-2xl border-2 border-dashed p-8 text-center transition-all ${
              isDragging
                ? "border-emerald-500 bg-emerald-500/5"
                : "border-zinc-800 hover:border-zinc-700 bg-zinc-950/60"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls,.parquet"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFileUpload(file);
              }}
              className="hidden"
            />

            <div className="flex flex-col items-center justify-center space-y-3">
              <div className="w-12 h-12 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-emerald-400">
                {isUploading ? (
                  <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
                ) : (
                  <Upload className="w-6 h-6" />
                )}
              </div>

              <div>
                <p className="text-sm font-semibold text-zinc-200">
                  {isUploading
                    ? "Converting & Sandboxing Dataset into Parquet Lake..."
                    : "Drop tabular file here, or click to browse"}
                </p>
                <p className="text-xs font-mono text-zinc-500 mt-1">
                  SUPPORTS CSV, EXCEL (.xlsx), PARQUET // 50MB CAP // READ-ONLY ISOLATED
                </p>
              </div>
            </div>
          </div>

          {uploadError && (
            <div className="mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center gap-2 text-xs text-rose-300">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{uploadError}</span>
            </div>
          )}

          {uploadSuccess && (
            <div className="mt-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300">
              {uploadSuccess}
            </div>
          )}
        </section>

        {/* Datasets Section */}
        <section className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-emerald-400" />
                Workspace Datasets
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-400">
                  {datasets.length}
                </span>
              </h2>
              <p className="text-xs text-zinc-400 font-mono mt-0.5">
                Vectorized Parquet instances mounted in DuckDB memory
              </p>
            </div>

            {/* Search Input */}
            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search datasets..."
                className="w-full pl-9 pr-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 font-mono"
              />
            </div>
          </div>

          {isLoading ? (
            <div className="p-12 text-center text-xs font-mono text-zinc-500">
              [Loading Workspace Datasets...]
            </div>
          ) : filteredDatasets.length === 0 ? (
            <div className="p-12 text-center border border-zinc-800/80 rounded-2xl bg-zinc-950/40 space-y-2">
              <p className="text-sm font-semibold text-zinc-300">No datasets found</p>
              <p className="text-xs font-mono text-zinc-500">
                Upload a CSV, Excel, or Parquet file above to initiate automated analysis.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {filteredDatasets.map((dataset) => {
                const gf = dataset.global_file;
                const sizeKb = Math.round(gf.file_size_bytes / 1024);

                return (
                  <TiltCard3D key={dataset.id} className="p-5 flex flex-col justify-between">
                    <div>
                      <div className="flex items-start justify-between gap-2 mb-3">
                        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0">
                          <FileText className="w-4 h-4 text-emerald-400" />
                        </div>
                        <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded border border-zinc-800 bg-zinc-900 text-zinc-400">
                          {gf.detected_domain || "general"}
                        </span>
                      </div>

                      <h3
                        className="text-sm font-semibold text-white truncate mb-1"
                        title={dataset.display_name}
                      >
                        {dataset.display_name}
                      </h3>

                      <div className="grid grid-cols-2 gap-2 text-xs font-mono text-zinc-400 mt-4 pt-3 border-t border-zinc-800/80">
                        <div>
                          <span className="text-[10px] text-zinc-500 block uppercase">Rows</span>
                          <span className="text-zinc-200 font-semibold">
                            {gf.row_count?.toLocaleString() ?? "—"}
                          </span>
                        </div>
                        <div>
                          <span className="text-[10px] text-zinc-500 block uppercase">Columns</span>
                          <span className="text-zinc-200 font-semibold">
                            {gf.col_count ?? "—"}
                          </span>
                        </div>
                        <div>
                          <span className="text-[10px] text-zinc-500 block uppercase">Size</span>
                          <span className="text-zinc-200 font-semibold">{sizeKb} KB</span>
                        </div>
                        <div>
                          <span className="text-[10px] text-zinc-500 block uppercase">Format</span>
                          <span className="text-zinc-200 uppercase font-semibold">
                            {gf.original_format}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="mt-5 pt-4 border-t border-zinc-800/80 flex items-center justify-between">
                      <button
                        onClick={() => handleDelete(dataset.id, dataset.display_name)}
                        className="p-1.5 text-zinc-500 hover:text-rose-400 hover:bg-zinc-800 rounded transition-colors"
                        title="Delete Dataset"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>

                      <Link
                        href={`/workspace/${dataset.id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-black text-xs font-semibold font-mono transition-colors shadow-sm"
                      >
                        <span>Open in IDE</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </TiltCard3D>
                );
              })}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
