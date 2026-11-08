import React from "react";

interface SpatialGlassPanelProps {
  children: React.ReactNode;
  className?: string;
  elevated?: boolean;
}

export function SpatialGlassPanel({
  children,
  className = "",
  elevated = false,
}: SpatialGlassPanelProps) {
  return (
    <div
      className={`relative rounded-xl border border-zinc-800/80 transition-all duration-300 ${
        elevated ? "glass-panel-elevated" : "glass-panel"
      } specular-top shadow-2xl shadow-black/60 ${className}`}
    >
      {children}
    </div>
  );
}

