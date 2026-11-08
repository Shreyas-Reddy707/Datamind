import React from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Privacy Policy | DataMind v2",
  description: "Privacy and telemetry policy for DataMind v2 analytical intelligence platform.",
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-[#09090B] text-zinc-100 flex flex-col justify-between py-12 px-6">
      <div className="max-w-3xl mx-auto w-full">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-emerald-400 transition-colors mb-8"
        >
          <ArrowLeft className="w-4 h-4" /> Back to DataMind
        </Link>

        <h1 className="text-3xl font-mono font-bold tracking-tight text-white mb-2">
          Privacy Policy
        </h1>
        <p className="text-sm font-mono text-zinc-400 mb-8">
          Effective: March 2025 // Strict Local-First & Zero Data Retention Options
        </p>

        <div className="space-y-8 text-sm leading-relaxed text-zinc-300">
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">1. Information Collection</h2>
            <p>
              We collect user account credentials (email and Argon2id hashed passwords), session
              identifiers, and dataset metadata strictly required to operate the analytical
              workspace. In guest mode, temporary anonymous sessions are deleted automatically after
              24 hours of inactivity.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">2. Processing of Datasets</h2>
            <p>
              Datasets uploaded to DataMind are processed using local-first in-process DuckDB instances.
              When multi-agent cognitive reasoning is initiated, only sanitized structural schemas,
              statistical summaries, and sample aggregations are passed to the language models. Raw
              tabular rows are never transmitted to external third-party model providers without
              explicit user consent.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">3. Security & Isolation</h2>
            <p>
              All stored analytical data is protected with read-only sandbox isolation, strict tenant
              separation, SHA-256 deduplicated file content hashing, and row-level access control.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">4. Cookies & Storage</h2>
            <p>
              We use strictly necessary HttpOnly cookies for session authentication and rotating
              refresh tokens. We do not use third-party tracking or advertising cookies.
            </p>
          </section>
        </div>
      </div>

      <footer className="mt-16 text-center text-xs font-mono text-zinc-500">
        DataMind v2 Platform // Security & Confidentiality Standard
      </footer>
    </div>
  );
}

