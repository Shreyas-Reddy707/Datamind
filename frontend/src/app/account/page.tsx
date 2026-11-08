"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, User, RefreshCw, AlertCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { User as UserType } from "@/lib/types";

export default function AccountPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserType | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    api.auth
      .me()
      .then((data) => {
        if (isMounted) {
          setUser(data);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setIsLoading(false);
        if (err instanceof ApiError && err.status === 401) {
          router.push("/login");
          return;
        }
        setErrorMsg(err.message || "Failed to load account profile.");
      });

    return () => {
      isMounted = false;
    };
  }, [router]);

  return (
    <div className="min-h-screen bg-[#09090B] text-zinc-100 p-8 max-w-3xl mx-auto space-y-6">
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-2 text-xs font-mono text-zinc-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Dashboard
      </Link>

      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight text-white">Account Profile</h1>
        <p className="text-xs font-mono text-zinc-400">
          OWASP Identity &amp; Tenant Credentials
        </p>
      </div>

      {isLoading && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-12 flex flex-col items-center justify-center space-y-3">
          <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
          <p className="text-xs font-mono text-zinc-400">Loading authenticated identity...</p>
        </div>
      )}

      {errorMsg && !isLoading && (
        <div className="p-4 rounded-xl border border-rose-500/20 bg-rose-500/10 flex items-center gap-2.5 text-xs font-mono text-rose-300">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {user && !isLoading && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-6 space-y-4 font-mono text-xs">
          <div className="flex items-center gap-3 pb-4 border-b border-zinc-800">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <User className="w-5 h-5" />
            </div>
            <div>
              <span className="text-sm font-semibold text-white block">
                {user.email}
              </span>
              <span className="text-zinc-500 text-[11px]">User ID: {user.id}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 pt-2">
            <div>
              <span className="text-zinc-500 block uppercase text-[10px]">Organization ID</span>
              <span className="text-zinc-200 font-semibold">{user.org_id}</span>
            </div>
            <div>
              <span className="text-zinc-500 block uppercase text-[10px]">RBAC Role</span>
              <span className="text-emerald-400 font-semibold uppercase">{user.role}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
