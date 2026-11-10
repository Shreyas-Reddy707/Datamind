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
              {/* Value Badges */}
              <div className="flex flex-wrap gap-2 items-center">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border border-emerald-500/20 bg-emerald-500/5 text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  ⚡ Instant Answers (&lt;25ms)
                </span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border border-cyan-500/20 bg-cyan-500/5 text-cyan-400">
                  <ShieldCheck className="w-3 h-3" />
                  🛡️ 100% Verified Columns (No Hallucinations)
                </span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border border-zinc-700 bg-zinc-900/60 text-zinc-300">
                  <BarChart3 className="w-3 h-3 text-emerald-400" />
                  📊 No-Code Charts, Tables &amp; Predictions
                </span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white leading-[1.1]">
                Turn Any Spreadsheet Into Clear Insights, Charts &amp; Predictions
              </h1>

              <p className="text-base sm:text-lg text-zinc-400 leading-relaxed max-w-2xl">
                Upload CSV, Excel, JSON, or Parquet files and explore your data in seconds without
                writing a single line of code. Discover hidden trends, build interactive 2D and 3D
                charts, test &quot;What-If&quot; prediction scenarios, and chat with your data privately.
              </p>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-4 pt-2">
                <Link
                  href="/register"
                  className="inline-flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-black font-semibold text-sm px-5 py-2.5 rounded-lg transition-all shadow-xl shadow-emerald-500/20"
                >
                  Create Free Account
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <button
                  onClick={handleGuestAccess}
                  disabled={isGuestLoading}
                  className="inline-flex items-center gap-2 border border-zinc-800 hover:border-zinc-700 bg-zinc-900/80 hover:bg-zinc-800 text-zinc-200 text-sm px-5 py-2.5 rounded-lg transition-colors font-mono cursor-pointer"
                >
                  <Bot className="w-4 h-4 text-emerald-400" />
                  {isGuestLoading ? "Opening Demo Workspace..." : "Try Instant Guest Demo"}
                </button>
              </div>

              {/* Plain-English Highlights */}
              <div className="pt-6 border-t border-zinc-800/80 grid grid-cols-3 gap-4 text-xs font-mono">
                <div>
                  <span className="text-zinc-500 block uppercase">Instant Speed</span>
                  <span className="text-zinc-200 font-semibold text-sm">&lt; 25ms Queries</span>
                </div>
                <div>
                  <span className="text-zinc-500 block uppercase">File Support</span>
                  <span className="text-zinc-200 font-semibold text-sm">CSV, Excel, Parquet</span>
                </div>
                <div>
                  <span className="text-zinc-500 block uppercase">Privacy</span>
                  <span className="text-zinc-200 font-semibold text-sm">Private Workspace</span>
                </div>
              </div>
            </div>

            {/* Right Column: Spatial 3D Data Core Canvas */}
            <div className="lg:col-span-5 h-[440px] sm:h-[500px]">
              <DataCore3DScene />
            </div>
          </div>
        </section>

        {/* 4 Core Workspace Capabilities */}
        <section className="max-w-7xl mx-auto px-6 py-20 border-t border-zinc-800/80">
          <div className="mb-12">
            <h2 className="text-xs font-mono uppercase tracking-widest text-emerald-400 mb-2">
              Inside Your Workspace
            </h2>
            <p className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Four No-Code Tools Built Around Your Files
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Card 1: Key Insights & Interactive 3D Charts */}
            <TiltCard3D className="p-6 h-full flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center mb-4">
                  <BarChart3 className="w-5 h-5 text-rose-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  Key Insights &amp; Interactive 3D Charts
                </h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  Automatically spots patterns, anomalies, and trends explained in plain English
                  (Background &rarr; What We Found &rarr; Data Proof &rarr; Next Step) alongside
                  interactive 2D and 3D charts on the same screen.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs font-mono text-zinc-500">
                <span>INSIGHTS &amp; CHARTS TAB</span>
                <span className="text-rose-400">2D &amp; 3D VISUALS</span>
              </div>
            </TiltCard3D>

            {/* Card 2: Predictions & What-If Simulator */}
            <TiltCard3D className="p-6 h-full flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mb-4">
                  <Activity className="w-5 h-5 text-amber-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  Predictions &amp; &quot;What-If&quot; Simulator
                </h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  Pick any column you want to predict (like cancellations, sales, or price). DataMind
                  tests multiple AI models automatically, highlights top drivers, and lets you move
                  sliders to simulate future outcomes.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs font-mono text-zinc-500">
                <span>PREDICT &amp; SIMULATE TAB</span>
                <span className="text-amber-400">LIVE SIMULATOR</span>
              </div>
            </TiltCard3D>

            {/* Card 3: No-Code Smart Tables & Multi-File Combiner */}
            <TiltCard3D className="p-6 h-full flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-4">
                  <Layers className="w-5 h-5 text-emerald-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  No-Code Smart Tables &amp; Multi-File Combiner
                </h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  Ask for any summary table in plain English, click visual filters and groupings, or
                  combine multiple uploaded files and Excel sheets without writing a single line of
                  SQL.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs font-mono text-zinc-500">
                <span>SMART TABLES &amp; PIVOT</span>
                <span className="text-emerald-400">NO SQL REQUIRED</span>
              </div>
            </TiltCard3D>

            {/* Card 4: Ask DataMind AI Assistant */}
            <TiltCard3D className="p-6 h-full flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mb-4">
                  <BrainCircuit className="w-5 h-5 text-cyan-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  Ask DataMind AI Assistant
                </h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  Chat with your data in plain language to get instant numbers and explanations, or
                  let the assistant switch tabs, build charts, and run predictions for you.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs font-mono text-zinc-500">
                <span>AI ASSISTANT DRAWER</span>
                <span className="text-cyan-400">VERIFIED ANSWERS</span>
              </div>
            </TiltCard3D>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800/80 bg-zinc-950 py-10 px-6">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-mono text-zinc-500">
          <div>
            DataMind v2 — Private No-Code Data Intelligence
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
