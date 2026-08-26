"use client";

import React, { useState, useRef, useEffect } from "react";
import { 
  Send, 
  Loader2, 
  Bot, 
  User, 
  RotateCw, 
  Copy, 
  Check, 
  AlertCircle,
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

export function ChatAssistant({ sessionId, meetingTitle }: ChatAssistantProps) {
  const { token } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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
  }, [sessionId]);

  // Auto-scroll to bottom on messages change
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

  const sendMessage = async (promptText?: string) => {
    const question = (promptText || input).trim();
    if (!question || isStreaming || !sessionId) return;

    setInput("");
    setError(null);
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
        let errDetail = "Failed to receive response";
        try {
          const errJson = await res.json();
          errDetail = errJson.error || errDetail;
        } catch {}
        throw new Error(errDetail);
      }

      if (!res.body) {
        throw new Error("No response stream received");
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
      setError(err.message || "Failed to generate answer.");
      setMessages((prev) => {
        const next = [...prev];
        if (next.length > 0 && next[next.length - 1].role === "assistant" && !next[next.length - 1].content) {
          next.pop();
        }
        return next;
      });
    } finally {
      setIsStreaming(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const starterPrompts = [
    "What were the core decisions reached in this meeting?",
    "Summarize the key deliverables and assigned owners.",
    "Were there any major risks or blockers identified?",
    "What are the scheduled deadlines from this discussion?",
  ];

  return (
    <div className="bg-[#131418] border border-[#22242a] rounded-lg overflow-hidden flex flex-col h-[580px] shadow-sm">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#22242a] flex items-center justify-between bg-[#0f1013]">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-[#ff5c47]" />
          <div>
            <div className="text-xs font-semibold text-[#f3f4f6]">Meeting Q&A Assistant</div>
            <div className="text-[10px] text-[#9ca3af] truncate max-w-[260px] sm:max-w-md">
              Ask questions directly grounded in this transcript
            </div>
          </div>
        </div>

        {messages.length > 0 && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setMessages([])}
            className="h-6 px-2 text-[11px] text-[#9ca3af] hover:text-[#f3f4f6] hover:bg-[#18191f] rounded"
          >
            Clear
          </Button>
        )}
      </div>

      {/* Messages Stream */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {loadingHistory && messages.length === 0 && (
          <div className="flex items-center justify-center py-12 gap-2 text-xs text-[#9ca3af]">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-[#ff5c47]" />
            <span>Loading conversation...</span>
          </div>
        )}

        {messages.length === 0 && !loadingHistory && (
          <div className="space-y-4 py-8 text-center max-w-md mx-auto">
            <div className="space-y-1">
              <div className="text-xs font-semibold text-[#f3f4f6]">
                Ask questions about this meeting
              </div>
              <p className="text-[11px] text-[#9ca3af] leading-relaxed">
                Answers are grounded strictly in the verified transcript and discussion pillars.
              </p>
            </div>

            {/* Quick Starters */}
            <div className="flex flex-col sm:flex-row flex-wrap justify-center gap-1.5 pt-1">
              {starterPrompts.map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => sendMessage(prompt)}
                  disabled={isStreaming}
                  className="px-2.5 py-1.5 rounded-md bg-[#18191f] border border-[#22242a] text-[11px] text-[#9ca3af] hover:text-[#f3f4f6] hover:border-[#ff5c47]/40 transition-colors text-left"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, idx) => {
          const isUser = msg.role === "user";

          return (
            <div
              key={idx}
              className={`flex gap-2 ${isUser ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`group relative max-w-[88%] sm:max-w-[80%] rounded-lg px-3.5 py-2.5 text-xs leading-relaxed transition-all ${
                  isUser
                    ? "bg-[#1e2027] border border-[#2a2c36] text-[#f3f4f6]"
                    : "bg-[#18191f] border border-[#22242a] text-[#e5e7eb]"
                }`}
              >
                {msg.content ? (
                  <MarkdownMessage content={msg.content} isUser={isUser} />
                ) : (
                  <span className="inline-flex items-center gap-1.5 text-[#9ca3af]">
                    <Loader2 className="w-3 h-3 animate-spin text-[#ff5c47]" />
                    <span>Generating answer...</span>
                  </span>
                )}

                {!isUser && msg.content && (
                  <button
                    onClick={() => handleCopyMessage(msg.content, idx)}
                    className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded bg-[#22242a] text-[#9ca3af] hover:text-[#f3f4f6]"
                    title="Copy message"
                  >
                    {copiedIndex === idx ? (
                      <Check className="w-3 h-3 text-[#10b981]" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                )}
              </div>
            </div>
          );
        })}

        {isStreaming && (
          <div className="flex items-center gap-1.5 text-[10.5px] text-[#ff5c47] px-1 font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-[#ff5c47] animate-ping" />
            <span>Streaming tokens via Groq...</span>
          </div>
        )}
      </div>

      {/* Input Composer */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          sendMessage();
        }}
        className="p-2.5 bg-[#0f1013] border-t border-[#22242a] flex items-center gap-2"
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about this meeting..."
          disabled={isStreaming}
          className="flex-1 h-8 px-3 bg-[#18191f] border border-[#22242a] rounded-md text-xs text-[#f3f4f6] placeholder-[#9ca3af] focus:outline-none focus:border-[#ff5c47]/50 transition-colors disabled:opacity-60"
        />
        <Button
          type="submit"
          size="icon"
          disabled={isStreaming || !input.trim()}
          className="w-8 h-8 rounded-md bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white shrink-0 disabled:opacity-40"
        >
          {isStreaming ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Send className="w-3.5 h-3.5" />
          )}
        </Button>
      </form>
    </div>
  );
}

export default ChatAssistant;
