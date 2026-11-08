"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import { Box, Layers } from "lucide-react";

// Dynamically import Plotly with SSR disabled via factory
const Plot = dynamic<any>(
  async () => {
    const Plotly = await import("plotly.js-dist-min");
    const createPlotlyComponent = (await import("react-plotly.js/factory")).default;
    return createPlotlyComponent(Plotly.default || Plotly);
  },
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full min-h-[380px] flex items-center justify-center text-xs font-mono text-zinc-500 bg-zinc-950/60 rounded-xl border border-zinc-800">
        [Initializing WebGL &amp; Vector Canvas...]
      </div>
    ),
  }
);

interface PlotlyCanvasProps {
  spec: {
    data?: any[];
    layout?: Record<string, any>;
    config?: Record<string, any>;
  };
  title?: string;
}

export function PlotlyCanvas({ spec, title }: PlotlyCanvasProps) {
  const [is3DMode, setIs3DMode] = useState(false);

  if (!spec || !spec.data || spec.data.length === 0) {
    return (
      <div className="w-full h-full min-h-[380px] flex items-center justify-center text-xs font-mono text-zinc-500 bg-zinc-950/60 rounded-xl border border-zinc-800">
        No chart specification available. Select variables and generate a visualization.
      </div>
    );
  }

  // Clone and transform spec for 3D WebGL mode if requested
  const transformedData = spec.data.map((trace: any) => {
    if (is3DMode) {
      return {
        ...trace,
        type: "scatter3d",
        mode: trace.mode || "markers",
        z: trace.y || trace.x, // Map Z axis
        marker: {
          ...trace.marker,
          size: 4,
          opacity: 0.8,
        },
      };
    }
    return trace;
  });

  const mergedLayout = {
    autosize: true,
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    margin: { l: 45, r: 25, t: 35, b: 40 },
    font: {
      family: "var(--font-geist-mono), monospace",
      size: 11,
      color: "#A1A1AA",
    },
    xaxis: {
      gridcolor: "#27272A",
      zerolinecolor: "#3F3F46",
      tickfont: { color: "#71717A" },
      titlefont: { color: "#A1A1AA" },
    },
    yaxis: {
      gridcolor: "#27272A",
      zerolinecolor: "#3F3F46",
      tickfont: { color: "#71717A" },
      titlefont: { color: "#A1A1AA" },
    },
    ...(is3DMode
      ? {
          scene: {
            xaxis: { gridcolor: "#27272A", backgroundcolor: "#09090B", color: "#A1A1AA" },
            yaxis: { gridcolor: "#27272A", backgroundcolor: "#09090B", color: "#A1A1AA" },
            zaxis: { gridcolor: "#27272A", backgroundcolor: "#09090B", color: "#A1A1AA" },
          },
        }
      : {}),
    ...spec.layout,
  };

  const config = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"] as any,
    toImageButtonOptions: {
      format: "png" as const,
      filename: "datamind_chart_export",
      height: 700,
      width: 1000,
      scale: 2,
    },
    ...spec.config,
  } as any;

  return (
    <div className="w-full flex flex-col rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 relative overflow-hidden">
      {/* Top Header with 3D Toggle */}
      <div className="flex items-center justify-between pb-3 mb-2 border-b border-zinc-800/80">
        <span className="text-xs font-mono font-medium text-zinc-300 truncate">
          {title || "Analytical Projection"}
        </span>

        {/* 3D WebGL Toggle Switch */}
        <button
          onClick={() => setIs3DMode(!is3DMode)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-mono transition-colors border ${
            is3DMode
              ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400"
              : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200"
          }`}
          title="Toggle 3D WebGL Projection"
        >
          {is3DMode ? <Box className="w-3.5 h-3.5" /> : <Layers className="w-3.5 h-3.5" />}
          <span>{is3DMode ? "3D WebGL Active" : "2D Vector Mode"}</span>
        </button>
      </div>

      {/* Plot Canvas */}
      <div className="w-full h-[400px]">
        <Plot
          data={transformedData}
          layout={mergedLayout}
          config={config}
          style={{ width: "100%", height: "100%" }}
          useResizeHandler={true}
        />
      </div>
    </div>
  );
}
