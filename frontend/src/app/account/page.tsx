"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, User, Shield, Key, Building } from "lucide-react";
import { api } from "@/lib/api";
import { User as UserType } from "@/lib/types";

export default function AccountPage() {
  const [user, setUser] = useState<UserType | null>(null);

  useEffect(() => {
    api.auth.me().then(setUser).catch(console.error);
  }, []);

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

      <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-6 space-y-4 font-mono text-xs">
        <div className="flex items-center gap-3 pb-4 border-b border-zinc-800">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <User className="w-5 h-5" />
          </div>
          <div>
            <span className="text-sm font-semibold text-white block">
              {user?.email || "analyst@enterprise.com"}
            </span>
            <span className="text-zinc-500 text-[11px]">User ID: {user?.id}</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 pt-2">
          <div>
            <span className="text-zinc-500 block uppercase text-[10px]">Organization ID</span>
            <span className="text-zinc-200 font-semibold">{user?.org_id || "Personal"}</span>
          </div>
          <div>
            <span className="text-zinc-500 block uppercase text-[10px]">RBAC Role</span>
            <span className="text-emerald-400 font-semibold uppercase">{user?.role || "analyst"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

