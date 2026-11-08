"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Database,
  Cpu,
  BrainCircuit,
  ShieldCheck,
  Activity,
  Layers,
  Sparkles,
  BarChart3,
  Bot,
} from "lucide-react";
import { DataCore3DScene } from "@/components/spatial/DataCore3DScene";
import { TiltCard3D } from "@/components/spatial/TiltCard3D";
import { api } from "@/lib/api";

export default function LandingPage() {
  const router = useRouter();
  const [isGuestLoading, setIsGuestLoading] = useState(false);

  const handleGuestAccess = async () => {
    try {
      setIsGuestLoading(true);
      await api.auth.guest();
      router.push("/dashboard");
    } catch (err) {
      console.error("Guest login failed:", err);
      router.push("/login");
    } finally {
      setIsGuestLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#09090B] text-zinc-100 flex flex-col justify-between selection:bg-emerald-500/20 selection:text-emerald-300">
      {/* Top Navigation */}
      <header className="border-b border-zinc-800/80 bg-zinc-950/70 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
              <Database className="w-4 h-4 text-emerald-400" />
            </div>
            <span className="font-mono text-base font-bold tracking-tight text-white">
              DataMind<span className="text-emerald-400">.v2</span>
            </span>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={handleGuestAccess}
              disabled={isGuestLoading}
              className="text-xs font-mono text-zinc-400 hover:text-white px-3 py-1.5 rounded-md border border-zinc-800 hover:border-zinc-700 transition-colors"
            >
              {isGuestLoading ? "Provisioning..." : "Quick Guest Access"}
            </button>
            <Link
              href="/login"
              className="text-xs font-mono text-zinc-300 hover:text-white transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="text-xs font-mono bg-emerald-500 hover:bg-emerald-600 text-black font-semibold px-3.5 py-1.5 rounded-md transition-all shadow-lg shadow-emerald-500/10"
            >
              Get Started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="max-w-7xl mx-auto px-6 pt-16 pb-20">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            {/* Left Column: Headlines & Actions */}
            <div className="lg:col-span-7 space-y-6">
              {/* Telemetry Badges */}
              <div className="flex flex-wrap gap-2 items-center">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border border-emerald-500/20 bg-emerald-500/5 text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  ENGINE // DUCKDB 1.1 + PARQUET
                </span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border border-cyan-500/20 bg-cyan-500/5 text-cyan-400">
                  <Cpu className="w-3 h-3" />
                  COGNITION // 3-TIER AGENTS
                </span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border border-zinc-700 bg-zinc-900/60 text-zinc-300">
                  <ShieldCheck className="w-3 h-3 text-emerald-400" />
                  OWASP LEVEL-2
                </span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white leading-[1.1]">
                Autonomous Tabular Intelligence & Multi-Agent Analytics
              </h1>

              <p className="text-base sm:text-lg text-zinc-400 leading-relaxed max-w-2xl">
                Vectorized DuckDB in-process execution meets bounded LangGraph multi-agent loops.
                Ingest CSV, Excel, or Parquet lakes and extract production-grade forensic diagnostics,
                interactive 3D charts, and automated ML pipelines in sub-second cycles.
              </p>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-4 pt-2">
                <Link
                  href="/register"
                  className="inline-flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-black font-semibold text-sm px-5 py-2.5 rounded-lg transition-all shadow-xl shadow-emerald-500/20"
                >
                  Launch Workspace
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <button
                  onClick={handleGuestAccess}
                  disabled={isGuestLoading}
                  className="inline-flex items-center gap-2 border border-zinc-800 hover:border-zinc-700 bg-zinc-900/80 hover:bg-zinc-800 text-zinc-200 text-sm px-5 py-2.5 rounded-lg transition-colors font-mono"
                >
                  <Bot className="w-4 h-4 text-emerald-400" />
                  {isGuestLoading ? "Provisioning Sandbox..." : "Instant Guest Demo"}
                </button>
              </div>

              {/* Live Spec Telemetry */}
              <div className="pt-6 border-t border-zinc-800/80 grid grid-cols-3 gap-4 text-xs font-mono">
                <div>
                  <span className="text-zinc-500 block uppercase">Query Latency</span>
                  <span className="text-zinc-200 font-semibold text-sm">&lt; 12ms</span>
                </div>
                <div>
                  <span className="text-zinc-500 block uppercase">Throughput</span>
                  <span className="text-zinc-200 font-semibold text-sm">500,000 Rows/sec</span>
                </div>
                <div>
                  <span className="text-zinc-500 block uppercase">Agent Architecture</span>
                  <span className="text-zinc-200 font-semibold text-sm">3-Tier Bounded</span>
                </div>
              </div>
            </div>

            {/* Right Column: Spatial 3D Data Core Canvas */}
            <div className="lg:col-span-5 h-[440px] sm:h-[500px]">
              <DataCore3DScene />
            </div>
          </div>
        </section>

        {/* 3D Bento Grid Architecture Section */}
        <section className="max-w-7xl mx-auto px-6 py-20 border-t border-zinc-800/80">
          <div className="mb-12">
            <h2 className="text-xs font-mono uppercase tracking-widest text-emerald-400 mb-2">
              System Architecture
            </h2>
            <p className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Built for High-Stakes Quantitative Analysis
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Bento Card 1: DuckDB */}
            <TiltCard3D className="p-6 h-full flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-4">
                  <Database className="w-5 h-5 text-emerald-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  Vectorized Parquet Engine
                </h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  In-process DuckDB executes analytical SQL directly on columnar Parquet slices.
                  Multi-file relational joins occur in RAM without cloud data egress.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs font-mono text-zinc-500">
                <span>DUCKDB 1.1</span>
                <span className="text-emerald-400">ZERO EGRESS</span>
              </div>
            </TiltCard3D>

            {/* Bento Card 2: 3-Tier Multi-Agent */}
            <TiltCard3D className="p-6 h-full flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mb-4">
                  <BrainCircuit className="w-5 h-5 text-cyan-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  3-Tier Cognitive Brain
                </h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  Tier 1 delivers instant SQL (&lt;100ms). Tier 2 produces forensic diagnostics.
                  Tier 3 orchestrates LangGraph multi-step hypothesis testing and auto-remediation.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs font-mono text-zinc-500">
                <span>LANGGRAPH</span>
                <span className="text-cyan-400">BOUNDED LOOPS</span>
              </div>
            </TiltCard3D>

            {/* Bento Card 3: Autonomous AutoML */}
            <TiltCard3D className="p-6 h-full flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mb-4">
                  <Activity className="w-5 h-5 text-amber-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  Autonomous AutoML Lab
                </h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  Diagnoses task formulation, handles class imbalances, runs 5-fold cross-validation,
                  and serves model leaderboards with feature importance matrices.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs font-mono text-zinc-500">
                <span>SCIKIT-LEARN</span>
                <span className="text-amber-400">CV-OPTIMIZED</span>
              </div>
            </TiltCard3D>

            {/* Bento Card 4: Forensic Quality */}
            <TiltCard3D className="p-6 h-full flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center mb-4">
                  <ShieldCheck className="w-5 h-5 text-rose-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  Forensic Data Diagnostics
                </h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  Automatically flags null pattern shifts, duplicate rows, skewness, Benford&apos;s Law
                  deviations, and suggests actionable remediation recipes.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs font-mono text-zinc-500">
                <span>FORENSIC SCAN</span>
                <span className="text-rose-400">HEALTH SCORE</span>
              </div>
            </TiltCard3D>

            {/* Bento Card 5: Self-Learning Epodic Memory */}
            <TiltCard3D className="p-6 h-full flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-4">
                  <Layers className="w-5 h-5 text-emerald-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  Epodic Semantic Memory
                </h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  PostgreSQL pgvector stores analytical findings, query patterns, and user feedback
                  to continuously improve future agent reasoning.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs font-mono text-zinc-500">
                <span>PGVECTOR</span>
                <span className="text-emerald-400">SEMANTIC RECALL</span>
              </div>
            </TiltCard3D>

            {/* Bento Card 6: OWASP Top-10 Hardened */}
            <TiltCard3D className="p-6 h-full flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mb-4">
                  <Cpu className="w-5 h-5 text-blue-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  Enterprise Security Core
                </h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  Argon2id hashing, 5-attempt account lockout, rotating HttpOnly refresh tokens,
                  magic-byte upload filters, and strict tenant isolation.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs font-mono text-zinc-500">
                <span>ARGON2ID</span>
                <span className="text-blue-400">ZERO TRUST</span>
              </div>
            </TiltCard3D>
          </div>
        </section>
      </main>

      {/* Industrial Footer */}
      <footer className="border-t border-zinc-800/80 bg-zinc-950 py-10 px-6">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-mono text-zinc-500">
          <div>
            DataMind v2 Platform // Built for Analytical Rigor
          </div>
          <div className="flex items-center gap-6">
            <Link href="/terms" className="hover:text-zinc-300 transition-colors">
              Terms of Service
            </Link>
            <Link href="/privacy" className="hover:text-zinc-300 transition-colors">
              Privacy Policy
            </Link>
            <Link href="/llms.txt" className="hover:text-zinc-300 transition-colors">
              llms.txt
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
