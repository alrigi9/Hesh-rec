"use client";

import React, { useState } from "react";
import { 
  Plus, 
  Search, 
  Layers, 
  CheckSquare, 
  FileText, 
  Sparkles, 
  Clock, 
  Tag, 
  ChevronRight,
  AudioWaveform,
  ShieldCheck
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MeetingSession } from "@/types/meeting";
import { formatMeetingTitle } from "@/lib/utils";

interface SidebarProps {
  sessions: MeetingSession[];
  activeSessionId: string | null;
  onSelectSession: (session: MeetingSession) => void;
  onOpenUpload: () => void;
}

export function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onOpenUpload,
}: SidebarProps) {
  const [search, setSearch] = useState("");

  const filteredSessions = sessions.filter((s) => {
    const q = search.toLowerCase();
    const title = (s.title || "").toLowerCase();
    const tags = (s.tags || []).join(" ").toLowerCase();
    return title.includes(q) || tags.includes(q);
  });

  return (
    <aside className="w-64 h-screen bg-[#111215] border-r border-[#232529] flex flex-col flex-shrink-0 select-none">
      {/* Brand Header */}
      <div className="p-4 flex items-center justify-between border-b border-[#232529]/60">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47]">
            <AudioWaveform className="w-4 h-4" />
          </div>
          <div>
            <div className="font-semibold text-sm tracking-tight text-[#f0f2f5] flex items-center gap-1.5 font-heading">
              Hesh Rec
              <span className="text-[10px] text-[#8b909a] font-normal px-1.5 py-0.5 rounded-full bg-[#1c1e22] border border-[#232529]">
                v2.4
              </span>
            </div>
            <div className="text-[11px] text-[#8b909a]">SOC 2 Speech Studio</div>
          </div>
        </div>
      </div>

      {/* Primary Action Button */}
      <div className="p-3">
        <Button
          onClick={onOpenUpload}
          className="w-full h-9 bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-medium rounded-full text-xs shadow-sm flex items-center justify-center gap-1.5 transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
          New Session
        </Button>
      </div>

      {/* Search Bar */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[#8b909a]" />
          <input
            type="text"
            placeholder="Search meetings..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-8 pl-8 pr-3 bg-[#18191c] text-xs text-[#f0f2f5] placeholder-[#8b909a] rounded-lg border border-[#232529] focus:outline-none focus:border-[#ff5c47]/50 transition-colors"
          />
        </div>
      </div>

      {/* Session History Stream */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
        <div className="px-2 py-1.5 text-[10px] font-semibold tracking-wider text-[#8b909a] uppercase">
          Recent Sessions ({filteredSessions.length})
        </div>

        {filteredSessions.length === 0 ? (
          <div className="px-3 py-6 text-center text-xs text-[#8b909a]">
            {search ? "No matches found" : "No sessions yet. Upload audio to begin."}
          </div>
        ) : (
          filteredSessions.map((s, idx) => {
            const sid = s.metadata?.session_id || s.id || `session_${idx}`;
            const isActive = activeSessionId === sid;
            const tag = s.tags?.[0] || "Meeting";

            return (
              <button
                key={sid}
                onClick={() => onSelectSession(s)}
                className={`w-full text-left px-2.5 py-2 rounded-lg text-xs transition-all flex flex-col gap-1 ${
                  isActive
                    ? "bg-[#1c1e22] text-[#f0f2f5] border border-[#2e3238]"
                    : "text-[#8b909a] hover:text-[#f0f2f5] hover:bg-[#16171a]"
                }`}
              >
                <div className="font-medium text-[12.5px] truncate text-[#f0f2f5] flex items-center justify-between">
                  <span className="truncate">{formatMeetingTitle(s.title, s.meeting_date)}</span>
                  {isActive && (
                    <span className="w-1.5 h-1.5 rounded-full bg-[#ff5c47] shrink-0" />
                  )}
                </div>
                <div className="flex items-center gap-2 text-[11px] text-[#8b909a]">
                  <span className="flex items-center gap-1 font-mono">
                    <Clock className="w-3 h-3 text-[#8b909a]" />
                    {s.metadata?.duration || `${s.duration_minutes || 0}m`}
                  </span>
                  <span>•</span>
                  <span className="truncate">#{tag.replace(/^#/, "")}</span>
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Footer Tenant Tag */}
      <div className="p-3 border-t border-[#232529]/60 flex items-center justify-between text-xs text-[#8b909a]">
        <div className="flex items-center gap-1.5 text-[11px]">
          <ShieldCheck className="w-3.5 h-3.5 text-[#3ec98a]" />
          <span>SOC 2 Compliant</span>
        </div>
        <Badge variant="outline" className="text-[10px] py-0 px-2 border-[#2e3238] bg-[#16171a] text-[#8b909a]">
          Pro
        </Badge>
      </div>
    </aside>
  );
}
