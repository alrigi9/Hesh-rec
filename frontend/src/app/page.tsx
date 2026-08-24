"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { 
  Sparkles, 
  Upload, 
  AudioWaveform, 
  FileText, 
  CheckSquare, 
  Network, 
  ShieldCheck, 
  Menu, 
  LogIn,
  Sliders,
  ArrowRight,
  Lock,
  Zap
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sidebar } from "@/components/Sidebar";
import { UploadModal } from "@/components/UploadModal";
import { AdminPortalModal } from "@/components/AdminPortalModal";
import { MeetingView } from "@/components/MeetingView";
import { AudioPlayer } from "@/components/AudioPlayer";
import { fetchSessions } from "@/lib/api";
import { MeetingSession } from "@/types/meeting";
import { useAuth } from "@/context/AuthContext";

export default function Home() {
  const router = useRouter();
  const { user, profile, token, isAdmin } = useAuth();
  const [sessions, setSessions] = useState<MeetingSession[]>([]);
  const [activeSession, setActiveSession] = useState<MeetingSession | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isAdminModalOpen, setIsAdminModalOpen] = useState(false);
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [audioSeekTime, setAudioSeekTime] = useState<number | undefined>(undefined);

  const isUserAdmin =
    isAdmin ||
    profile?.role === "admin" ||
    (user?.email?.toLowerCase().includes("admin") ?? false) ||
    user?.email === "h.alraiqe@gmail.com" ||
    user?.email === "alrigi9@gmail.com";

  // Load sessions on mount or when authenticated user changes
  useEffect(() => {
    if (!user || !user.id || user.id === "guest") {
      setSessions([]);
      return;
    }
    fetchSessions(user.id, token || undefined).then((data) => {
      if (data && data.length > 0) {
        setSessions(data);
      } else {
        setSessions([]);
      }
    });
  }, [user, token]);

  const handleOpenUpload = () => {
    if (!user) {
      router.push(
        "/login?msg=" +
          encodeURIComponent("Please sign in or create an account to transcribe audio (300 free mins/month)")
      );
      return;
    }
    setIsUploadOpen(true);
  };

  const handleUploadSuccess = (newSession: MeetingSession) => {
    setSessions((prev) => [newSession, ...prev]);
    setActiveSession(newSession);
  };

  const handleSeekAudio = (seconds: number) => {
    setAudioSeekTime(seconds);
  };

  const minutesUsed = profile?.minutes_used_this_month ?? 0.0;
  const minutesLimit = profile?.monthly_minutes_limit ?? 300.0;
  const minutesRemaining = Math.max(0, Math.round(minutesLimit - minutesUsed));

  return (
    <div className="flex h-screen overflow-hidden bg-[#0A0B0F] text-[#f0f2f5] flex-col md:flex-row font-sans">
      {/* Fixed Sticky Mobile Navigation Bar */}
      <header className="md:hidden h-14 bg-[#0A0B0F]/90 backdrop-blur-md border-b border-white/[0.08] px-4 flex items-center justify-between shrink-0 sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => setIsMobileDrawerOpen(true)}
            className="w-9 h-9 text-[#8b909a] hover:text-[#f0f2f5] hover:bg-white/5 rounded-xl"
            aria-label="Open Navigation Menu"
          >
            <Menu className="w-5 h-5" />
          </Button>

          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47]">
              <AudioWaveform className="w-4 h-4" />
            </div>
            <span className="font-bold text-sm text-[#f0f2f5] font-heading tracking-tight">
              RecMap
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Dedicated Admin Console Button for Admins */}
          {isUserAdmin && (
            <Button
              size="sm"
              onClick={() => setIsAdminModalOpen(true)}
              className="h-8 px-2.5 rounded-full bg-[#ff5c47]/15 hover:bg-[#ff5c47]/25 text-[#ff5c47] border border-[#ff5c47]/30 text-xs font-medium gap-1 shadow-sm"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Admin</span>
            </Button>
          )}

          {user ? (
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-[11px] font-mono text-[#8b909a]">
                <Zap className="w-3 h-3 text-[#ff5c47]" />
                {minutesRemaining}m left
              </span>
              <div className="w-7 h-7 rounded-full bg-[#ff5c47]/20 border border-[#ff5c47]/30 flex items-center justify-center text-[11px] font-semibold text-[#ff5c47]">
                {user.email ? user.email[0].toUpperCase() : "U"}
              </div>
            </div>
          ) : (
            <Link href="/login">
              <Button
                size="sm"
                variant="outline"
                className="h-8 px-3 rounded-full border-white/10 bg-white/5 text-[#f0f2f5] hover:border-[#ff5c47]/50 text-xs font-medium"
              >
                <LogIn className="w-3.5 h-3.5 mr-1.5 text-[#ff5c47]" />
                Sign In
              </Button>
            </Link>
          )}
        </div>
      </header>

      {/* Sidebar (Desktop Static & Mobile Slide-Over Drawer) */}
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSession?.metadata?.session_id || activeSession?.id || null}
        onSelectSession={(s) => {
          setActiveSession(s);
          setIsMobileDrawerOpen(false);
        }}
        onOpenUpload={() => {
          setIsMobileDrawerOpen(false);
          handleOpenUpload();
        }}
        onOpenAdmin={() => setIsAdminModalOpen(true)}
        isMobileOpen={isMobileDrawerOpen}
        onCloseMobile={() => setIsMobileDrawerOpen(false)}
      />

      {/* Main Content Area */}
      <main className="flex-1 h-[calc(100vh-3.5rem)] md:h-screen overflow-y-auto overflow-x-hidden relative">
        {/* Desktop Top Admin Bar when user is admin */}
        {isUserAdmin && (
          <div className="hidden md:flex items-center justify-between px-6 py-2 bg-[#13151B]/80 border-b border-white/[0.08] text-xs">
            <div className="flex items-center gap-2 text-[#8b909a]">
              <ShieldCheck className="w-4 h-4 text-[#ff5c47]" />
              <span>Admin Console • <span className="text-[#f0f2f5] font-mono">{user?.email}</span></span>
            </div>
            <Button
              size="sm"
              onClick={() => setIsAdminModalOpen(true)}
              className="h-7 px-3 rounded-full bg-[#ff5c47]/15 hover:bg-[#ff5c47]/25 text-[#ff5c47] border border-[#ff5c47]/30 text-xs font-medium gap-1.5 shadow-[0_0_15px_rgba(255,92,71,0.15)]"
            >
              <Sliders className="w-3 h-3" />
              <span>Open Admin Management Portal</span>
            </Button>
          </div>
        )}

        {activeSession ? (
          <>
            <MeetingView session={activeSession} onSeekAudio={handleSeekAudio} />
            <AudioPlayer
              src={activeSession.metadata?.audio_url}
              currentTime={audioSeekTime}
            />
          </>
        ) : (
          /* Studio Workspace Ingestion & Landing View */
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pt-6 sm:pt-12 pb-16 space-y-8 sm:space-y-12">
            {/* Clean Hero Banner */}
            <div className="space-y-4 text-center max-w-xl mx-auto">
              <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-[#ff5c47]/10 border border-[#ff5c47]/20 text-[#ff5c47] text-xs font-medium mx-auto">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Enterprise Speech & Audio Intelligence</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#f0f2f5] font-heading leading-snug break-words">
                Turn Voice & Meetings into Clear, Actionable Intelligence.
              </h1>
              <p className="text-xs sm:text-sm text-[#8b909a] leading-relaxed max-w-lg mx-auto">
                Fast, secure audio transcription and intelligent breakdown powered by advanced AI models. Get instant executive summaries, mind maps, and structured action items.
              </p>
              
              {/* Direct Ingestion Action Button */}
              <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
                <Button
                  onClick={handleOpenUpload}
                  className="w-full sm:w-auto h-11 px-8 rounded-full bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-semibold text-xs shadow-lg shadow-[#ff5c47]/25 transition-all gap-2"
                >
                  <Upload className="w-4 h-4" />
                  Upload File
                </Button>

                {!user && (
                  <Link href="/login" className="w-full sm:w-auto">
                    <Button
                      variant="outline"
                      className="w-full sm:w-auto h-11 px-6 rounded-full border-white/10 bg-[#13151B] hover:bg-[#18191c] text-[#f0f2f5] text-xs font-medium gap-1.5"
                    >
                      <LogIn className="w-3.5 h-3.5 text-[#ff5c47]" />
                      Sign In
                    </Button>
                  </Link>
                )}
              </div>
            </div>

            {/* Feature Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
              <div className="bg-[#13151B] border border-white/[0.08] rounded-2xl p-5 space-y-2 shadow-sm">
                <div className="w-8 h-8 rounded-lg bg-[#ff5c47]/10 flex items-center justify-center text-[#ff5c47]">
                  <FileText className="w-4 h-4" />
                </div>
                <div className="text-sm font-semibold text-[#f0f2f5] font-heading">
                  Executive Summaries
                </div>
                <div className="text-xs text-[#8b909a] leading-relaxed">
                  Clear, structured meeting overviews highlighting core decisions.
                </div>
              </div>

              <div className="bg-[#13151B] border border-white/[0.08] rounded-2xl p-5 space-y-2 shadow-sm">
                <div className="w-8 h-8 rounded-lg bg-[#3ec98a]/10 flex items-center justify-center text-[#3ec98a]">
                  <CheckSquare className="w-4 h-4" />
                </div>
                <div className="text-sm font-semibold text-[#f0f2f5] font-heading">
                  Action Items & Tasks
                </div>
                <div className="text-xs text-[#8b909a] leading-relaxed">
                  Auto-extracted deliverables with accountable owners and deadlines.
                </div>
              </div>

              <div className="bg-[#13151B] border border-white/[0.08] rounded-2xl p-5 space-y-2 shadow-sm">
                <div className="w-8 h-8 rounded-lg bg-[#7cb0ff]/10 flex items-center justify-center text-[#7cb0ff]">
                  <Network className="w-4 h-4" />
                </div>
                <div className="text-sm font-semibold text-[#f0f2f5] font-heading">
                  Interactive Mind Maps
                </div>
                <div className="text-xs text-[#8b909a] leading-relaxed">
                  Visual concept and decision mapping for instant thematic clarity.
                </div>
              </div>

              <div className="bg-[#13151B] border border-white/[0.08] rounded-2xl p-5 space-y-2 shadow-sm">
                <div className="w-8 h-8 rounded-lg bg-[#b180ff]/10 flex items-center justify-center text-[#b180ff]">
                  <Lock className="w-4 h-4" />
                </div>
                <div className="text-sm font-semibold text-[#f0f2f5] font-heading">
                  Enterprise-Grade Privacy
                </div>
                <div className="text-xs text-[#8b909a] leading-relaxed">
                  Encrypted, private audio processing and dedicated user isolation.
                </div>
              </div>
            </div>

            {/* Recent Workspaces List (Only rendered for authenticated users) */}
            {user && sessions && sessions.length > 0 && (
              <div className="space-y-3">
                <div className="text-sm font-semibold text-[#f0f2f5] font-heading flex items-center justify-between">
                  <span>Recent Workspaces</span>
                  <span className="text-xs text-[#8b909a] font-normal font-sans">
                    {sessions.length} total meetings
                  </span>
                </div>

                <div className="space-y-2">
                  {sessions.slice(0, 5).map((s, idx) => (
                    <div
                      key={idx}
                      onClick={() => setActiveSession(s)}
                      className="bg-[#13151B] border border-white/[0.08] hover:border-white/20 rounded-2xl p-3.5 sm:p-4 sm:px-5 flex items-center justify-between cursor-pointer transition-all hover:bg-[#18191c]"
                    >
                      <div className="space-y-1 truncate pr-3">
                        <div className="text-sm font-semibold text-[#f0f2f5] truncate">
                          {s.title || "Untitled Session"}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-[#8b909a]">
                          <span>{s.metadata?.duration || `${s.duration_minutes || 0} min`}</span>
                          <span>•</span>
                          <span>{s.meeting_date || "Recent"}</span>
                          <span>•</span>
                          <span>{(s.sections || []).length} Sections</span>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="rounded-full text-xs text-[#8b909a] hover:text-[#f0f2f5] hover:bg-white/5 shrink-0"
                      >
                        <span className="hidden sm:inline mr-1">Open Workspace</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Ingestion & Transcribe Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={handleUploadSuccess}
      />

      {/* Integrated In-Page Admin Portal Modal */}
      {isUserAdmin && (
        <AdminPortalModal
          isOpen={isAdminModalOpen}
          onClose={() => setIsAdminModalOpen(false)}
        />
      )}
    </div>
  );
}
