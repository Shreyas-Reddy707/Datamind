"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Send,
  Bot,
  User as UserIcon,
  Sparkles,
  Zap,
  BrainCircuit,
  Cpu,
  Layers,
  ArrowUpRight,
  RefreshCw,
  X,
  Minus,
} from "lucide-react";
import { api } from "@/lib/api";
import { ChatMessage } from "@/lib/types";
import { useWorkspaceStore } from "@/store/useWorkspaceStore";

interface RightChatProps {
  fileId: string;
}

export function RightChat({ fileId }: RightChatProps) {
  const {
    chatMessages,
    setChatMessages,
    addChatMessage,
    isStreaming,
    setIsStreaming,
    streamBuffer,
    setStreamBuffer,
    appendStreamBuffer,
    currentAgentStep,
    setCurrentAgentStep,
    activeTier,
    setActiveTier,
    injectArtifact,
    isChatOpen,
    setIsChatOpen,
  } = useWorkspaceStore();

  const [inputMessage, setInputMessage] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadChatHistory();
  }, [fileId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, streamBuffer]);

  const loadChatHistory = async () => {
    try {
      const history = await api.chat.history(fileId);
      setChatMessages(history);
    } catch (err) {
      console.error("Failed to load chat history:", err);
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const query = textToSend || inputMessage;
    if (!query.trim() || isStreaming) return;

    setInputMessage("");

    // Add user message to state
    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      role: "user",
      message_text: query,
      created_at: new Date().toISOString(),
    };
    addChatMessage(userMsg);

    setIsStreaming(true);
    setStreamBuffer("");
    setCurrentAgentStep("Perceiving Query & Schema Constraints...");
    setActiveTier(1);

    let accumulatedText = "";
    let capturedArtifact: Record<string, unknown> | null = null;
    let hasSettled = false;
    const startTime = performance.now();

    const settleStream = () => {
      if (hasSettled) return;
      hasSettled = true;
      setIsStreaming(false);
      setStreamBuffer("");
      setCurrentAgentStep(null);
    };

    try {
      await api.chat.stream(fileId, query, {
        onToken: (token) => {
          accumulatedText += token;
          appendStreamBuffer(token);
        },
        onArtifact: (artifact) => {
          capturedArtifact = artifact;
        },
        onDone: () => {
          const latency = Math.round(performance.now() - startTime);
          const assistantMsg: ChatMessage = {
            id: `ast-${Date.now()}`,
            role: "assistant",
            message_text: accumulatedText,
            tier: activeTier || 1,
            latency_ms: latency,
            created_at: new Date().toISOString(),
            artifact: capturedArtifact
              ? {
                  type: (capturedArtifact.type as any) || "chart",
                  data: capturedArtifact,
                }
              : null,
          };
          addChatMessage(assistantMsg);
          settleStream();
        },
        onError: (err) => {
          console.error("Stream error:", err);
          const latency = Math.round(performance.now() - startTime);
          const fallbackText = accumulatedText.trim()
            ? `${accumulatedText}\n\n[Stream interrupted: ${err.message || "Connection error"}]`
            : `Failed to stream response: ${err.message || "An unexpected error occurred."}`;
          const assistantMsg: ChatMessage = {
            id: `ast-err-${Date.now()}`,
            role: "assistant",
            message_text: fallbackText,
            tier: activeTier || 1,
            latency_ms: latency,
            created_at: new Date().toISOString(),
          };
          addChatMessage(assistantMsg);
          settleStream();
        },
      });
    } catch (err: unknown) {
      console.error("Chat dispatch error:", err);
      const errorMessage =
        err instanceof Error ? err.message : "Server unreachable.";
      const assistantMsg: ChatMessage = {
        id: `ast-err-${Date.now()}`,
        role: "assistant",
        message_text: `Failed to dispatch query: ${errorMessage}`,
        tier: 1,
        created_at: new Date().toISOString(),
      };
      addChatMessage(assistantMsg);
    } finally {
      settleStream();
    }
  };

  const suggestions = [
    "What are the strongest correlations?",
    "Check Benford's Law anomaly deviations",
    "Auto-diagnose predictive targets",
    "List top 5 data quality risks",
  ];

  if (!isChatOpen) {
    return (
      <button
        onClick={() => setIsChatOpen(true)}
        className="fixed right-6 bottom-6 z-50 flex items-center gap-2.5 px-4 py-2.5 rounded-full bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold text-xs shadow-2xl shadow-emerald-500/30 border border-emerald-400/50 transition-all hover:scale-105 active:scale-95 font-mono cursor-pointer"
        title="Open AI Analyst Chat"
      >
        <Sparkles className="w-4 h-4 fill-zinc-950" />
        <span>💬 AI Analyst</span>
        {isStreaming && (
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
          </span>
        )}
      </button>
    );
  }

  return (
    <aside className="w-[420px] max-w-[92vw] fixed right-4 bottom-4 top-16 z-50 flex flex-col rounded-2xl border border-zinc-800 bg-zinc-950/95 backdrop-blur-xl shadow-2xl shadow-black/80 overflow-hidden animate-in fade-in slide-in-from-right-4 duration-200">
      {/* Chat Top Header */}
      <div className="p-3.5 border-b border-zinc-800/80 flex items-center justify-between select-none bg-zinc-900/60">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
            <BrainCircuit className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold text-white flex items-center gap-1.5">
              <span>Cognitive Brain</span>
              <span className="text-[10px] text-emerald-400 font-normal">v2</span>
            </h3>
            <span className="text-[10px] font-mono text-zinc-500">
              3-Tier LangGraph Multi-Agent
            </span>
          </div>
        </div>

        {/* Tier Status Indicator & Controls */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono border border-zinc-800 bg-zinc-900">
            <Zap className="w-3 h-3 text-emerald-400" />
            <span className="text-zinc-300">
              {activeTier === 3 ? "Tier 3: LRM" : activeTier === 2 ? "Tier 2: Analyst" : "Tier 1: Instant"}
            </span>
          </div>
          <button
            onClick={() => setIsChatOpen(false)}
            className="p-1 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
            title="Minimize Chat"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Live Agent Step Ticker (Active when streaming) */}
      {isStreaming && (
        <div className="bg-zinc-900 border-b border-zinc-800 px-4 py-2 flex items-center justify-between text-xs font-mono text-cyan-400">
          <div className="flex items-center gap-2 truncate">
            <RefreshCw className="w-3.5 h-3.5 animate-spin text-cyan-400 shrink-0" />
            <span className="truncate">{currentAgentStep || "Reasoning over schema..."}</span>
          </div>
          <span className="text-[10px] text-zinc-500 font-mono shrink-0">SSE STREAM</span>
        </div>
      )}

      {/* Messages Scroll View */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs font-mono">
        {chatMessages.length === 0 && (
          <div className="py-8 text-center space-y-3">
            <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto text-emerald-400">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold text-zinc-300">
                Cognitive Analytical Pair
              </p>
              <p className="text-[11px] text-zinc-500 mt-1 max-w-[240px] mx-auto">
                Ask natural language questions to query Parquet columns, generate hypotheses,
                or benchmark ML models.
              </p>
            </div>

            {/* Quick Suggestion Pills */}
            <div className="flex flex-col gap-1.5 pt-3">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => handleSendMessage(s)}
                  className="text-left px-3 py-2 rounded-lg bg-zinc-900/60 hover:bg-zinc-900 border border-zinc-800 text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors"
                >
                  &rarr; {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {chatMessages.map((msg) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={msg.id}
              className={`flex flex-col space-y-1.5 ${
                isUser ? "items-end" : "items-start"
              }`}
            >
              <div
                className={`p-3.5 rounded-xl border max-w-[92%] leading-relaxed ${
                  isUser
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-100"
                    : "bg-zinc-900/90 border-zinc-800 text-zinc-200"
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.message_text}</div>

                {/* Artifact Action Pill ("Inject to Lab") */}
                {msg.artifact && (
                  <div className="mt-3 pt-2.5 border-t border-zinc-800/80 flex items-center justify-between">
                    <span className="text-[10px] text-cyan-400 uppercase">
                      Generated {msg.artifact.type}
                    </span>
                    <button
                      onClick={() => injectArtifact(msg.artifact!)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 text-[10px] font-semibold transition-colors"
                    >
                      <span>Inject to Lab</span>
                      <ArrowUpRight className="w-3 h-3" />
                    </button>
                  </div>
                )}
              </div>

              {/* Message Footer Telemetry */}
              <div className="flex items-center gap-2 text-[10px] text-zinc-500 px-1">
                <span>{isUser ? "Operator" : `Agent (Tier ${msg.tier || 1})`}</span>
                {msg.latency_ms && <span>• {msg.latency_ms}ms</span>}
              </div>
            </div>
          );
        })}

        {/* Streaming Buffer bubble */}
        {isStreaming && streamBuffer && (
          <div className="flex flex-col items-start space-y-1.5">
            <div className="p-3.5 rounded-xl border bg-zinc-900/90 border-cyan-500/30 text-zinc-200 max-w-[92%] leading-relaxed">
              <div className="whitespace-pre-wrap">{streamBuffer}</div>
            </div>
            <span className="text-[10px] text-cyan-400 px-1 animate-pulse">
              Generating response...
            </span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Chat Input Bar */}
      <div className="p-4 border-t border-zinc-800/80 bg-zinc-950/80 select-none">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="relative"
        >
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            disabled={isStreaming}
            placeholder="Ask agent about columns, trends, or models..."
            className="w-full pl-3.5 pr-10 py-2.5 bg-zinc-900 border border-zinc-800 rounded-xl text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 font-mono disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isStreaming || !inputMessage.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 disabled:opacity-40 text-black transition-colors"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </aside>
  );
}

