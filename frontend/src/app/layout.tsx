import type { Metadata, Viewport } from "next";
import "./globals.css";

export const viewport: Viewport = {
  themeColor: "#09090b",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://datamind.ai"),
  title: {
    default: "DataMind v2 — Multi-Agent Tabular Intelligence & AutoML",
    template: "%s | DataMind v2",
  },
  description:
    "High-performance analytical workspace powered by DuckDB, Apache Parquet, and a 3-tier multi-agent cognitive brain. Sub-millisecond queries and zero-config machine learning.",
  keywords: [
    "DataMind",
    "DuckDB",
    "AutoML",
    "Data Intelligence",
    "Tabular Analytics",
    "Multi-Agent",
    "FastAPI",
    "Next.js 15",
  ],
  authors: [{ name: "DataMind Team" }],
  creator: "DataMind",
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://datamind.ai",
    title: "DataMind v2 — Multi-Agent Tabular Intelligence & AutoML",
    description:
      "Vectorized Parquet analysis, forensic diagnostics, and multi-agent machine learning in one unified workspace.",
    siteName: "DataMind",
  },
  twitter: {
    card: "summary_large_image",
    title: "DataMind v2 — Multi-Agent Tabular Intelligence",
    description:
      "Vectorized Parquet analysis, forensic diagnostics, and multi-agent machine learning in one unified workspace.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "DataMind v2",
    operatingSystem: "All",
    applicationCategory: "BusinessApplication",
    description:
      "Autonomous tabular data intelligence, vectorized DuckDB analytics, and multi-agent AutoML workspace.",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
    },
    softwareVersion: "2.0.0",
    featureList: [
      "DuckDB in-process vectorized analytical SQL engine",
      "Sub-millisecond Apache Parquet data lake ingestion",
      "3-Tier bounded multi-agent reasoning with LangGraph",
      "Automated stratified machine learning benchmarking",
      "Self-learning epodic memory with pgvector embeddings",
    ],
  };

  return (
    <html lang="en" className="dark">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body
        className="antialiased font-sans bg-[#09090B] text-zinc-100 min-h-screen selection:bg-emerald-500/20 selection:text-emerald-300"
      >
        {children}
      </body>
    </html>
  );
}
