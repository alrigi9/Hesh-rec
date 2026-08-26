"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  AudioWaveform,
  Plus,
  Search,
  Clock,
  ShieldCheck,
  User,
  LogOut,
  LogIn,
  Layers,
  X,
  Sliders,
  Loader2,
  AlertCircle,
  FileText,
  Monitor,
  Download,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { MeetingSession } from "@/types/meeting";
import { formatMeetingTitle } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import { normalizeTemplate, TEMPLATES_CONFIG } from "@/lib/templates";

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
  const minutesRemaining = Math.max(0, Math.round(minutesLimit - minutesUsed));

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
    <div className="flex flex-col h-full select-none bg-[#121316] text-[#f3f4f6]">
      {/* Brand Header */}
      <div className="h-14 px-4 flex items-center justify-between border-b border-[#22242a]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47] shrink-0">
            <AudioWaveform className="w-4 h-4" />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm tracking-tight text-[#f3f4f6]">
              RecMap
            </span>
            <span className="text-[10px] text-[#9ca3af] font-mono px-1.5 py-0.5 rounded bg-[#18191f] border border-[#22242a]">
              v3.2
            </span>
          </div>
        </div>

        {isMobileOpen && (
          <Button
            size="icon"
            variant="ghost"
            onClick={onCloseMobile}
            className="w-7 h-7 rounded-md text-[#9ca3af] hover:text-[#f3f4f6] hover:bg-[#18191f]"
          >
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>

      {/* Quota Progress */}
      {user && (
        <div className="px-3 pt-3 pb-1">
          <div className="p-2.5 rounded-lg bg-[#18191f] border border-[#22242a] space-y-1.5">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-[#9ca3af]">Monthly Usage</span>
              <span className="font-mono text-[#f3f4f6] font-medium">
                {minutesUsed.toFixed(0)} / {minutesLimit.toFixed(0)}m
              </span>
            </div>
            <div className="w-full h-1 rounded bg-[#262830] overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  percentUsed >= 90 ? "bg-[#ef4444]" : percentUsed >= 60 ? "bg-[#f59e0b]" : "bg-[#10b981]"
                }`}
                style={{ width: `${percentUsed}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Primary Action Button */}
      <div className="p-3">
        <Button
          onClick={handleUploadClick}
          disabled={isQuotaExceeded}
          className="w-full h-9 rounded-md bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-medium text-xs shadow-sm flex items-center justify-center gap-1.5 transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Recording</span>
        </Button>
      </div>

      {/* Search Input */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-[#9ca3af] absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search meetings..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-8 pl-8 pr-2.5 bg-[#18191f] border border-[#22242a] rounded-md text-xs text-[#f3f4f6] placeholder-[#9ca3af] focus:outline-none focus:border-[#ff5c47]/50 transition-colors"
          />
        </div>
      </div>

      {/* Session History List */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
        <div className="px-2 py-1.5 text-[10px] font-semibold text-[#9ca3af] uppercase tracking-wider flex items-center justify-between">
          <span>Meetings</span>
          <span className="font-mono text-[10px] lowercase">{sessions.length}</span>
        </div>

        {filteredSessions.length === 0 ? (
          <div className="p-6 text-center text-xs text-[#9ca3af] space-y-1">
            <FileText className="w-5 h-5 text-[#9ca3af] mx-auto opacity-40 mb-1" />
            <p>No meetings found.</p>
          </div>
        ) : (
          filteredSessions.map((s, idx) => {
            const sid = s.metadata?.session_id || s.id || `session-${idx}`;
            const isActive = activeSessionId === sid;
            const rawTemplate = (s as any).template || s.metadata?.template || (s as any).template_type;
            const templateId = normalizeTemplate(rawTemplate);
            const templateBadge = templateId !== "auto" ? TEMPLATES_CONFIG[templateId]?.badge : null;
            const isItemProcessing = s.status === "processing" || (!s.summary && !s.executive_summary && s.status !== "failed");
            const isItemFailed = s.status === "failed";

            return (
              <button
                key={sid}
                onClick={() => handleSelect(s)}
                className={`w-full text-left px-2.5 py-2 rounded-md text-xs transition-colors flex flex-col gap-1 relative ${
                  isActive
                    ? "bg-[#1e2027] text-[#f3f4f6] border border-[#2a2c36]"
                    : "text-[#9ca3af] hover:text-[#f3f4f6] hover:bg-[#18191f] border border-transparent"
                }`}
              >
                {isActive && (
                  <div className="absolute left-0 top-1.5 bottom-1.5 w-0.5 bg-[#ff5c47] rounded-r" />
                )}
                <div className="font-medium text-xs truncate text-[#f3f4f6] flex items-center justify-between">
                  <span className="truncate">{formatMeetingTitle(s.title, s.meeting_date)}</span>
                  {templateBadge && (
                    <span className="text-[9px] px-1 py-0.2 rounded bg-[#22242a] text-[#9ca3af] shrink-0 font-mono uppercase">
                      {templateBadge}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1.5 text-[10.5px] text-[#9ca3af]">
                  {isItemProcessing ? (
                    <span className="flex items-center gap-1 text-[#ff5c47] font-medium">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      <span>Processing...</span>
                    </span>
                  ) : isItemFailed ? (
                    <span className="flex items-center gap-1 text-[#ef4444] font-medium">
                      <AlertCircle className="w-3 h-3" />
                      <span>Failed</span>
                    </span>
                  ) : (
                    <>
                      <span className="font-mono">
                        {s.metadata?.duration || `${s.duration_minutes || 0}m`}
                      </span>
                      <span>•</span>
                      <span>{s.meeting_date || s.date || "Recent"}</span>
                    </>
                  )}
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Admin Quick Launcher */}
      {isUserAdmin && onOpenAdmin && (
        <div className="p-2 border-t border-[#22242a]">
          <Button
            size="sm"
            onClick={() => {
              if (onCloseMobile) onCloseMobile();
              onOpenAdmin();
            }}
            className="w-full h-8 rounded-md bg-[#18191f] hover:bg-[#1e2027] text-[#ff5c47] border border-[#22242a] text-xs font-medium gap-1.5 justify-start px-2.5"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Admin Console</span>
          </Button>
        </div>
      )}

      {/* Desktop App Quick Download Link */}
      <div className="p-2 border-t border-[#22242a]">
        <Link
          href="/download"
          onClick={() => {
            if (onCloseMobile) onCloseMobile();
          }}
          className="w-full h-8 rounded-md bg-[#18191f] hover:bg-[#1e2027] text-[#9ca3af] hover:text-[#f3f4f6] border border-[#22242a] text-xs font-medium gap-1.5 flex items-center justify-between px-2.5 transition-colors"
        >
          <div className="flex items-center gap-1.5">
            <Monitor className="w-3.5 h-3.5 text-[#ff5c47]" />
            <span>Desktop Recorder</span>
          </div>
          <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-[#22242a] text-[#9ca3af]">
            v1.0
          </span>
        </Link>
      </div>

      {/* Footer User Profile */}
      <div className="p-3 border-t border-[#22242a] flex items-center justify-between text-xs text-[#9ca3af] bg-[#0f1013]">
        {user ? (
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2 truncate pr-2">
              <div className="w-6 h-6 rounded-md bg-[#22242a] flex items-center justify-center text-[#f3f4f6] shrink-0 text-[11px] font-medium">
                {user.email ? user.email[0].toUpperCase() : "U"}
              </div>
              <div className="truncate">
                <div className="text-xs text-[#f3f4f6] truncate font-medium">
                  {user.email?.split("@")[0]}
                </div>
                <div className="text-[10px] text-[#9ca3af] capitalize">{profile?.role || "user"}</div>
              </div>
            </div>

            <Button
              size="icon"
              variant="ghost"
              onClick={signOut}
              title="Sign Out"
              className="w-7 h-7 text-[#9ca3af] hover:text-[#ff5c47] hover:bg-[#18191f] rounded-md"
            >
              <LogOut className="w-3.5 h-3.5" />
            </Button>
          </div>
        ) : (
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-1.5 text-[11px] text-[#9ca3af]">
              <ShieldCheck className="w-3.5 h-3.5 text-[#10b981]" />
              <span>Enterprise Privacy</span>
            </div>
            <Link href="/login" onClick={onCloseMobile}>
              <Button
                size="sm"
                variant="outline"
                className="h-7 px-2.5 text-xs rounded-md border-[#22242a] bg-[#18191f] text-[#f3f4f6] hover:border-[#ff5c47]/50"
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
      <aside className="hidden md:flex w-64 h-screen bg-[#121316] border-r border-[#22242a] flex-col flex-shrink-0">
        {sidebarContent}
      </aside>

      {/* Mobile Slide-Over Drawer */}
      {isMobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div 
            onClick={onCloseMobile} 
            className="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity" 
          />

          {/* Slide Drawer */}
          <div className="relative w-4/5 max-w-xs bg-[#121316] border-r border-[#22242a] h-full shadow-2xl flex flex-col z-10 animate-in slide-in-from-left duration-200">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}
