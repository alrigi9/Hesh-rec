"use client";

import React, { useState } from "react";
import Link from "next/link";
import { 
  Plus, 
  Search, 
  Clock, 
  AudioWaveform,
  ShieldCheck,
  ShieldAlert,
  Sliders,
  LogIn,
  LogOut,
  User,
  Sparkles,
  X
} from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MeetingSession } from "@/types/meeting";
import { formatMeetingTitle } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";

interface SidebarProps {
  sessions: MeetingSession[];
  activeSessionId: string | null;
  onSelectSession: (session: MeetingSession) => void;
  onOpenUpload: () => void;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onOpenUpload,
  isMobileOpen = false,
  onCloseMobile,
}: SidebarProps) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const { user, profile, isAdmin, signOut } = useAuth();

  const filteredSessions = sessions.filter((s) => {
    const q = search.toLowerCase();
    const title = (s.title || "").toLowerCase();
    const tags = (s.tags || []).join(" ").toLowerCase();
    return title.includes(q) || tags.includes(q);
  });

  const minutesUsed = profile?.minutes_used_this_month ?? 0.0;
  const minutesLimit = profile?.monthly_minutes_limit ?? 300.0;
  const percentUsed = Math.min(100, Math.round((minutesUsed / minutesLimit) * 100));
  const isQuotaExceeded = minutesUsed >= minutesLimit && !isAdmin;

  const handleSelect = (s: MeetingSession) => {
    onSelectSession(s);
    if (onCloseMobile) onCloseMobile();
  };

  const handleUploadClick = () => {
    if (!user) {
      if (onCloseMobile) onCloseMobile();
      router.push(
        "/login?msg=" +
          encodeURIComponent("Please sign in or create an account to transcribe audio (300 free mins/month)")
      );
      return;
    }
    onOpenUpload();
    if (onCloseMobile) onCloseMobile();
  };

  const sidebarContent = (
    <div className="flex flex-col h-full select-none">
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

        {/* Mobile Close Button */}
        {onCloseMobile && (
          <Button
            size="icon"
            variant="ghost"
            onClick={onCloseMobile}
            className="md:hidden w-8 h-8 rounded-full text-[#8b909a] hover:text-[#f0f2f5] hover:bg-[#1c1e22]"
          >
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>

      {/* Primary Action Button */}
      <div className="p-3 space-y-2">
        <Button
          onClick={handleUploadClick}
          disabled={isQuotaExceeded}
          className="w-full h-9 bg-[#ff5c47] hover:bg-[#ff5c47]/90 disabled:opacity-50 text-white font-medium rounded-full text-xs shadow-sm flex items-center justify-center gap-1.5 transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>{isQuotaExceeded ? "Quota Limit Reached" : "New Session"}</span>
        </Button>

        {/* Admin Dashboard shortcut if admin */}
        {isAdmin && (
          <Link href="/admin" onClick={onCloseMobile} className="block">
            <Button
              variant="outline"
              className="w-full h-8 rounded-full text-xs border-[#ff5c47]/30 bg-[#ff5c47]/5 text-[#ff5c47] hover:bg-[#ff5c47]/10 flex items-center justify-center gap-1.5 transition-all"
            >
              <Sliders className="w-3 h-3" />
              <span>Admin Dashboard</span>
            </Button>
          </Link>
        )}
      </div>

      {/* Monthly Quota Badge Card */}
      <div className="px-3 pb-2">
        <div className="p-2.5 rounded-xl bg-[#141517] border border-[#232529] space-y-1.5">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-[#8b909a] flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-[#ff5c47]" />
              Monthly Quota
            </span>
            <span className="font-mono text-[#f0f2f5] font-medium">
              {minutesUsed.toFixed(1)} / {minutesLimit.toFixed(0)}m
            </span>
          </div>
          
          <div className="w-full h-1.5 bg-[#232529] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                percentUsed > 90
                  ? "bg-[#ff5c47]"
                  : percentUsed > 60
                  ? "bg-[#f9ab00]"
                  : "bg-[#3ec98a]"
              }`}
              style={{ width: `${percentUsed}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-[10px] text-[#8b909a] pt-0.5">
            <span>{Math.max(0, minutesLimit - minutesUsed).toFixed(0)}m remaining</span>
            <span>{percentUsed}% used</span>
          </div>
        </div>
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
                onClick={() => handleSelect(s)}
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

      {/* Footer User / Auth Profile */}
      <div className="p-3 border-t border-[#232529]/60 flex items-center justify-between text-xs text-[#8b909a]">
        {user ? (
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2 truncate pr-2">
              <div className="w-6 h-6 rounded-full bg-[#232529] flex items-center justify-center text-[#f0f2f5] shrink-0">
                <User className="w-3.5 h-3.5" />
              </div>
              <div className="truncate">
                <div className="text-xs text-[#f0f2f5] truncate font-medium">
                  {user.email?.split("@")[0]}
                </div>
                <div className="text-[10px] text-[#8b909a] capitalize">{profile?.role || "user"}</div>
              </div>
            </div>

            <Button
              size="icon"
              variant="ghost"
              onClick={signOut}
              title="Sign Out"
              className="w-7 h-7 text-[#8b909a] hover:text-[#ff5c47] rounded-lg"
            >
              <LogOut className="w-3.5 h-3.5" />
            </Button>
          </div>
        ) : (
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-1.5 text-[11px]">
              <ShieldCheck className="w-3.5 h-3.5 text-[#3ec98a]" />
              <span>SOC 2 Type II</span>
            </div>
            <Link href="/login" onClick={onCloseMobile}>
              <Button
                size="sm"
                variant="outline"
                className="h-7 px-2.5 text-[11px] rounded-full border-[#232529] bg-[#18191c] text-[#f0f2f5] hover:border-[#ff5c47]/50"
              >
                <LogIn className="w-3 h-3 mr-1 text-[#ff5c47]" />
                Sign In
              </Button>
            </Link>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Static Sidebar */}
      <aside className="hidden md:flex w-64 h-screen bg-[#111215] border-r border-[#232529] flex-col flex-shrink-0">
        {sidebarContent}
      </aside>

      {/* Mobile Slide-Over Drawer */}
      {isMobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div 
            onClick={onCloseMobile} 
            className="fixed inset-0 bg-black/75 backdrop-blur-sm transition-opacity" 
          />

          {/* Drawer Panel */}
          <div className="relative w-72 max-w-[85vw] bg-[#111215] border-r border-[#232529] shadow-2xl flex flex-col h-full z-10 animate-in slide-in-from-left duration-200">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}
