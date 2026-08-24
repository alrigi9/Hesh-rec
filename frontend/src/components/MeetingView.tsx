"use client";

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
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
  Sparkles, 
  Send,
  Loader2,
  HelpCircle,
  Lightbulb,
  AlertCircle,
  Share2,
  Link as LinkIcon
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MeetingSession, ActionItem, MeetingSection, TranscriptSegment } from "@/types/meeting";
import { MindmapView } from "@/components/MindmapView";
import { askMeetingAssistant, togglePublicSession } from "@/lib/api";
import { formatMeetingTitle } from "@/lib/utils";

interface MeetingViewProps {
  session: MeetingSession;
  onSeekAudio?: (seconds: number) => void;
}

export function MeetingView({ session, onSeekAudio }: MeetingViewProps) {
  // Console debugging for inspecting exact API payloads in DevTools
  console.log("Current Active Session Data:", session);

  const [activeTab, setActiveTab] = useState("summary");
  const [copied, setCopied] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

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

  // Strategic Insights / AI Suggestions extraction
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

  // Sync action items when session changes
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
    // Reset to summary tab when switching sessions
    setActiveTab("summary");
    setMessages([]);
  }, [session.metadata?.session_id, session.title, session.id]);

  // Chat State
  const [messages, setMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  // Title cleaner
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
        togglePublicSession(session.id, true);
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

  const handleSendChat = async (promptText?: string) => {
    const query = promptText || chatInput.trim();
    if (!query || chatLoading) return;

    const newMessages = [...messages, { role: "user", content: query }];
    setMessages(newMessages);
    setChatInput("");
    setChatLoading(true);

    try {
      const answer = await askMeetingAssistant(session, query, newMessages);
      setMessages([...newMessages, { role: "assistant", content: answer }]);
    } catch {
      setMessages([
        ...newMessages,
        {
          role: "assistant",
          content: "Sorry, I encountered an issue analyzing this meeting context.",
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const totalActions = actionItems.length;
  const completedActions = actionItems.filter((a) => a.status === "completed").length;
  const completionPercent = totalActions > 0 ? Math.round((completedActions / totalActions) * 100) : 0;
  const displayDate = session.meeting_date || session.date;
  const displayDuration = session.metadata?.duration || session.duration || (session.duration_minutes ? `${session.duration_minutes}m` : null);

  return (
    <div className="max-w-4xl mx-auto px-3 sm:px-6 py-4 sm:py-8 pb-28 md:pb-12 overflow-x-hidden print:p-0 print:m-0">
      {/* Editorial Header */}
      <motion.div 
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="space-y-4 mb-6 sm:mb-8"
      >
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#f0f2f5] font-heading break-words leading-tight print:text-black">
          {displayTitle}
        </h1>

        {/* Floating Metadata Pills */}
        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 text-xs">
          {displayDuration && (
            <span className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-full bg-[#18191c] border border-[#232529] text-[#8b909a] font-mono text-[11px] sm:text-xs">
              <Clock className="w-3 h-3 text-[#ff5c47]" />
              {displayDuration}
            </span>
          )}
          {displayDate && (
            <span className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-full bg-[#18191c] border border-[#232529] text-[#8b909a] text-[11px] sm:text-xs">
              <Calendar className="w-3 h-3 text-[#ff5c47]" />
              {displayDate}
            </span>
          )}
          {session.tags && session.tags.slice(0, 3).map((tag, idx) => (
            <span key={idx} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#18191c] border border-[#232529] text-[#8b909a] text-[11px]">
              <Tag className="w-2.5 h-2.5 text-[#ff5c47]" />
              {tag}
            </span>
          ))}
          {/* Strict RecMap Intelligence Engine Pill */}
          <span className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-full bg-[#ff5c47]/10 border border-[#ff5c47]/20 text-[#ff5c47] text-[11px] sm:text-xs font-medium">
            <Sparkles className="w-3 h-3" />
            RecMap Intelligence
          </span>
        </div>

        {/* Action Toolbar */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-b border-[#232529] pb-4 sm:pb-6 print:hidden">
          <Button
            size="sm"
            variant="outline"
            onClick={handleShareLink}
            className={`h-8 px-3 rounded-full text-xs border-[#232529] bg-[#141517] shrink-0 transition-all ${
              shareCopied
                ? "text-[#3ec98a] border-[#3ec98a]/40 bg-[#3ec98a]/10"
                : "text-[#8b909a] hover:text-[#f0f2f5] hover:bg-[#1c1e22]"
            }`}
          >
            {shareCopied ? (
              <Check className="w-3.5 h-3.5 mr-1.5 text-[#3ec98a]" />
            ) : (
              <Share2 className="w-3.5 h-3.5 mr-1.5 text-[#ff5c47]" />
            )}
            {shareCopied ? "Link Copied!" : "Share"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleCopyMarkdown}
            className="h-8 px-3 rounded-full text-xs border-[#232529] bg-[#141517] text-[#8b909a] hover:text-[#f0f2f5] hover:bg-[#1c1e22] shrink-0 transition-colors"
          >
            {copied ? <Check className="w-3.5 h-3.5 mr-1.5 text-[#3ec98a]" /> : <Copy className="w-3.5 h-3.5 mr-1.5 text-[#ff5c47]" />}
            {copied ? "Copied!" : "Copy Summary"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleDownloadMarkdown}
            className="h-8 px-3 rounded-full text-xs border-[#232529] bg-[#141517] text-[#8b909a] hover:text-[#f0f2f5] hover:bg-[#1c1e22] shrink-0 transition-colors"
          >
            <Download className="w-3.5 h-3.5 mr-1.5 text-[#ff5c47]" />
            Export Markdown
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => window.print()}
            className="h-8 px-3 rounded-full text-xs border-[#232529] bg-[#141517] text-[#8b909a] hover:text-[#f0f2f5] hover:bg-[#1c1e22] shrink-0 transition-colors"
          >
            <Printer className="w-3.5 h-3.5 mr-1.5 text-[#ff5c47]" />
            Print / PDF
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleDownloadJSON}
            className="h-8 px-3 rounded-full text-xs border-[#232529] bg-[#141517] text-[#8b909a] hover:text-[#f0f2f5] hover:bg-[#1c1e22] shrink-0 transition-colors"
          >
            <Download className="w-3.5 h-3.5 mr-1.5" />
            JSON
          </Button>
        </div>
      </motion.div>

      {/* Tabs Container */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="bg-[#141517] border border-[#232529] p-1 rounded-2xl sm:rounded-full flex flex-nowrap sm:inline-flex gap-1 max-w-full overflow-x-auto no-scrollbar shrink-0 select-none">
          <TabsTrigger
            value="summary"
            className="rounded-full text-xs px-3.5 sm:px-4 py-1.5 data-[state=active]:bg-[#1c1e22] data-[state=active]:text-[#f0f2f5] text-[#8b909a] shrink-0 transition-all"
          >
            <FileText className="w-3.5 h-3.5 mr-1.5" />
            Summary
          </TabsTrigger>
          <TabsTrigger
            value="actions"
            className="rounded-full text-xs px-3.5 sm:px-4 py-1.5 data-[state=active]:bg-[#1c1e22] data-[state=active]:text-[#f0f2f5] text-[#8b909a] shrink-0 transition-all"
          >
            <CheckSquare className="w-3.5 h-3.5 mr-1.5" />
            Action Items ({totalActions})
          </TabsTrigger>
          <TabsTrigger
            value="mindmap"
            className="rounded-full text-xs px-4 py-1.5 data-[state=active]:bg-[#1c1e22] data-[state=active]:text-[#f0f2f5] text-[#8b909a] shrink-0 transition-all"
          >
            <Network className="w-3.5 h-3.5 mr-1.5" />
            Mind Map
          </TabsTrigger>
          <TabsTrigger
            value="transcript"
            className="rounded-full text-xs px-4 py-1.5 data-[state=active]:bg-[#1c1e22] data-[state=active]:text-[#f0f2f5] text-[#8b909a] shrink-0 transition-all"
          >
            <Clock className="w-3.5 h-3.5 mr-1.5" />
            Transcript
          </TabsTrigger>
          <TabsTrigger
            value="chat"
            className="rounded-full text-xs px-4 py-1.5 data-[state=active]:bg-[#1c1e22] data-[state=active]:text-[#f0f2f5] text-[#8b909a] shrink-0 transition-all"
          >
            <MessageSquare className="w-3.5 h-3.5 mr-1.5" />
            Chat
          </TabsTrigger>
        </TabsList>

        {/* TAB 1: SUMMARY (Default Visible directly under tab bar) */}
        <TabsContent value="summary" className="space-y-8 focus-visible:outline-none">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="space-y-8"
          >
            {/* Executive Summary Card */}
            {summaryText && (
              <div className="bg-[#141517] border border-[#232529] rounded-2xl p-6 shadow-sm">
                <div className="text-xs font-bold text-[#ff5c47] uppercase tracking-wider mb-2 font-heading">
                  Executive Brief
                </div>
                <p className="text-sm leading-relaxed text-[#f0f2f5] whitespace-pre-line">{summaryText}</p>
              </div>
            )}

            {/* Key Discussion Pillars / Sections */}
            {pillars.length > 0 && (
              <div className="space-y-6">
                {pillars.map((sec, idx) => {
                  const n = sec.n || idx + 1;
                  const cleanSecTitle = (sec.title || `Topic ${n}`).replace(/^\d+\.\s*/, "");

                  return (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.25, delay: idx * 0.05 }}
                      className="bg-[#141517] border border-[#232529] rounded-2xl p-6 space-y-4 shadow-sm hover:border-[#2e3238] transition-colors"
                    >
                      <h2 className="text-lg font-bold text-[#f0f2f5] font-heading">
                        {n}. {cleanSecTitle}
                      </h2>
                      {sec.narrative && (
                        <p className="text-sm leading-relaxed text-[#f0f2f5] whitespace-pre-line">{sec.narrative}</p>
                      )}

                      {/* Decisions */}
                      {sec.decisions && sec.decisions.length > 0 && (
                        <div className="p-4 bg-[#18191c] border border-[#232529] rounded-xl space-y-2">
                          <div className="text-xs font-semibold text-[#f0f2f5]">Decisions Agreed:</div>
                          <ul className="space-y-1 text-xs text-[#8b909a]">
                            {sec.decisions.map((d, dIdx) => (
                              <li key={dIdx} className="flex items-start gap-2">
                                <span className="text-[#3ec98a] font-bold">•</span>
                                <span>{d}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Inline Action Items */}
                      {sec.action_items && sec.action_items.length > 0 && (
                        <div className="space-y-2 pt-2">
                          <div className="text-xs font-semibold text-[#8b909a] uppercase tracking-wider">
                            Deliverables
                          </div>
                          <div className="space-y-1.5">
                            {sec.action_items.map((act, aIdx) => (
                              <div
                                key={aIdx}
                                className="flex items-center justify-between p-2.5 rounded-xl bg-[#18191c] border border-[#232529] text-xs text-[#f0f2f5]"
                              >
                                <span className="truncate">
                                  {act.task || act.description}
                                </span>
                                <div className="flex items-center gap-2 shrink-0">
                                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-[#232529] text-[#8b909a]">
                                    {act.owner || act.assignee || "Team"}
                                  </span>
                                  {act.due_date && (
                                    <span className="text-[11px] font-mono text-[#8b909a]">
                                      {act.due_date}
                                    </span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </motion.div>
                  );
                })}
              </div>
            )}

            {/* Strategic Insights / AI Suggestions */}
            {strategicItems.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className="bg-[#141517] border border-[#232529] rounded-2xl p-6 space-y-4 shadow-sm"
              >
                <div className="text-xs font-bold text-[#ff5c47] uppercase tracking-wider flex items-center gap-1.5">
                  <Lightbulb className="w-4 h-4 text-[#ff5c47]" />
                  Strategic Insights & Recommendations
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {strategicItems.map((item, idx) => {
                    const itemTitle = item.label || item.title || "Insight";
                    const itemDetail = item.detail || item.body || item.text || "";
                    return (
                      <div key={idx} className="p-3.5 rounded-xl bg-[#18191c] border border-[#232529] space-y-1">
                        <div className="text-xs font-semibold text-[#f0f2f5]">{itemTitle}</div>
                        {itemDetail && <p className="text-xs text-[#8b909a] leading-relaxed">{itemDetail}</p>}
                      </div>
                    );
                  })}
                </div>
              </motion.div>
            )}

            {/* Open Questions */}
            {session.open_questions && session.open_questions.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className="bg-[#141517] border border-[#232529] border-l-4 border-l-[#f9ab00] rounded-2xl p-6 space-y-3"
              >
                <div className="text-xs font-bold text-[#f9ab00] uppercase tracking-wider flex items-center gap-1.5">
                  <HelpCircle className="w-4 h-4" />
                  Open Questions & Unresolved Items
                </div>
                <ul className="space-y-2 text-xs text-[#f0f2f5]">
                  {session.open_questions.map((q, idx) => {
                    const qText = typeof q === "string" ? q : q.question;
                    const raisedBy = typeof q === "object" ? q.raised_by : "";
                    return (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-[#f9ab00] font-bold">•</span>
                        <span>
                          {qText}
                          {raisedBy && <em className="text-[#8b909a] ml-1">({raisedBy})</em>}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </motion.div>
            )}

            {/* Fallback if no structured sections exist yet */}
            {!summaryText && pillars.length === 0 && session.raw_markdown && (
              <div className="bg-[#141517] border border-[#232529] rounded-2xl p-6 space-y-4">
                <pre className="text-xs text-[#f0f2f5] whitespace-pre-wrap font-sans leading-relaxed">
                  {session.raw_markdown}
                </pre>
              </div>
            )}
          </motion.div>
        </TabsContent>

        {/* TAB 2: ACTION ITEMS MANAGER */}
        <TabsContent value="actions" className="space-y-6 focus-visible:outline-none">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="space-y-6"
          >
            {/* Progress Header */}
            <div className="bg-[#141517] border border-[#232529] rounded-2xl p-6 flex items-center justify-between shadow-sm">
              <div>
                <div className="text-base font-semibold text-[#f0f2f5] font-heading">
                  Action Items Tracker
                </div>
                <div className="text-xs text-[#8b909a]">
                  {completedActions} of {totalActions} tasks completed ({completionPercent}%)
                </div>
              </div>
              <div className="w-36 h-2 bg-[#232529] rounded-full overflow-hidden">
                <div
                  className="h-full bg-[#ff5c47] rounded-full transition-all duration-300"
                  style={{ width: `${completionPercent}%` }}
                />
              </div>
            </div>

            {/* Checklist */}
            <div className="space-y-2">
              {actionItems.map((item, idx) => {
                const isDone = item.status === "completed";
                const taskText = item.task || item.description || "Deliverable";

                return (
                  <div
                    key={idx}
                    onClick={() => toggleActionStatus(idx)}
                    className={`flex items-center justify-between p-3.5 rounded-2xl border cursor-pointer transition-all ${
                      isDone
                        ? "bg-[#141517]/50 border-[#232529]/60 text-[#8b909a]"
                        : "bg-[#141517] border-[#232529] text-[#f0f2f5] hover:border-[#2e3238]"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-5 h-5 rounded-md border flex items-center justify-center transition-colors ${
                          isDone
                            ? "bg-[#ff5c47] border-[#ff5c47] text-white"
                            : "border-[#3e434c] bg-[#18191c]"
                        }`}
                      >
                        {isDone && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                      </div>
                      <span className={`text-xs ${isDone ? "line-through text-[#8b909a]" : "font-medium"}`}>
                        {taskText}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-[#1c1e22] border border-[#232529] text-[#8b909a]">
                        {item.owner || item.assignee || "Team"}
                      </span>
                      {item.priority === "HIGH" && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#ff5c47]/10 text-[#ff5c47] border border-[#ff5c47]/20">
                          HIGH
                        </span>
                      )}
                      {item.due_date && (
                        <span className="text-[11px] font-mono text-[#8b909a]">
                          {item.due_date}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
              {actionItems.length === 0 && (
                <div className="p-8 text-center text-xs text-[#8b909a] bg-[#141517] border border-[#232529] rounded-2xl">
                  No action items identified for this session.
                </div>
              )}
            </div>
          </motion.div>
        </TabsContent>

        {/* TAB 3: MIND MAP */}
        <TabsContent value="mindmap" className="focus-visible:outline-none">
          <motion.div
            initial={{ opacity: 0, scale: 0.99 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3 }}
          >
            <MindmapView session={session} />
          </motion.div>
        </TabsContent>

        {/* TAB 4: TRANSCRIPT */}
        <TabsContent value="transcript" className="space-y-4 focus-visible:outline-none">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="bg-[#141517] border border-[#232529] rounded-2xl p-6 space-y-3 shadow-sm"
          >
            <div className="text-xs font-semibold text-[#8b909a] uppercase tracking-wider mb-2">
              Diarized Transcript
            </div>

            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-2">
              {transcriptSegments.map((seg, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-[#18191c] border border-[#232529] space-y-1.5 hover:border-[#2e3238] transition-colors"
                >
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold px-2 py-0.5 rounded-full bg-[#232529] text-[#f0f2f5] text-[11px]">
                        {seg.speaker || "Speaker 1"}
                      </span>
                      <span className="font-mono text-[11px] text-[#8b909a]">
                        {seg.timestamp || "00:00"}
                      </span>
                    </div>

                    {seg.seconds !== undefined && onSeekAudio && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onSeekAudio(seg.seconds || 0)}
                        className="h-6 px-2 text-[11px] text-[#ff5c47] hover:bg-[#ff5c47]/10 rounded-full"
                      >
                        Play from here
                      </Button>
                    )}
                  </div>
                  <div className="text-xs leading-relaxed text-[#f0f2f5]">{seg.text}</div>
                </div>
              ))}

              {transcriptSegments.length === 0 && (
                <div className="p-8 text-center text-xs text-[#8b909a]">
                  {fullTranscriptText || "No transcript turns available."}
                </div>
              )}
            </div>
          </motion.div>
        </TabsContent>

        {/* TAB 5: CHAT ASSISTANT */}
        <TabsContent value="chat" className="space-y-6 focus-visible:outline-none">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="bg-[#141517] border border-[#232529] rounded-2xl p-6 min-h-[500px] flex flex-col justify-between shadow-sm"
          >
            {/* Messages Stream */}
            <div className="space-y-4 overflow-y-auto max-h-[420px] pr-2">
              {messages.length === 0 ? (
                <div className="space-y-4 py-8">
                  <div className="text-center space-y-1">
                    <div className="w-10 h-10 rounded-full bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47] mx-auto">
                      <Sparkles className="w-5 h-5" />
                    </div>
                    <div className="text-sm font-semibold text-[#f0f2f5] font-heading">
                      Meeting Assistant
                    </div>
                    <div className="text-xs text-[#8b909a]">
                      Ask specific questions grounded in this meeting transcript and decisions.
                    </div>
                  </div>

                  {/* Clickable Starter Pills */}
                  <div className="flex flex-wrap justify-center gap-2 pt-2">
                    {[
                      "What were the key decisions?",
                      "List all action items with owners",
                      "Summarize next steps and deadlines",
                    ].map((prompt, pIdx) => (
                      <button
                        key={pIdx}
                        onClick={() => handleSendChat(prompt)}
                        className="px-3.5 py-1.5 rounded-full bg-[#18191c] border border-[#232529] text-xs text-[#8b909a] hover:text-[#f0f2f5] hover:border-[#ff5c47]/50 hover:bg-[#ff5c47]/5 transition-all"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((m, mIdx) => (
                  <div
                    key={mIdx}
                    className={`flex gap-3 ${
                      m.role === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div
                      className={`p-3.5 rounded-2xl text-xs leading-relaxed max-w-[80%] ${
                        m.role === "user"
                          ? "bg-[#ff5c47] text-white rounded-br-none"
                          : "bg-[#18191c] border border-[#232529] text-[#f0f2f5] rounded-bl-none"
                      }`}
                    >
                      {m.content}
                    </div>
                  </div>
                ))
              )}

              {chatLoading && (
                <div className="flex items-center gap-2 text-xs text-[#8b909a] p-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[#ff5c47]" />
                  <span>Analyzing meeting context...</span>
                </div>
              )}
            </div>

            {/* Pinned Pill Input */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendChat();
              }}
              className="relative mt-4"
            >
              <input
                type="text"
                placeholder="Ask a question about this meeting..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                disabled={chatLoading}
                className="w-full h-11 pl-4 pr-12 bg-[#18191c] border border-[#232529] rounded-full text-xs text-[#f0f2f5] placeholder-[#8b909a] focus:outline-none focus:border-[#ff5c47]/60 transition-colors shadow-inner"
              />
              <Button
                type="submit"
                size="icon"
                disabled={chatLoading || !chatInput.trim()}
                className="w-8 h-8 rounded-full bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white absolute right-1.5 top-1/2 -translate-y-1/2 shadow-sm"
              >
                <Send className="w-3.5 h-3.5" />
              </Button>
            </form>
          </motion.div>
        </TabsContent>
      </Tabs>

      {/* Mobile Floating Bottom Navigation Bar */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[#0A0B0F]/95 backdrop-blur-lg border-t border-white/[0.08] px-2 py-1.5 flex items-center justify-around shadow-2xl safe-area-bottom">
        {[
          { id: "summary", label: "Summary", icon: FileText },
          { id: "actions", label: "Actions", icon: CheckSquare, count: totalActions },
          { id: "mindmap", label: "Mind Map", icon: Network },
          { id: "transcript", label: "Transcript", icon: Clock },
          { id: "chat", label: "Chat", icon: MessageSquare },
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
              className={`flex flex-col items-center justify-center py-1 px-2.5 rounded-xl transition-all relative ${
                isActive
                  ? "text-[#ff5c47] font-semibold"
                  : "text-[#8b909a] hover:text-[#f0f2f5]"
              }`}
            >
              <div className="relative">
                <Icon className={`w-4 h-4 mb-0.5 ${isActive ? "text-[#ff5c47]" : "text-[#8b909a]"}`} />
                {tab.count !== undefined && tab.count > 0 && (
                  <span className="absolute -top-1 -right-2 bg-[#ff5c47] text-white text-[9px] font-bold rounded-full w-3.5 h-3.5 flex items-center justify-center">
                    {tab.count}
                  </span>
                )}
              </div>
              <span className="text-[10px] tracking-tight">{tab.label}</span>
              {isActive && (
                <div className="w-1 h-1 rounded-full bg-[#ff5c47] absolute -bottom-0.5" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
