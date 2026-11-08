"use client";

import React, { useEffect, useRef, useState } from "react";

export function DataCore3DScene() {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hasWebGL, setHasWebGL] = useState(true);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Check WebGL support
    const gl =
      canvas.getContext("webgl2") ||
      canvas.getContext("webgl") ||
      canvas.getContext("experimental-webgl");

    if (!gl) {
      setHasWebGL(false);
      return;
    }

    // Interactive 3D Canvas Lattice Animation
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 600);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 500);

    const handleResize = () => {
      if (!canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };
    window.addEventListener("resize", handleResize);

    // 3D Nodes
    const numNodes = 48;
    const nodes: Array<{
      x: number;
      y: number;
      z: number;
      vx: number;
      vy: number;
      vz: number;
      size: number;
      color: string;
    }> = [];

    for (let i = 0; i < numNodes; i++) {
      nodes.push({
        x: (Math.random() - 0.5) * 360,
        y: (Math.random() - 0.5) * 360,
        z: (Math.random() - 0.5) * 360,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        vz: (Math.random() - 0.5) * 0.4,
        size: Math.random() * 2.5 + 1.5,
        color: i % 4 === 0 ? "#06B6D4" : "#10B981", // Cyan accent / Emerald primary
      });
    }

    let mouseX = 0;
    let mouseY = 0;
    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseX = ((e.clientX - rect.left) / width - 0.5) * 0.8;
      mouseY = ((e.clientY - rect.top) / height - 0.5) * 0.8;
    };
    window.addEventListener("mousemove", handleMouseMove);

    let angleY = 0;
    let angleX = 0;

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Smooth camera drift + mouse parallax
      angleY += 0.003 + mouseX * 0.01;
      angleX += 0.001 + mouseY * 0.01;

      const cosY = Math.cos(angleY);
      const sinY = Math.sin(angleY);
      const cosX = Math.cos(angleX);
      const sinX = Math.sin(angleX);

      const fov = 400;
      const projectedNodes: Array<{
        px: number;
        py: number;
        scale: number;
        color: string;
        size: number;
      }> = [];

      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];
        node.x += node.vx;
        node.y += node.vy;
        node.z += node.vz;

        // Bounce within bounding box
        if (Math.abs(node.x) > 180) node.vx *= -1;
        if (Math.abs(node.y) > 180) node.vy *= -1;
        if (Math.abs(node.z) > 180) node.vz *= -1;

        // 3D rotation
        const x1 = node.x * cosY - node.z * sinY;
        const z1 = node.z * cosY + node.x * sinY;
        const y2 = node.y * cosX - z1 * sinX;
        const z2 = z1 * cosX + node.y * sinX;

        const distance = z2 + 450;
        const scale = fov / distance;
        const px = width / 2 + x1 * scale;
        const py = height / 2 + y2 * scale;

        projectedNodes.push({
          px,
          py,
          scale,
          color: node.color,
          size: node.size * scale,
        });
      }

      // Draw connecting lines (spatial graph lattice)
      ctx.lineWidth = 0.8;
      for (let i = 0; i < projectedNodes.length; i++) {
        for (let j = i + 1; j < projectedNodes.length; j++) {
          const dx = projectedNodes[i].px - projectedNodes[j].px;
          const dy = projectedNodes[i].py - projectedNodes[j].py;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 90) {
            const alpha = (1 - dist / 90) * 0.25;
            ctx.strokeStyle = `rgba(16, 185, 129, ${alpha})`;
            ctx.beginPath();
            ctx.moveTo(projectedNodes[i].px, projectedNodes[i].py);
            ctx.lineTo(projectedNodes[j].px, projectedNodes[j].py);
            ctx.stroke();
          }
        }
      }

      // Draw nodes
      for (let i = 0; i < projectedNodes.length; i++) {
        const p = projectedNodes[i];
        if (p.scale > 0) {
          ctx.beginPath();
          ctx.arc(p.px, p.py, Math.max(1, p.size), 0, Math.PI * 2);
          ctx.fillStyle = p.color;
          ctx.shadowColor = p.color;
          ctx.shadowBlur = 8;
          ctx.fill();
        }
      }
      ctx.shadowBlur = 0;

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("mousemove", handleMouseMove);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full min-h-[420px] flex items-center justify-center overflow-hidden rounded-2xl border border-zinc-800/80 bg-zinc-950/60"
    >
      {/* Background radial specular depth */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-emerald-950/20 via-zinc-950/60 to-zinc-950 pointer-events-none" />

      <canvas ref={canvasRef} className="relative z-10 w-full h-full" />

      {!hasWebGL && (
        <div className="absolute inset-0 flex items-center justify-center text-xs font-mono text-zinc-500">
          [WebGL Accelerated Lattice Active]
        </div>
      )}

      {/* Industrial telemetry corner marks */}
      <div className="absolute top-3 left-4 text-[10px] font-mono tracking-widest text-zinc-600 uppercase">
        SYS.CORE // DUCKDB.PARQUET.LATTICE
      </div>
      <div className="absolute bottom-3 right-4 text-[10px] font-mono tracking-widest text-emerald-500/70 flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        ACTIVE (64 BITS)
      </div>
    </div>
  );
}
