"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  FileText, 
  CheckSquare, 
  Network, 
  MessageSquare, 
  Clock, 
  Calendar, 
  Tag, 
  Copy, 
  Download, 
  Printer, 
  Check, 
  Send,
  Loader2, 
  HelpCircle,
  Lightbulb,
  AlertCircle,
  Share2,
  RotateCw,
  Cpu,
  CheckCircle2,
  Radio,
  FileAudio
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MeetingSession, ActionItem, MeetingSection, TranscriptSegment } from "@/types/meeting";
import { MindmapView } from "@/components/MindmapView";
import { ChatAssistant } from "@/components/ChatAssistant";
import { normalizeTemplate, TEMPLATES_CONFIG } from "@/lib/templates";
import { togglePublicSession, fetchSessionById, retryProcessingSession } from "@/lib/api";
import { formatMeetingTitle } from "@/lib/utils";
import { supabase } from "@/lib/supabaseClient";
import { useAuth } from "@/context/AuthContext";

interface MeetingViewProps {
  session: MeetingSession;
  onSeekAudio?: (seconds: number) => void;
  onSessionUpdated?: (updatedSession: MeetingSession) => void;
  readOnly?: boolean;
}

export function MeetingView({ session: initialSession, onSeekAudio, onSessionUpdated, readOnly = false }: MeetingViewProps) {
  const { user, token } = useAuth();
  const [session, setSession] = useState<MeetingSession>(initialSession);
  const [activeTab, setActiveTab] = useState("summary");
  const [copied, setCopied] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [elapsedProcessingSeconds, setElapsedProcessingSeconds] = useState(0);

  const isOwner = Boolean(user?.id && session.user_id && user.id === session.user_id);
  const canAccessChat = !readOnly && (isOwner || user?.role === "admin");

  // Sync initialSession changes to local state
  useEffect(() => {
    setSession(initialSession);
  }, [initialSession]);

  const sessionId = session.id || session.metadata?.session_id;
  const status = session.status || (session.summary || session.executive_summary ? "completed" : "processing");
  const isProcessing = status === "processing";
  const isFailed = status === "failed";

  // --------------------------------------------------------------------------
  // Realtime Subscription & Polling when session is processing
  // --------------------------------------------------------------------------
  useEffect(() => {
    if (!isProcessing || !sessionId) return;

    let timer: NodeJS.Timeout | null = null;
    let pollInterval: NodeJS.Timeout | null = null;

    setElapsedProcessingSeconds(0);
    timer = setInterval(() => {
      setElapsedProcessingSeconds((prev) => prev + 1);
    }, 1000);

    const channel = supabase
      .channel(`session-realtime-${sessionId}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "sessions",
          filter: `id=eq.${sessionId}`,
        },
        async (payload) => {
          console.log("[Realtime] Session record updated in Supabase:", payload.new);
          const fullData = await fetchSessionById(sessionId, token || undefined);
          if (fullData) {
            setSession(fullData);
            onSessionUpdated?.(fullData);
          }
        }
      )
      .subscribe();

    pollInterval = setInterval(async () => {
      try {
        const fullData = await fetchSessionById(sessionId, token || undefined);
        if (fullData) {
          if (fullData.status === "completed" || fullData.status === "failed" || fullData.summary) {
            setSession(fullData);
            onSessionUpdated?.(fullData);
          }
        }
      } catch (err) {
        console.warn("[Polling] Status check note:", err);
      }
    }, 3500);

    return () => {
      if (timer) clearInterval(timer);
      if (pollInterval) clearInterval(pollInterval);
      supabase.removeChannel(channel);
    };
  }, [isProcessing, sessionId, token, onSessionUpdated]);

  const handleRetry = async () => {
    if (!sessionId || retrying) return;
    setRetrying(true);
    try {
      const ok = await retryProcessingSession(sessionId, token || undefined);
      if (ok) {
        setSession((prev) => ({
          ...prev,
          status: "processing",
          error_message: null,
        }));
      }
    } catch (err) {
      console.error("Retry failed:", err);
    } finally {
      setRetrying(false);
    }
  };

  // Robust data key fallbacks
  const summaryText = session.executive_summary || session.tldr || session.summary || "";
  const pillars: MeetingSection[] = (session.discussion_pillars && session.discussion_pillars.length > 0)
    ? session.discussion_pillars
    : (session.sections || []);
  const rawActions: ActionItem[] = session.action_items || [];
  const transcriptSegments: TranscriptSegment[] = Array.isArray(session.transcript_segments)
    ? session.transcript_segments
    : (Array.isArray(session.transcript) ? session.transcript : []);
  const fullTranscriptText = typeof session.transcript === "string"
    ? session.transcript
    : (session.full_transcript_text || "");

  const rawSuggestions: any = session.strategic_insights || session.ai_suggestions;
  const strategicItems: Array<{ label?: string; title?: string; detail?: string; body?: string; text?: string }> = Array.isArray(rawSuggestions)
    ? rawSuggestions
    : (Array.isArray(rawSuggestions?.items) ? rawSuggestions.items : []);

  // Action Items Consolidation
  const [actionItems, setActionItems] = useState<ActionItem[]>(() => {
    const items = [...rawActions];
    pillars.forEach((sec) => {
      (sec.action_items || []).forEach((a) => {
        if (!items.find((it) => (it.task && it.task === a.task) || (it.description && it.description === a.description))) {
          items.push(a);
        }
      });
    });
    return items.map((it, idx) => ({
      ...it,
      number: idx + 1,
      status: it.status || "pending",
      priority: it.priority || "MED",
    }));
  });

  useEffect(() => {
    const items = [...(session.action_items || [])];
    const currentPillars = (session.discussion_pillars && session.discussion_pillars.length > 0)
      ? session.discussion_pillars
      : (session.sections || []);
    
    currentPillars.forEach((sec) => {
      (sec.action_items || []).forEach((a) => {
        if (!items.find((it) => (it.task && it.task === a.task) || (it.description && it.description === a.description))) {
          items.push(a);
        }
      });
    });
    setActionItems(
      items.map((it, idx) => ({
        ...it,
        number: idx + 1,
        status: it.status || "pending",
        priority: it.priority || "MED",
      }))
    );
    setActiveTab("summary");
  }, [session.metadata?.session_id, session.title, session.id, session.status]);

  const rawTitle = session.title || "Meeting Summary";
  const cleanTitle = rawTitle
    .replace(/^Upload \d+ \d+\s*/i, "")
    .replace(/^upload_\d+_\d+_\s*/i, "")
    .replace(/^session_\d+_\d+_\s*/i, "");
  const displayTitle = formatMeetingTitle(cleanTitle, session.meeting_date || session.date);

  const toggleActionStatus = (idx: number) => {
    setActionItems((prev) =>
      prev.map((item, i) =>
        i === idx
          ? {
              ...item,
              status: item.status === "completed" ? "pending" : "completed",
            }
          : item
      )
    );
  };

  const handleShareLink = async () => {
    const sid = session.id || session.metadata?.session_id || "sample";
    const shareUrl = typeof window !== "undefined" ? `${window.location.origin}/share/${sid}` : `/share/${sid}`;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 2500);
      if (session.id) {
        togglePublicSession(session.id, true, token || undefined);
      }
    } catch {
      // fallback
    }
  };

  const generateFullMarkdown = () => {
    let md = `# ${displayTitle}\n\n`;
    md += `**Date:** ${displayDate || "N/A"}  \n`;
    md += `**Duration:** ${displayDuration || "N/A"}  \n\n`;
    md += `## ⚡ Executive Summary\n${summaryText}\n\n`;

    if (pillars.length > 0) {
      md += `## 📋 Discussion Topics & Sections\n`;
      pillars.forEach((sec, idx) => {
        md += `### ${sec.n || idx + 1}. ${sec.title}\n`;
        if (sec.narrative) md += `${sec.narrative}\n\n`;
        if (sec.decisions && sec.decisions.length > 0) {
          md += `**Decisions:**\n`;
          sec.decisions.forEach((d) => (md += `- ${d}\n`));
          md += `\n`;
        }
      });
    }

    if (actionItems.length > 0) {
      md += `## ✅ Action Items\n`;
      actionItems.forEach((a) => {
        const check = a.status === "completed" ? "[x]" : "[ ]";
        md += `- ${check} **${a.task || a.description}** — *${a.owner || a.assignee || "Team"}* (${a.priority || "MED"})${a.due_date ? ` [Due: ${a.due_date}]` : ""}\n`;
      });
      md += `\n`;
    }

    if (session.mindmap_markdown) {
      md += `## 🧠 Mind Map\n\`\`\`markmap\n${session.mindmap_markdown}\n\`\`\`\n`;
    }

    return md;
  };

  const handleDownloadMarkdown = () => {
    const md = generateFullMarkdown();
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${displayTitle.replace(/[^a-z0-9]/gi, "_").toLowerCase()}.md`;
    a.click();
  };

  const handleCopyMarkdown = () => {
    const md = generateFullMarkdown();
    navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadJSON = () => {
    const jsonStr = JSON.stringify(session, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${displayTitle.replace(/[^a-z0-9]/gi, "_").toLowerCase()}.json`;
    a.click();
  };

  const totalActions = actionItems.length;
  const completedActions = actionItems.filter((a) => a.status === "completed").length;
  const completionPercent = totalActions > 0 ? Math.round((completedActions / totalActions) * 100) : 0;
  const displayDate = session.meeting_date || session.date || (session.created_at ? new Date(session.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "");
  const displayDuration = session.duration || (session.duration_minutes ? `${session.duration_minutes}m` : "");

  const rawTemplate = (session as any).template || session.metadata?.template || session.metadata?.template_type;
  const templateId = normalizeTemplate(rawTemplate);
  const templateConfig = templateId !== "auto" ? TEMPLATES_CONFIG[templateId] : null;

  // ==========================================================================
  // VIEW 1: PROCESSING STATE
  // ==========================================================================
  if (isProcessing) {
    const isTranscribing = elapsedProcessingSeconds < 10;
    const isSynthesizing = elapsedProcessingSeconds >= 10 && elapsedProcessingSeconds < 25;
    const isSaving = elapsedProcessingSeconds >= 25;

    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-12 sm:py-20">
        <motion.div 
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-[#131418] border border-[#22242a] rounded-xl p-6 sm:p-8 space-y-6 text-center shadow-lg"
        >
          <div className="w-12 h-12 rounded-lg bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47] mx-auto">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>

          <div className="space-y-2">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#ff5c47]/10 border border-[#ff5c47]/20 text-[#ff5c47] text-xs font-medium">
              <span>
                {isTranscribing && "1. Transcribing audio stream (Whisper)..."}
                {isSynthesizing && "2. Extracting intelligence & mind map (GPT-120B)..."}
                {isSaving && "3. Finalizing executive synthesis..."}
              </span>
            </div>
            <h2 className="text-xl font-bold text-[#f3f4f6] tracking-tight">
              {displayTitle}
            </h2>
            <p className="text-xs text-[#9ca3af] max-w-md mx-auto leading-relaxed">
              Processing in background cloud worker. You can safely navigate away; your meeting intelligence will appear automatically.
            </p>
          </div>

          {/* 3 Step Pipeline */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-left">
            <div className="p-3 rounded-lg bg-[#18191f] border border-[#10b981]/30 space-y-1">
              <div className="flex items-center justify-between text-xs text-[#10b981] font-medium">
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  1. Storage
                </span>
                <span className="text-[10px] font-mono">100%</span>
              </div>
              <p className="text-[11px] text-[#9ca3af]">Secure Audio Stored</p>
            </div>

            <div className={`p-3 rounded-lg bg-[#18191f] border space-y-1 ${
              isTranscribing ? "border-[#ff5c47]/50" : "border-[#10b981]/30"
            }`}>
              <div className={`flex items-center justify-between text-xs font-medium ${
                isTranscribing ? "text-[#ff5c47]" : "text-[#10b981]"
              }`}>
                <span className="flex items-center gap-1.5">
                  {isTranscribing ? <Radio className="w-3.5 h-3.5 animate-pulse text-[#ff5c47]" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                  2. Speech
                </span>
                <span className="text-[10px] font-mono">{isTranscribing ? `${elapsedProcessingSeconds}s` : "✓ Done"}</span>
              </div>
              <p className="text-[11px] text-[#9ca3af]">Whisper Large V3</p>
            </div>

            <div className={`p-3 rounded-lg bg-[#18191f] border space-y-1 ${
              isSynthesizing || isSaving ? "border-[#ff5c47]/50 text-[#ff5c47]" : "border-[#22242a] opacity-60"
            }`}>
              <div className={`flex items-center justify-between text-xs font-medium ${
                isSynthesizing || isSaving ? "text-[#ff5c47]" : "text-[#9ca3af]"
              }`}>
                <span className="flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5" />
                  3. Intelligence
                </span>
                <span className="text-[10px] font-mono">
                  {isSynthesizing || isSaving ? `${Math.max(0, elapsedProcessingSeconds - 10)}s` : "Pending"}
                </span>
              </div>
              <p className="text-[11px] text-[#9ca3af]">GPT-120B Model</p>
            </div>
          </div>

          <div className="space-y-1.5 pt-2 border-t border-[#22242a]">
            <div className="flex items-center justify-between text-xs text-[#9ca3af]">
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3 text-[#ff5c47]" />
                Elapsed: <span className="font-mono text-[#f3f4f6] font-medium">{elapsedProcessingSeconds}s</span>
              </span>
              <span className="font-mono text-[11px] text-[#10b981]">Realtime Sync</span>
            </div>
            <div className="w-full bg-[#18191f] h-1.5 rounded overflow-hidden">
              <motion.div
                className="h-full bg-[#ff5c47] rounded"
                animate={{ width: ["20%", "70%", "95%"] }}
                transition={{ duration: 25, ease: "easeInOut" }}
              />
            </div>
          </div>
        </motion.div>
      </div>
    );
  }

  // ==========================================================================
  // VIEW 2: FAILED STATE
  // ==========================================================================
  if (isFailed) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-12 sm:py-20">
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-[#131418] border border-[#ef4444]/30 rounded-xl p-8 space-y-5 text-center shadow-lg"
        >
          <div className="w-12 h-12 rounded-lg bg-[#ef4444]/10 border border-[#ef4444]/20 flex items-center justify-center text-[#ef4444] mx-auto">
            <AlertCircle className="w-6 h-6" />
          </div>

          <div className="space-y-1.5">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded bg-[#ef4444]/10 text-[#ef4444] text-xs font-semibold">
              Processing Failed
            </div>
            <h2 className="text-xl font-bold text-[#f3f4f6]">{displayTitle}</h2>
            <p className="text-xs text-[#ef4444] bg-[#ef4444]/10 p-3 rounded-lg max-w-lg mx-auto leading-relaxed border border-[#ef4444]/20">
              {session.error_message || "An unexpected error occurred during audio transcription or synthesis."}
            </p>
          </div>

          <div className="flex items-center justify-center pt-2">
            <Button
              onClick={handleRetry}
              disabled={retrying}
              className="h-9 px-5 rounded-md bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-medium text-xs gap-1.5 shadow-sm"
            >
              <RotateCw className={`w-3.5 h-3.5 ${retrying ? "animate-spin" : ""}`} />
              <span>{retrying ? "Retrying..." : "Retry Processing"}</span>
            </Button>
          </div>
        </motion.div>
      </div>
    );
  }

  // ==========================================================================
  // VIEW 3: COMPLETED MEETING SESSION VIEW
  // ==========================================================================
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-8 py-6 sm:py-8 pb-32 md:pb-20 overflow-x-hidden print:p-0 print:m-0 text-[#f3f4f6]">
      {/* Workspace Header */}
      <motion.div 
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="space-y-4 mb-6 pb-4 border-b border-[#22242a]"
      >
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="space-y-2">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#f3f4f6] leading-tight print:text-black">
              {displayTitle}
            </h1>

            {/* Metadata Badges */}
            <div className="flex flex-wrap items-center gap-2 text-xs text-[#9ca3af]">
              {displayDate && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[#18191f] border border-[#22242a] text-[11px]">
                  <Calendar className="w-3 h-3 text-[#9ca3af]" />
                  {displayDate}
                </span>
              )}
              {displayDuration && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[#18191f] border border-[#22242a] text-[11px] font-mono">
                  <Clock className="w-3 h-3 text-[#9ca3af]" />
                  {displayDuration}
                </span>
              )}
              {templateConfig && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[#ff5c47]/10 border border-[#ff5c47]/20 text-[#ff5c47] text-[11px] font-medium font-mono uppercase">
                  {templateConfig.badge}
                </span>
              )}
              {session.tags && session.tags.slice(0, 2).map((tag, idx) => (
                <span key={idx} className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[#18191f] border border-[#22242a] text-[11px]">
                  <Tag className="w-2.5 h-2.5 text-[#9ca3af]" />
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="flex items-center gap-1.5 shrink-0 print:hidden">
            <Button
              size="sm"
              variant="outline"
              onClick={handleShareLink}
              className={`h-8 px-2.5 rounded-md text-xs border-[#22242a] bg-[#131418] transition-colors ${
                shareCopied
                  ? "text-[#10b981] border-[#10b981]/40 bg-[#10b981]/10"
                  : "text-[#9ca3af] hover:text-[#f3f4f6] hover:bg-[#18191f]"
              }`}
            >
              {shareCopied ? <Check className="w-3.5 h-3.5 mr-1 text-[#10b981]" /> : <Share2 className="w-3.5 h-3.5 mr-1" />}
              <span>{shareCopied ? "Copied" : "Share"}</span>
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={handleCopyMarkdown}
              className="h-8 px-2.5 rounded-md text-xs border-[#22242a] bg-[#131418] text-[#9ca3af] hover:text-[#f3f4f6] hover:bg-[#18191f] transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 mr-1 text-[#10b981]" /> : <Copy className="w-3.5 h-3.5 mr-1" />}
              <span>{copied ? "Copied" : "Copy"}</span>
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={handleDownloadMarkdown}
              className="h-8 px-2.5 rounded-md text-xs border-[#22242a] bg-[#131418] text-[#9ca3af] hover:text-[#f3f4f6] hover:bg-[#18191f] transition-colors"
            >
              <Download className="w-3.5 h-3.5 mr-1" />
              <span>Export</span>
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => window.print()}
              className="h-8 px-2.5 rounded-md text-xs border-[#22242a] bg-[#131418] text-[#9ca3af] hover:text-[#f3f4f6] hover:bg-[#18191f] transition-colors"
            >
              <Printer className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </motion.div>

      {/* Tabs Container */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="bg-[#131418] border border-[#22242a] p-1 rounded-lg flex flex-nowrap sm:inline-flex gap-1 max-w-full overflow-x-auto no-scrollbar shrink-0 select-none">
          <TabsTrigger
            value="summary"
            className="rounded-md text-xs px-3 py-1.5 data-[state=active]:bg-[#1e2027] data-[state=active]:text-[#f3f4f6] data-[state=active]:shadow-sm text-[#9ca3af] shrink-0 transition-all font-medium"
          >
            <FileText className="w-3.5 h-3.5 mr-1.5" />
            Summary
          </TabsTrigger>
          <TabsTrigger
            value="actions"
            className="rounded-md text-xs px-3 py-1.5 data-[state=active]:bg-[#1e2027] data-[state=active]:text-[#f3f4f6] data-[state=active]:shadow-sm text-[#9ca3af] shrink-0 transition-all font-medium"
          >
            <CheckSquare className="w-3.5 h-3.5 mr-1.5" />
            Action Items ({totalActions})
          </TabsTrigger>
          <TabsTrigger
            value="mindmap"
            className="rounded-md text-xs px-3 py-1.5 data-[state=active]:bg-[#1e2027] data-[state=active]:text-[#f3f4f6] data-[state=active]:shadow-sm text-[#9ca3af] shrink-0 transition-all font-medium"
          >
            <Network className="w-3.5 h-3.5 mr-1.5" />
            Mind Map
          </TabsTrigger>
          <TabsTrigger
            value="transcript"
            className="rounded-md text-xs px-3 py-1.5 data-[state=active]:bg-[#1e2027] data-[state=active]:text-[#f3f4f6] data-[state=active]:shadow-sm text-[#9ca3af] shrink-0 transition-all font-medium"
          >
            <Clock className="w-3.5 h-3.5 mr-1.5" />
            Transcript
          </TabsTrigger>
          {canAccessChat && (
            <TabsTrigger
              value="chat"
              className="rounded-md text-xs px-3 py-1.5 data-[state=active]:bg-[#1e2027] data-[state=active]:text-[#f3f4f6] data-[state=active]:shadow-sm text-[#9ca3af] shrink-0 transition-all font-medium"
            >
              <MessageSquare className="w-3.5 h-3.5 mr-1.5" />
              Chat
            </TabsTrigger>
          )}
        </TabsList>

        {/* TAB 1: SUMMARY */}
        <TabsContent value="summary" className="space-y-6 focus-visible:outline-none">
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="space-y-6"
          >
            {/* Executive Summary Card */}
            {summaryText && (
              <div className="bg-[#131418] border border-[#22242a] rounded-lg p-5 sm:p-6 space-y-2">
                <div className="text-[11px] font-semibold text-[#ff5c47] uppercase tracking-wider font-mono">
                  Executive Brief
                </div>
                <p className="text-sm leading-relaxed text-[#e5e7eb] whitespace-pre-line">{summaryText}</p>
              </div>
            )}

            {/* Key Discussion Pillars / Sections */}
            {pillars.length > 0 && (
              <div className="space-y-4">
                <div className="text-xs font-semibold text-[#9ca3af] uppercase tracking-wider px-1">
                  Discussion Pillars
                </div>
                {pillars.map((sec, idx) => {
                  const n = sec.n || idx + 1;
                  const cleanSecTitle = (sec.title || `Topic ${n}`).replace(/^\d+\.\s*/, "");

                  return (
                    <div
                      key={idx}
                      className="bg-[#131418] border border-[#22242a] rounded-lg p-5 space-y-3"
                    >
                      <h2 className="text-sm font-semibold text-[#f3f4f6]">
                        {n}. {cleanSecTitle}
                      </h2>
                      {sec.narrative && (
                        <p className="text-xs sm:text-sm leading-relaxed text-[#d1d5db] whitespace-pre-line">{sec.narrative}</p>
                      )}

                      {/* Decisions */}
                      {sec.decisions && sec.decisions.length > 0 && (
                        <div className="p-3 bg-[#18191f] border border-[#22242a] rounded-md space-y-1.5">
                          <div className="text-xs font-medium text-[#f3f4f6]">Decisions Agreed:</div>
                          <ul className="space-y-1 text-xs text-[#9ca3af]">
                            {sec.decisions.map((d, dIdx) => (
                              <li key={dIdx} className="flex items-start gap-2">
                                <span className="text-[#10b981] font-bold">•</span>
                                <span>{d}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Inline Action Items */}
                      {sec.action_items && sec.action_items.length > 0 && (
                        <div className="space-y-1.5 pt-1">
                          <div className="text-[11px] font-medium text-[#9ca3af]">
                            Deliverables
                          </div>
                          <div className="space-y-1">
                            {sec.action_items.map((act, aIdx) => (
                              <div
                                key={aIdx}
                                className="flex items-center justify-between p-2 rounded bg-[#18191f] border border-[#22242a] text-xs text-[#f3f4f6]"
                              >
                                <span className="truncate pr-2">
                                  {act.task || act.description}
                                </span>
                                <div className="flex items-center gap-1.5 shrink-0">
                                  <span className="text-[10.5px] px-1.5 py-0.5 rounded bg-[#22242a] text-[#9ca3af]">
                                    {act.owner || act.assignee || "Team"}
                                  </span>
                                  {act.due_date && (
                                    <span className="text-[10.5px] font-mono text-[#9ca3af]">
                                      {act.due_date}
                                    </span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Strategic Insights */}
            {strategicItems.length > 0 && (
              <div className="bg-[#131418] border border-[#22242a] rounded-lg p-5 space-y-3">
                <div className="text-xs font-semibold text-[#ff5c47] uppercase tracking-wider flex items-center gap-1.5">
                  <Lightbulb className="w-3.5 h-3.5" />
                  Strategic Insights & Recommendations
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                  {strategicItems.map((item, idx) => {
                    const itemTitle = item.label || item.title || "Insight";
                    const itemDetail = item.detail || item.body || item.text || "";
                    return (
                      <div key={idx} className="p-3 rounded-md bg-[#18191f] border border-[#22242a] space-y-1">
                        <div className="text-xs font-medium text-[#f3f4f6]">{itemTitle}</div>
                        {itemDetail && <p className="text-xs text-[#9ca3af] leading-relaxed">{itemDetail}</p>}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Open Questions */}
            {session.open_questions && session.open_questions.length > 0 && (
              <div className="bg-[#131418] border border-[#22242a] border-l-2 border-l-amber-500 rounded-lg p-5 space-y-2">
                <div className="text-xs font-semibold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                  <HelpCircle className="w-3.5 h-3.5" />
                  Open Questions & Dependencies
                </div>
                <ul className="space-y-1.5 text-xs text-[#d1d5db]">
                  {session.open_questions.map((q, idx) => {
                    const qText = typeof q === "string" ? q : q.question;
                    const raisedBy = typeof q === "object" ? q.raised_by : "";
                    return (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-amber-400 font-bold">•</span>
                        <span>
                          {qText}
                          {raisedBy && <span className="text-[#9ca3af] ml-1">({raisedBy})</span>}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {/* Fallback if raw text */}
            {!summaryText && pillars.length === 0 && session.raw_markdown && (
              <div className="bg-[#131418] border border-[#22242a] rounded-lg p-5 space-y-3">
                <pre className="text-xs text-[#f3f4f6] whitespace-pre-wrap font-sans leading-relaxed">
                  {session.raw_markdown}
                </pre>
              </div>
            )}
          </motion.div>
        </TabsContent>

        {/* TAB 2: ACTION ITEMS */}
        <TabsContent value="actions" className="space-y-4 focus-visible:outline-none">
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="space-y-4"
          >
            {/* Progress Header */}
            <div className="bg-[#131418] border border-[#22242a] rounded-lg p-4 flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold text-[#f3f4f6]">
                  Deliverables Checklist
                </div>
                <div className="text-xs text-[#9ca3af]">
                  {completedActions} of {totalActions} tasks completed ({completionPercent}%)
                </div>
              </div>
              <div className="w-32 h-1.5 bg-[#18191f] rounded overflow-hidden">
                <div
                  className="h-full bg-[#ff5c47] rounded transition-all duration-300"
                  style={{ width: `${completionPercent}%` }}
                />
              </div>
            </div>

            {/* Checklist */}
            <div className="space-y-1.5">
              {actionItems.map((item, idx) => {
                const isDone = item.status === "completed";
                const taskText = item.task || item.description || "Deliverable";

                return (
                  <div
                    key={idx}
                    onClick={() => toggleActionStatus(idx)}
                    className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors ${
                      isDone
                        ? "bg-[#131418]/60 border-[#22242a] text-[#9ca3af]"
                        : "bg-[#131418] border-[#22242a] text-[#f3f4f6] hover:border-[#2e3238]"
                    }`}
                  >
                    <div className="flex items-center gap-3 truncate pr-2">
                      <div
                        className={`w-4 h-4 rounded border flex items-center justify-center transition-colors shrink-0 ${
                          isDone
                            ? "bg-[#ff5c47] border-[#ff5c47] text-white"
                            : "border-[#3b3e4a] bg-[#18191f]"
                        }`}
                      >
                        {isDone && <Check className="w-3 h-3 stroke-[3]" />}
                      </div>
                      <span className={`text-xs truncate ${isDone ? "line-through text-[#9ca3af]" : "font-medium"}`}>
                        {taskText}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <span className="text-[10.5px] px-2 py-0.5 rounded bg-[#18191f] border border-[#22242a] text-[#9ca3af]">
                        {item.owner || item.assignee || "Team"}
                      </span>
                      {item.priority === "HIGH" && (
                        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-[#ff5c47]/10 text-[#ff5c47] border border-[#ff5c47]/20">
                          HIGH
                        </span>
                      )}
                      {item.due_date && (
                        <span className="text-[10.5px] font-mono text-[#9ca3af]">
                          {item.due_date}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
              {actionItems.length === 0 && (
                <div className="p-8 text-center text-xs text-[#9ca3af] bg-[#131418] border border-[#22242a] rounded-lg">
                  No action items identified for this session.
                </div>
              )}
            </div>
          </motion.div>
        </TabsContent>

        {/* TAB 3: MIND MAP */}
        <TabsContent value="mindmap" className="focus-visible:outline-none">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
          >
            <MindmapView session={session} />
          </motion.div>
        </TabsContent>

        {/* TAB 4: TRANSCRIPT */}
        <TabsContent value="transcript" className="space-y-4 focus-visible:outline-none">
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="bg-[#131418] border border-[#22242a] rounded-lg p-5 space-y-3"
          >
            <div className="text-xs font-semibold text-[#9ca3af] uppercase tracking-wider mb-2">
              Diarized Transcript
            </div>

            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {transcriptSegments.map((seg, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-md bg-[#18191f] border border-[#22242a] space-y-1 hover:border-[#2e3238] transition-colors"
                >
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold px-1.5 py-0.5 rounded bg-[#22242a] text-[#f3f4f6] text-[10.5px]">
                        {seg.speaker || "Speaker 1"}
                      </span>
                      <span className="font-mono text-[11px] text-[#9ca3af]">
                        {seg.timestamp || "00:00"}
                      </span>
                    </div>

                    {seg.seconds !== undefined && onSeekAudio && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onSeekAudio(seg.seconds || 0)}
                        className="h-6 px-2 text-[11px] text-[#ff5c47] hover:bg-[#ff5c47]/10 rounded-md"
                      >
                        Play from here
                      </Button>
                    )}
                  </div>
                  <div className="text-xs leading-relaxed text-[#e5e7eb]">{seg.text}</div>
                </div>
              ))}

              {transcriptSegments.length === 0 && (
                <div className="p-8 text-center text-xs text-[#9ca3af]">
                  {fullTranscriptText || "No transcript turns available."}
                </div>
              )}
            </div>
          </motion.div>
        </TabsContent>

        {/* TAB 5: CHAT ASSISTANT */}
        {canAccessChat && (
          <TabsContent value="chat" className="space-y-4 focus-visible:outline-none">
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              <ChatAssistant sessionId={sessionId} meetingTitle={displayTitle} />
            </motion.div>
          </TabsContent>
        )}
      </Tabs>

      {/* Mobile Bottom Navigation */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[#121316]/95 backdrop-blur-md border-t border-[#22242a] px-2 py-1 flex items-center justify-around">
        {[
          { id: "summary", label: "Summary", icon: FileText },
          { id: "actions", label: "Actions", icon: CheckSquare, count: totalActions },
          { id: "mindmap", label: "Mind Map", icon: Network },
          { id: "transcript", label: "Transcript", icon: Clock },
          ...(canAccessChat ? [{ id: "chat", label: "Chat", icon: MessageSquare }] : []),
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => {
                setActiveTab(tab.id);
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
              className={`flex flex-col items-center justify-center py-1 px-2 rounded-md transition-colors relative ${
                isActive
                  ? "text-[#ff5c47] font-semibold"
                  : "text-[#9ca3af] hover:text-[#f3f4f6]"
              }`}
            >
              <div className="relative">
                <Icon className={`w-4 h-4 mb-0.5 ${isActive ? "text-[#ff5c47]" : "text-[#9ca3af]"}`} />
                {tab.count !== undefined && tab.count > 0 && (
                  <span className="absolute -top-1 -right-2 w-3.5 h-3.5 bg-[#ff5c47] text-white text-[9px] font-bold rounded-full flex items-center justify-center">
                    {tab.count}
                  </span>
                )}
              </div>
              <span className="text-[10px]">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
