"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Sparkles,
  ArrowUp,
  Loader2,
  CheckCircle2,
  ListTodo,
  ShieldAlert,
  CalendarClock,
  GitCompare,
  RotateCw,
  Copy,
  Check,
  AlertCircle,
  Trash2,
  Bot,
  MessageSquare
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import { MarkdownMessage } from "@/components/MarkdownMessage";

export interface ChatMessage {
  id?: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
}

interface ChatAssistantProps {
  sessionId?: string;
  meetingTitle?: string;
}

const PROMPT_SUGGESTIONS = [
  {
    id: "decisions",
    label: "Decisions",
    icon: CheckCircle2,
    iconColor: "text-[#10b981] bg-[#10b981]/10 border-[#10b981]/20",
    description: "What core decisions were finalized?",
    prompt: "What were the key decisions made and finalized in this meeting?",
  },
  {
    id: "actions",
    label: "Action Items",
    icon: ListTodo,
    iconColor: "text-[#ff5c47] bg-[#ff5c47]/10 border-[#ff5c47]/20",
    description: "Who owns the next steps and deliverables?",
    prompt: "List all action items, assigned owners, and deliverables agreed upon.",
  },
  {
    id: "risks",
    label: "Risks & Blockers",
    icon: ShieldAlert,
    iconColor: "text-[#f59e0b] bg-[#f59e0b]/10 border-[#f59e0b]/20",
    description: "What obstacles or concerns were raised?",
    prompt: "What major risks, challenges, or blockers were discussed during this meeting?",
  },
  {
    id: "deadlines",
    label: "Deadlines & Dates",
    icon: CalendarClock,
    iconColor: "text-[#3b82f6] bg-[#3b82f6]/10 border-[#3b82f6]/20",
    description: "What milestones and timelines were mentioned?",
    prompt: "Extract all dates, milestones, and deadlines mentioned in this discussion.",
  },
  {
    id: "takeaways",
    label: "Key Takeaways",
    icon: Sparkles,
    iconColor: "text-[#a855f7] bg-[#a855f7]/10 border-[#a855f7]/20",
    description: "Executive synthesis of the discussion",
    prompt: "Provide a concise 3-bullet executive synthesis of the most critical takeaways from this meeting.",
  },
  {
    id: "changes",
    label: "What Changed?",
    icon: GitCompare,
    iconColor: "text-[#ec4899] bg-[#ec4899]/10 border-[#ec4899]/20",
    description: "Updates, pivots, or new direction",
    prompt: "What new changes, updates, or strategic pivots were introduced in this meeting?",
  },
];

export function ChatAssistant({ sessionId, meetingTitle }: ChatAssistantProps) {
  const { token } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUserPrompt, setLastUserPrompt] = useState<string | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load chat history on mount or when sessionId changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }

    let isMounted = true;
    setLoadingHistory(true);
    setError(null);

    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    fetch(`/api/sessions/${sessionId}/chat`, { headers })
      .then((res) => res.json())
      .then((data) => {
        if (isMounted && data && Array.isArray(data.messages)) {
          setMessages(data.messages);
        }
      })
      .catch((err) => {
        console.warn("[ChatAssistant] History fetch note:", err);
      })
      .finally(() => {
        if (isMounted) setLoadingHistory(false);
      });

    return () => {
      isMounted = false;
    };
  }, [sessionId, token]);

  // Auto-scroll to bottom smoothly on message stream updates
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, isStreaming]);

  const handleCopyMessage = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const sendMessage = async (promptText?: string) => {
    const question = (promptText || input).trim();
    if (!question || isStreaming || !sessionId) return;

    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    setError(null);
    setLastUserPrompt(question);
    setIsStreaming(true);

    const userMsg: ChatMessage = { role: "user", content: question };
    const initialAssistantMsg: ChatMessage = { role: "assistant", content: "" };

    setMessages((prev) => [...prev, userMsg, initialAssistantMsg]);

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`/api/sessions/${sessionId}/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          question,
          history: messages.slice(-10),
        }),
      });

      if (!res.ok) {
        let errDetail = "Couldn't get an answer. Please try again.";
        try {
          const errJson = await res.json();
          if (errJson.error && !errJson.error.includes("Internal") && !errJson.error.includes("500")) {
            errDetail = errJson.error;
          }
        } catch {}
        throw new Error(errDetail);
      }

      if (!res.body) {
        throw new Error("Couldn't receive response stream.");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedAnswer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        accumulatedAnswer += chunk;

        setMessages((prev) => {
          const next = [...prev];
          if (next.length > 0 && next[next.length - 1].role === "assistant") {
            next[next.length - 1] = {
              role: "assistant",
              content: accumulatedAnswer,
            };
          }
          return next;
        });
      }
    } catch (err: any) {
      console.error("[ChatAssistant] Error:", err);
      setError(err.message || "Couldn't get an answer. Please try again.");
      setMessages((prev) => {
        const next = [...prev];
        if (next.length > 0 && next[next.length - 1].role === "assistant" && !next[next.length - 1].content) {
          next.pop();
        }
        return next;
      });
    } finally {
      setIsStreaming(false);
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  };

  return (
    <div className="bg-[#111216] border border-[#22242a] rounded-xl overflow-hidden flex flex-col h-[640px] max-h-[calc(100vh-14rem)] min-h-[480px] shadow-sm">
      {/* Minimal AI Assistant Header */}
      <div className="px-4 py-3 border-b border-[#22242a] flex items-center justify-between bg-[#0e0f12]">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-md bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47]">
            <Sparkles className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="text-xs font-semibold text-[#f3f4f6] flex items-center gap-1.5">
              <span>Meeting Q&A</span>
              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-[#1c1e24] text-[#9ca3af] border border-[#262830]">
                AI Assistant
              </span>
            </div>
            <div className="text-[10px] text-[#9ca3af] truncate max-w-[240px] sm:max-w-md">
              Answers synthesized directly from meeting transcript
            </div>
          </div>
        </div>

        {messages.length > 0 && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setMessages([])}
            className="h-7 px-2 text-[11px] text-[#9ca3af] hover:text-[#ff5c47] hover:bg-[#18191f] rounded-md gap-1 cursor-pointer transition-colors"
            title="Clear Conversation"
          >
            <Trash2 className="w-3 h-3" />
            <span className="hidden sm:inline">Clear</span>
          </Button>
        )}
      </div>

      {/* Messages Stream Container */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3.5 sm:p-5 space-y-4">
        {loadingHistory && messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center py-20 gap-2.5 text-xs text-[#9ca3af]">
            <Loader2 className="w-4 h-4 animate-spin text-[#ff5c47]" />
            <span>Retrieving meeting context...</span>
          </div>
        )}

        {/* Intentional, Compact Empty State */}
        {messages.length === 0 && !loadingHistory && (
          <div className="h-full flex flex-col items-center justify-center py-6 px-2 text-center max-w-xl mx-auto space-y-5 animate-in fade-in duration-200">
            <div className="space-y-1.5">
              <div className="w-10 h-10 rounded-xl bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47] mx-auto shadow-sm">
                <Sparkles className="w-5 h-5" />
              </div>
              <h3 className="text-sm sm:text-base font-semibold text-[#f3f4f6] tracking-tight">
                Ask anything about this meeting
              </h3>
              <p className="text-xs text-[#9ca3af] max-w-md mx-auto leading-relaxed">
                Answers are synthesized directly from this meeting's transcript, discussion pillars, and action items.
              </p>
            </div>

            {/* Curated Prompt Suggestions */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full pt-1">
              {PROMPT_SUGGESTIONS.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => sendMessage(item.prompt)}
                    disabled={isStreaming}
                    className="flex items-start gap-2.5 p-3 rounded-xl bg-[#15161b] hover:bg-[#1a1c22] border border-[#22242a] hover:border-[#ff5c47]/30 transition-all text-left group cursor-pointer disabled:opacity-50"
                  >
                    <div className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 mt-0.5 border ${item.iconColor}`}>
                      <Icon className="w-3.5 h-3.5" />
                    </div>
                    <div className="space-y-0.5 min-w-0 flex-1">
                      <div className="text-xs font-semibold text-[#f3f4f6] group-hover:text-[#ff5c47] transition-colors truncate">
                        {item.label}
                      </div>
                      <div className="text-[11px] text-[#9ca3af] group-hover:text-[#cbd5e1] leading-snug line-clamp-1">
                        {item.description}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Active Conversation Flow */}
        {messages.length > 0 && (
          <div className="space-y-4">
            {/* Quick Follow-up Chips Bar */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1.5 border-b border-[#1c1e24] scrollbar-none">
              <span className="text-[10px] text-[#6b7280] uppercase tracking-wider font-mono shrink-0 mr-1">
                Quick Prompts:
              </span>
              {PROMPT_SUGGESTIONS.slice(0, 4).map((item) => (
                <button
                  key={item.id}
                  onClick={() => sendMessage(item.prompt)}
                  disabled={isStreaming}
                  className="px-2.5 py-1 rounded-md bg-[#16171d] hover:bg-[#1e2027] border border-[#22242a] hover:border-[#ff5c47]/30 text-[11px] text-[#9ca3af] hover:text-[#f3f4f6] transition-colors shrink-0 cursor-pointer disabled:opacity-50"
                >
                  {item.label}
                </button>
              ))}
            </div>

            {/* Message Stream */}
            {messages.map((msg, idx) => {
              const isUser = msg.role === "user";

              if (isUser) {
                return (
                  <div key={idx} className="flex justify-end pt-1">
                    <div className="max-w-[88%] sm:max-w-[78%] rounded-2xl rounded-tr-sm bg-[#1c1e24] border border-[#2a2c35] px-4 py-2.5 text-xs sm:text-[13px] text-[#f3f4f6] shadow-sm leading-relaxed">
                      <MarkdownMessage content={msg.content} isUser={true} />
                    </div>
                  </div>
                );
              }

              return (
                <div key={idx} className="flex justify-start pt-1">
                  <div className="group relative w-full rounded-xl bg-[#141519]/70 border border-[#22242a] p-4 sm:p-5 text-[#e5e7eb] space-y-2.5 shadow-sm">
                    {/* Assistant Note Header */}
                    <div className="flex items-center justify-between border-b border-[#22242a]/60 pb-2 text-[11px] text-[#9ca3af]">
                      <div className="flex items-center gap-1.5 font-medium">
                        <Sparkles className="w-3.5 h-3.5 text-[#ff5c47]" />
                        <span className="text-[#f3f4f6]">RecMap Intelligence</span>
                        <span>•</span>
                        <span className="text-[10px] text-[#6b7280]">Transcript Grounded</span>
                      </div>

                      {msg.content && (
                        <button
                          onClick={() => handleCopyMessage(msg.content, idx)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-[#22242a] text-[#9ca3af] hover:text-[#f3f4f6] flex items-center gap-1 text-[10px] cursor-pointer"
                          title="Copy response"
                        >
                          {copiedIndex === idx ? (
                            <>
                              <Check className="w-3 h-3 text-[#10b981]" />
                              <span className="text-[#10b981]">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" />
                              <span>Copy</span>
                            </>
                          )}
                        </button>
                      )}
                    </div>

                    {/* Markdown Output or Thinking State */}
                    {msg.content ? (
                      <MarkdownMessage content={msg.content} isUser={false} />
                    ) : (
                      <div className="flex items-center gap-2 text-xs text-[#9ca3af] py-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-[#ff5c47] animate-pulse" />
                        <span>Synthesizing answer from transcript...</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Inline Error State with Retry */}
        {error && (
          <div className="p-3 rounded-lg bg-[#2a1717]/60 border border-[#ef4444]/30 flex items-center justify-between text-xs text-[#fca5a5]">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-[#ef4444] shrink-0" />
              <span>{error}</span>
            </div>
            {lastUserPrompt && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => sendMessage(lastUserPrompt)}
                className="h-6 px-2 text-[11px] text-[#fca5a5] hover:text-white hover:bg-[#ef4444]/20 rounded gap-1 cursor-pointer"
              >
                <RotateCw className="w-3 h-3" />
                <span>Retry</span>
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Modern Input Composer */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          sendMessage();
        }}
        className="p-3 bg-[#0e0f12] border-t border-[#22242a] space-y-1.5"
      >
        <div className="relative flex items-end gap-2 bg-[#15161b] border border-[#22242a] focus-within:border-[#ff5c47]/50 focus-within:ring-1 focus-within:ring-[#ff5c47]/20 rounded-xl p-2 transition-all">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about this meeting…"
            disabled={isStreaming}
            className="flex-1 resize-none bg-transparent border-0 text-xs sm:text-[13px] text-[#f3f4f6] placeholder-[#6b7280] focus:outline-none py-1.5 px-2 min-h-[36px] max-h-[140px] leading-relaxed disabled:opacity-60"
          />
          <Button
            type="submit"
            size="icon"
            disabled={isStreaming || !input.trim()}
            className="w-8 h-8 rounded-lg bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white disabled:opacity-30 shrink-0 flex items-center justify-center transition-all cursor-pointer shadow-sm mb-0.5"
            title="Send Question (Enter)"
          >
            {isStreaming ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <ArrowUp className="w-4 h-4" />
            )}
          </Button>
        </div>

        <div className="flex items-center justify-between text-[10.5px] text-[#6b7280] px-1">
          <span>Grounded in transcript & discussion context</span>
          <span className="hidden sm:inline font-mono text-[10px]">
            Enter ↵ to send • Shift+Enter for new line
          </span>
        </div>
      </form>
    </div>
  );
}

export default ChatAssistant;
