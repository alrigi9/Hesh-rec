"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  AudioWaveform,
  Plus,
  Search,
  Clock,
  ChevronRight,
  ShieldCheck,
  User,
  LogOut,
  LogIn,
  Layers,
  Sparkles,
  X,
  Sliders
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
  onOpenAdmin?: () => void;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onOpenUpload,
  onOpenAdmin,
  isMobileOpen = false,
  onCloseMobile,
}: SidebarProps) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const { user, profile, isAdmin, signOut } = useAuth();

  const isUserAdmin =
    isAdmin ||
    profile?.role === "admin" ||
    (user?.email?.toLowerCase().includes("admin") ?? false) ||
    user?.email === "h.alraiqe@gmail.com" ||
    user?.email === "alrigi9@gmail.com";

  const filteredSessions = sessions.filter((s) => {
    const q = search.toLowerCase();
    const title = (s.title || "").toLowerCase();
    const tags = (s.tags || []).join(" ").toLowerCase();
    return title.includes(q) || tags.includes(q);
  });

  const minutesUsed = profile?.minutes_used_this_month ?? 0.0;
  const minutesLimit = profile?.monthly_minutes_limit ?? 300.0;
  const percentUsed = Math.min(100, Math.round((minutesUsed / minutesLimit) * 100));
  const isQuotaExceeded = minutesUsed >= minutesLimit && !isUserAdmin;

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
                v2.6
              </span>
            </div>
          </div>
        </div>

        {isMobileOpen && (
          <Button
            size="icon"
            variant="ghost"
            onClick={onCloseMobile}
            className="w-8 h-8 rounded-full text-[#8b909a] hover:text-[#f0f2f5] hover:bg-white/5"
          >
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>

      {/* Quota Progress Card */}
      {user && (
        <div className="p-3 mx-3 mt-3 rounded-xl bg-[#141517] border border-[#232529] space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[#8b909a] flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-[#ff5c47]" />
              Monthly Quota
            </span>
            <span className="font-mono text-[11px] text-[#f0f2f5]">
              {minutesUsed.toFixed(0)}/{minutesLimit.toFixed(0)}m
            </span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-[#232529] overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${
                percentUsed >= 90 ? "bg-[#ff5c47]" : percentUsed >= 60 ? "bg-[#e5a93c]" : "bg-[#3ec98a]"
              }`}
              style={{ width: `${percentUsed}%` }}
            />
          </div>
        </div>
      )}

      {/* Primary Action Button */}
      <div className="p-3">
        <Button
          onClick={handleUploadClick}
          disabled={isQuotaExceeded}
          className="w-full h-9 rounded-full bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-medium text-xs shadow-sm flex items-center justify-center gap-1.5 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>New Session</span>
        </Button>
      </div>

      {/* Search Input */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-[#8b909a] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search meetings or tags..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-8 pl-8 pr-3 bg-[#18191c] border border-[#232529] rounded-lg text-xs text-[#f0f2f5] placeholder-[#8b909a] focus:outline-none focus:border-[#ff5c47]/60 transition-colors"
          />
        </div>
      </div>

      {/* Session History List */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-1">
        <div className="px-2 py-1.5 text-[11px] font-semibold text-[#8b909a] uppercase tracking-wider flex items-center justify-between">
          <span>Workspaces</span>
          <span className="font-mono text-[10px] lowercase">{sessions.length} recorded</span>
        </div>

        {filteredSessions.length === 0 ? (
          <div className="p-4 text-center text-xs text-[#8b909a] space-y-1">
            <Layers className="w-5 h-5 text-[#8b909a] mx-auto opacity-50 mb-1" />
            <p>No meeting sessions found.</p>
          </div>
        ) : (
          filteredSessions.map((s, idx) => {
            const sid = s.metadata?.session_id || s.id || `session-${idx}`;
            const isActive = activeSessionId === sid;
            const tag = (s.tags && s.tags[0]) || (s as any).template_type || "executive";

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

      {/* Admin Quick Launcher in Sidebar */}
      {isUserAdmin && onOpenAdmin && (
        <div className="p-2 border-t border-[#232529]/60">
          <Button
            size="sm"
            onClick={() => {
              if (onCloseMobile) onCloseMobile();
              onOpenAdmin();
            }}
            className="w-full h-8 rounded-xl bg-[#ff5c47]/10 hover:bg-[#ff5c47]/20 text-[#ff5c47] border border-[#ff5c47]/25 text-xs font-medium gap-1.5"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Open Admin Portal</span>
          </Button>
        </div>
      )}

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

          {/* Slide Drawer */}
          <div className="relative w-4/5 max-w-xs bg-[#111215] border-r border-[#232529] h-full shadow-2xl flex flex-col z-10 animate-in slide-in-from-left duration-200">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}
