"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Database, Lock, Mail, ArrowRight, Bot, AlertCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGuestLoading, setIsGuestLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsLoading(true);

    try {
      await api.auth.login(email, password);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.errorCode === "ACCOUNT_LOCKED") {
          setErrorMsg("Account locked due to 5 consecutive failed attempts. Try again in 15 minutes.");
        } else {
          setErrorMsg(err.message || "Invalid email or password.");
        }
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Failed to connect to authentication service.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleGuest = async () => {
    setErrorMsg(null);
    setIsGuestLoading(true);
    try {
      await api.auth.guest();
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMsg(err.message);
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Failed to provision guest session.");
      }
    } finally {
      setIsGuestLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#09090B] flex flex-col justify-center items-center p-6 selection:bg-emerald-500/20 selection:text-emerald-300">
      {/* Background radial specular */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-emerald-500/5 blur-3xl rounded-full pointer-events-none" />

      <div className="w-full max-w-md relative z-10">
        {/* Logo Header */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2.5 mb-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
              <Database className="w-5 h-5 text-emerald-400" />
            </div>
            <span className="font-mono text-xl font-bold tracking-tight text-white">
              DataMind<span className="text-emerald-400">.v2</span>
            </span>
          </Link>
          <h1 className="text-xl font-semibold text-zinc-100">Sign in to workspace</h1>
          <p className="text-xs text-zinc-400 mt-1 font-mono">
            SECURE ANALYTICAL ACCESS // OWASP HARDENED
          </p>
        </div>

        {/* Login Card */}
        <div className="glass-panel rounded-2xl border border-zinc-800 p-8 shadow-2xl relative specular-top">
          {errorMsg && (
            <div className="mb-6 p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-start gap-2.5 text-xs text-rose-300">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label
                htmlFor="login-email"
                className="block text-xs font-mono text-zinc-400 uppercase tracking-wider mb-2"
              >
                Work Email
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  id="login-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="analyst@enterprise.com"
                  className="w-full pl-10 pr-4 py-2.5 bg-zinc-900/90 border border-zinc-800 rounded-lg text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors font-mono"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label
                  htmlFor="login-password"
                  className="block text-xs font-mono text-zinc-400 uppercase tracking-wider"
                >
                  Password
                </label>
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  id="login-password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-10 pr-4 py-2.5 bg-zinc-900/90 border border-zinc-800 rounded-lg text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors font-mono"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading || isGuestLoading}
              className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-black font-semibold text-sm rounded-lg transition-all shadow-lg shadow-emerald-500/20 flex items-center justify-center gap-2"
            >
              {isLoading ? "Authenticating..." : "Sign In"}
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-6 text-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-zinc-800" />
            </div>
            <span className="relative px-3 bg-zinc-950 text-[10px] uppercase font-mono tracking-wider text-zinc-500">
              Or Explore Instantly
            </span>
          </div>

          {/* 1-Click Guest Access */}
          <button
            type="button"
            onClick={handleGuest}
            disabled={isLoading || isGuestLoading}
            className="w-full py-2.5 bg-zinc-900 hover:bg-zinc-800 disabled:opacity-50 text-zinc-200 border border-zinc-800 rounded-lg text-sm transition-colors flex items-center justify-center gap-2 font-mono"
          >
            <Bot className="w-4 h-4 text-emerald-400" />
            {isGuestLoading ? "Provisioning Guest Session..." : "Continue as Guest"}
          </button>
        </div>

        {/* Footer Link */}
        <p className="text-center text-xs text-zinc-500 mt-6">
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            className="text-emerald-400 hover:underline font-mono"
          >
            Create Workspace Account
          </Link>
        </p>
      </div>
    </div>
  );
}

