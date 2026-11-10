"use client";

import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Send,
  Bot,
  MessageSquare,
  Zap,
  BrainCircuit,
  ArrowUpRight,
  RefreshCw,
  X,
  Info,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api } from "@/lib/api";
import { ChatEngineStatus, ChatMessage, LabChartType, UiActionEvent } from "@/lib/types";
import { LabTab, useWorkspaceStore } from "@/store/useWorkspaceStore";
import { MarkdownMessage } from "./MarkdownMessage";

interface RightChatProps {
  fileId: string;
}

export function RightChat({ fileId }: RightChatProps) {
  const router = useRouter();
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
    setActiveLabTab,
    setRequestedChartOverride,
    setRequestedAutoMLRun,
    injectArtifact,
    isChatOpen,
    setIsChatOpen,
  } = useWorkspaceStore();

  const [inputMessage, setInputMessage] = useState("");
  const [engineStatus, setEngineStatus] = useState<ChatEngineStatus | null>(null);
  const [showMinimalInfo, setShowMinimalInfo] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadChatHistory();
    refreshEngineStatus();
  }, [fileId]);

  useEffect(() => {
    if (isChatOpen) {
      refreshEngineStatus();
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
      }, 40);
    }
  }, [isChatOpen]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, streamBuffer]);

  useEffect(() => {
    if (!isChatOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsChatOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isChatOpen, setIsChatOpen]);

  const refreshEngineStatus = async () => {
    try {
      const st = await api.chat.status();
      setEngineStatus(st);
    } catch {
      // ignore probe errors
    }
  };

  const loadChatHistory = async () => {
    try {
      const history = await api.chat.history(fileId);
      setChatMessages(history);
    } catch (err) {
      console.error("Failed to load chat history:", err);
    }
  };

  const executeUiAction = async (act: UiActionEvent) => {
    const payload = act.payload || {};
    if (act.action === "switch_tab" && typeof payload.tab === "string") {
      setActiveLabTab(payload.tab as LabTab);
    } else if (act.action === "switch_file" && typeof payload.file_id === "string") {
      router.push(`/workspace/${payload.file_id}`);
    } else if (act.action === "switch_sheet" && typeof payload.sheet_name === "string") {
      try {
        await api.files.switchSheet(fileId, payload.sheet_name);
        window.location.reload();
      } catch (err) {
        console.error("Agentic sheet switch failed:", err);
      }
    } else if (act.action === "update_chart") {
      setRequestedChartOverride({
        chart_type: (payload.chart_type as LabChartType) || "bar",
        x_col: (payload.x_col as string) || null,
        y_col: (payload.y_col as string) || null,
        color_col: (payload.color_col as string) || null,
        nonce: Date.now(),
      });
    } else if (act.action === "run_automl") {
      setActiveLabTab("predict");
      setRequestedAutoMLRun({
        target_col: (payload.target_col as string) || null,
        nonce: Date.now(),
      });
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const query = textToSend || inputMessage;
    if (!query.trim() || isStreaming) return;

    setInputMessage("");

    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      role: "user",
      message_text: query,
      created_at: new Date().toISOString(),
    };
    addChatMessage(userMsg);

    setIsStreaming(true);
    setStreamBuffer("");
    setCurrentAgentStep("Analyzing your question...");
    setActiveTier(1);

    let accumulatedText = "";
    let capturedArtifact: Record<string, unknown> | null = null;
    let detectedTierNum = 1;
    const executedActions: UiActionEvent[] = [];
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
        onTierDetected: (info) => {
          if (typeof info.tier === "number") {
            detectedTierNum = info.tier;
            setActiveTier(info.tier);
          }
        },
        onToken: (token) => {
          accumulatedText += token;
          appendStreamBuffer(token);
        },
        onArtifact: (artifact) => {
          capturedArtifact = artifact;
        },
        onUiAction: (uiAct) => {
          executedActions.push(uiAct);
          executeUiAction(uiAct);
        },
        onDone: () => {
          const latency = Math.max(1, Math.round(performance.now() - startTime));
          const assistantMsg: ChatMessage = {
            id: `ast-${Date.now()}`,
            role: "assistant",
            message_text:
              accumulatedText.trim() ||
              "Completed workspace verification. Ask a column metric or command to inspect live numbers.",
            tier: detectedTierNum,
            latency_ms: latency,
            created_at: new Date().toISOString(),
            actions: executedActions.length > 0 ? executedActions : undefined,
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
          const latency = Math.max(1, Math.round(performance.now() - startTime));
          const fallbackText = accumulatedText.trim()
            ? `${accumulatedText}\n\n[Stream interrupted: ${err.message || "Connection error"}]`
            : `Unable to complete stream (${err.message || "Unexpected connection error"}).`;
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
      const errorMessage = err instanceof Error ? err.message : "Server unreachable.";
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
    "Summarize the key takeaways in this file",
    "What factors drive cancellations the most?",
    "Build a chart comparing my top categories",
    "How do I use the Predict & Simulate tab?",
  ];

  const isOllamaOnline = engineStatus?.online === true;

  const floatingToggleButton = (
    <button
      type="button"
      onClick={() => setIsChatOpen(!isChatOpen)}
      data-testid="chat-floating-toggle"
      aria-label={isChatOpen ? "Hide AI" : "Open AI Analyst Chat"}
      title={isChatOpen ? "Hide AI Analyst (Esc)" : "Open AI Analyst Chat"}
      className={`fixed right-6 bottom-4 z-50 flex items-center gap-2 px-4 py-2 rounded-full font-semibold text-xs shadow-2xl border transition-all hover:scale-105 active:scale-95 font-mono cursor-pointer ${
        isChatOpen
          ? "bg-zinc-900 hover:bg-zinc-800 text-zinc-200 border-zinc-700 shadow-black/60"
          : "bg-emerald-500 hover:bg-emerald-400 text-zinc-950 border-emerald-400/50 shadow-emerald-500/30"
      }`}
    >
      {isChatOpen ? (
        <>
          <X className="w-3.5 h-3.5 text-zinc-300" />
          <span>Hide AI</span>
        </>
      ) : (
        <>
          <MessageSquare className="w-4 h-4 text-zinc-950" />
          <span>AI Analyst</span>
          {isStreaming && (
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
            </span>
          )}
        </>
      )}
    </button>
  );

  if (!isChatOpen) {
    return floatingToggleButton;
  }

  return (
    <>
      {floatingToggleButton}
      <aside
        data-testid="chat-drawer"
        className="w-[460px] max-w-[94vw] fixed right-4 bottom-16 top-16 z-50 flex flex-col rounded-2xl border border-zinc-800 bg-zinc-950/95 backdrop-blur-xl shadow-2xl shadow-black/80 overflow-hidden animate-in fade-in slide-in-from-right-4 duration-200"
      >
        {/* Chat Top Header */}
        <div className="p-3.5 border-b border-zinc-800/80 space-y-2 select-none bg-zinc-900/60 shrink-0">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center shrink-0">
                <BrainCircuit className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-xs font-mono font-bold text-white flex items-center gap-1.5 min-w-0">
                  <span className="truncate">DataMind AI Assistant</span>
                </h3>
                <span
                  className="text-[10px] font-mono text-zinc-500 block truncate"
                  title="Ask about your data, charts, predictions, or how to use this workspace"
                >
                  Data, charts, predictions &amp; help
                </span>
              </div>
            </div>

            <div className="flex items-center gap-1.5 flex-shrink-0">
              <button
                type="button"
                onClick={() => !isOllamaOnline && setShowMinimalInfo((v) => !v)}
                className={`flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-mono border transition-colors truncate max-w-[170px] ${
                  isOllamaOnline
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                    : "border-amber-500/30 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 cursor-pointer"
                }`}
                title={
                  isOllamaOnline
                    ? `Connected to ${engineStatus?.model}`
                    : "Click to view Minimal Mode capabilities"
                }
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    isOllamaOnline ? "bg-emerald-400" : "bg-amber-400"
                  }`}
                />
                <span className="truncate">
                  {engineStatus
                    ? isOllamaOnline
                      ? `Ollama Live (${engineStatus.model})`
                      : "Minimal Mode (DuckDB)"
                    : "Checking Engine..."}
                </span>
                {!isOllamaOnline &&
                  (showMinimalInfo ? (
                    <ChevronUp className="w-3 h-3 shrink-0" />
                  ) : (
                    <ChevronDown className="w-3 h-3 shrink-0" />
                  ))}
              </button>

              <button
                type="button"
                onClick={() => setIsChatOpen(false)}
                aria-label="Hide"
                title="Hide (Esc)"
                data-testid="chat-collapse-button"
                className="flex-shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-mono text-zinc-200 hover:text-white bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 transition-colors cursor-pointer"
              >
                <ChevronDown className="w-3.5 h-3.5 shrink-0" />
                <span>Hide</span>
                <X className="w-3.5 h-3.5 shrink-0" />
              </button>
            </div>
          </div>

        {/* Expandable Minimal Mode Capabilities Info Banner */}
        {!isOllamaOnline && showMinimalInfo && (
          <div className="p-2.5 rounded-lg border border-amber-500/20 bg-zinc-950/90 text-[10px] font-mono text-zinc-300 space-y-1.5">
            <div className="flex items-center gap-1.5 text-amber-300 font-semibold">
              <Info className="w-3.5 h-3.5 shrink-0" />
              <span>Minimal Local Engine Active (Ollama Offline)</span>
            </div>
            <ul className="space-y-1 text-zinc-400 pl-1">
              <li>• Any column stats (average, min/max, median, empty values, group-bys)</li>
              <li>• Dataset summaries, key patterns &amp; factor explanations</li>
              <li>• Workspace commands (&quot;Open Predict &amp; Simulate&quot;, &quot;Plot adr by hotel&quot;)</li>
            </ul>
            <p className="text-emerald-400/90 pt-0.5">
              Tip: Run &quot;ollama serve&quot; locally to unlock open-ended generative reasoning.
            </p>
          </div>
        )}
      </div>

      {/* Live Agent Step Ticker */}
      {isStreaming && (
        <div className="bg-zinc-900 border-b border-zinc-800 px-4 py-2 flex items-center justify-between text-xs font-mono text-cyan-400 shrink-0">
          <div className="flex items-center gap-2 truncate">
            <RefreshCw className="w-3.5 h-3.5 animate-spin text-cyan-400 shrink-0" />
            <span className="truncate">{currentAgentStep || "Analyzing your question..."}</span>
          </div>
          <span className="text-[10px] text-zinc-500 font-mono shrink-0">LIVE</span>
        </div>
      )}

      {/* Messages Scroll View (min-h-0 + generous bottom padding prevents bubble clipping) */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 pt-4 pb-6 space-y-4 text-xs font-mono">
        {chatMessages.length === 0 && (
          <div className="py-6 text-center space-y-3">
            <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto text-emerald-400">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold text-zinc-300">
                DataMind AI Assistant
              </p>
              <p className="text-[11px] text-zinc-500 mt-1 max-w-[290px] mx-auto">
                Ask about your data, charts, predictions, or how to use this workspace.
              </p>
            </div>

            <div className="flex flex-col gap-1.5 pt-2">
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
          const showLatency = typeof msg.latency_ms === "number" && msg.latency_ms > 0;
          return (
            <div
              key={msg.id}
              className={`flex flex-col space-y-1.5 ${
                isUser ? "items-end" : "items-start"
              }`}
            >
              <div
                className={`p-3.5 rounded-xl border max-w-[94%] leading-relaxed ${
                  isUser
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-100"
                    : "bg-zinc-900/90 border-zinc-800 text-zinc-200"
                }`}
              >
                {isUser ? (
                  <div className="whitespace-pre-wrap text-xs">{msg.message_text}</div>
                ) : (
                  <MarkdownMessage content={msg.message_text} />
                )}

                {/* Executed UI Actions Confirmation Pills */}
                {msg.actions && msg.actions.length > 0 && (
                  <div className="mt-2.5 pt-2 border-t border-zinc-800/80 flex flex-wrap gap-1.5">
                    {msg.actions.map((act, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-[10px]"
                      >
                        <Zap className="w-3 h-3" />
                        <span>{act.label || act.action}</span>
                      </span>
                    ))}
                  </div>
                )}

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
                <span>{isUser ? "You" : "DataMind AI"}</span>
                {!isUser && (
                  <span className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                    {msg.tier === 3
                      ? "🔬 Deep Analysis"
                      : msg.tier === 2
                        ? "💬 AI Response"
                        : "⚡ Instant Answer"}
                  </span>
                )}
                {showLatency ? <span>• {msg.latency_ms}ms</span> : null}
              </div>
            </div>
          );
        })}

        {/* Streaming Buffer bubble */}
        {isStreaming && streamBuffer && (
          <div className="flex flex-col items-start space-y-1.5">
            <div className="p-3.5 rounded-xl border bg-zinc-900/90 border-cyan-500/30 text-zinc-200 max-w-[94%] leading-relaxed">
              <MarkdownMessage content={streamBuffer} />
            </div>
            <span className="text-[10px] text-cyan-400 px-1 animate-pulse">
              Generating response...
            </span>
          </div>
        )}

        <div ref={messagesEndRef} className="h-2 shrink-0" />
      </div>

      {/* Chat Input Bar */}
      <div className="p-3.5 border-t border-zinc-800/80 bg-zinc-950/95 select-none shrink-0">
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
            placeholder="Ask about your data, charts, or commands..."
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
    </>
  );
}
