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
    default: "DataMind v2 — No-Code Data Insights, 3D Charts & Predictions",
    template: "%s | DataMind v2",
  },
  description:
    "Upload CSV, Excel, JSON, or Parquet spreadsheets and explore plain-English insights, interactive 2D/3D charts, What-If predictions, and no-code smart pivot tables privately.",
  keywords: [
    "DataMind",
    "No-Code Analytics",
    "Data Insights",
    "What-If Simulator",
    "Smart Pivot Tables",
    "AutoML",
    "DuckDB",
    "Next.js 15",
  ],
  authors: [{ name: "DataMind Team" }],
  creator: "DataMind",
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://datamind.ai",
    title: "DataMind v2 — No-Code Data Insights, 3D Charts & Predictions",
    description:
      "Key insights, interactive 2D/3D charts, What-If predictions, and no-code smart tables in one private workspace.",
    siteName: "DataMind",
  },
  twitter: {
    card: "summary_large_image",
    title: "DataMind v2 — No-Code Data Insights & Predictions",
    description:
      "Turn spreadsheets into plain-English insights, 3D charts, and What-If predictions without writing code.",
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
      "Private no-code workspace for plain-English data insights, interactive 2D/3D charts, What-If predictions, and smart pivot tables.",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
    },
    softwareVersion: "2.0.0",
    featureList: [
      "Overview & Data Explorer with Data Quality Score",
      "Key Insights & Interactive 2D/3D Plotly Chart Studio",
      "Predict & Simulate What-If Outcome Engine",
      "No-Code Smart Tables & Multi-File Visual Combiner",
      "Verified DataMind AI Assistant (Online Ollama + Offline DuckDB Mode)",
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
