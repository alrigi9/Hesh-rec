"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { 
  Sparkles, 
  Upload, 
  AudioWaveform, 
  FileText, 
  CheckSquare, 
  Clock, 
  ArrowRight, 
  ShieldCheck,
  Menu,
  Plus,
  User,
  LogIn
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Sidebar } from "@/components/Sidebar";
import { UploadModal } from "@/components/UploadModal";
import { MeetingView } from "@/components/MeetingView";
import { AudioPlayer } from "@/components/AudioPlayer";
import { fetchSessions } from "@/lib/api";
import { MeetingSession } from "@/types/meeting";
import { useAuth } from "@/context/AuthContext";

export default function Home() {
  const { user, profile, token } = useAuth();
  const [sessions, setSessions] = useState<MeetingSession[]>([]);
  const [activeSession, setActiveSession] = useState<MeetingSession | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [audioSeekTime, setAudioSeekTime] = useState<number | undefined>(undefined);

  // Load sessions on mount or when user changes
  useEffect(() => {
    fetchSessions(user?.id, token || undefined).then((data) => {
      if (data && data.length > 0) {
        setSessions(data);
      } else {
        setSessions([]);
      }
    });
  }, [user?.id, token]);

  const handleUploadSuccess = (newSession: MeetingSession) => {
    setSessions((prev) => [newSession, ...prev]);
    setActiveSession(newSession);
  };

  const handleSeekAudio = (seconds: number) => {
    setAudioSeekTime(seconds);
  };

  const minutesUsed = profile?.minutes_used_this_month ?? 0.0;
  const minutesLimit = profile?.monthly_minutes_limit ?? 300.0;

  return (
    <div className="flex h-screen overflow-hidden bg-[#0c0d0e] text-[#f0f2f5] flex-col md:flex-row">
      {/* Top Mobile Navigation Bar (visible < 768px) */}
      <header className="md:hidden h-14 bg-[#111215] border-b border-[#232529] px-4 flex items-center justify-between shrink-0 z-30">
        <div className="flex items-center gap-3">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => setIsMobileDrawerOpen(true)}
            className="w-9 h-9 text-[#8b909a] hover:text-[#f0f2f5] hover:bg-[#18191c] rounded-xl"
            aria-label="Open Navigation Menu"
          >
            <Menu className="w-5 h-5" />
          </Button>

          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47]">
              <AudioWaveform className="w-4 h-4" />
            </div>
            <span className="font-bold text-sm text-[#f0f2f5] font-heading">
              Hesh Rec
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Quota Badge on Mobile */}
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#18191c] border border-[#232529] text-[11px] font-mono text-[#8b909a]">
            <Sparkles className="w-3 h-3 text-[#ff5c47]" />
            {minutesUsed.toFixed(0)}/{minutesLimit.toFixed(0)}m
          </span>

          <Button
            size="sm"
            onClick={() => setIsUploadOpen(true)}
            className="h-8 px-3 rounded-full bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white text-xs font-medium gap-1"
          >
            <Plus className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Upload</span>
          </Button>
        </div>
      </header>

      {/* Sidebar (Desktop static & Mobile Slide-Over Drawer) */}
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSession?.metadata?.session_id || activeSession?.id || null}
        onSelectSession={(s) => {
          setActiveSession(s);
          setIsMobileDrawerOpen(false);
        }}
        onOpenUpload={() => {
          setIsUploadOpen(true);
          setIsMobileDrawerOpen(false);
        }}
        isMobileOpen={isMobileDrawerOpen}
        onCloseMobile={() => setIsMobileDrawerOpen(false)}
      />

      {/* Main Content Area */}
      <main className="flex-1 h-[calc(100vh-3.5rem)] md:h-screen overflow-y-auto overflow-x-hidden relative">
        {activeSession ? (
          <>
            <MeetingView session={activeSession} onSeekAudio={handleSeekAudio} />
            <AudioPlayer
              src={activeSession.metadata?.audio_url}
              currentTime={audioSeekTime}
            />
          </>
        ) : (
          /* Empty State / Welcome Dashboard */
          <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 sm:py-16 space-y-8 sm:space-y-12">
            {/* Hero Banner */}
            <div className="space-y-4 text-center max-w-xl mx-auto pt-4 sm:pt-8">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#ff5c47]/10 border border-[#ff5c47]/20 text-[#ff5c47] text-xs font-medium">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Next-Gen Speech & Meeting Intelligence</span>
              </div>
              <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#f0f2f5] font-heading leading-tight break-words">
                Turn recordings into SOC 2 executive intelligence.
              </h1>
              <p className="text-xs sm:text-sm text-[#8b909a] leading-relaxed max-w-md mx-auto">
                Groq LPUs for ultra-fast Whisper transcription, paired with Gemini 2.5 Flash
                for granular deliverables, mind maps, and compliance governance.
              </p>
              <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
                <Button
                  onClick={() => setIsUploadOpen(true)}
                  className="w-full sm:w-auto h-10 px-6 rounded-full bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-medium text-xs shadow-lg shadow-[#ff5c47]/20 transition-all gap-2"
                >
                  <Upload className="w-4 h-4" />
                  Transcribe & Extract Meeting
                </Button>
                {!user && (
                  <Link href="/login" className="w-full sm:w-auto">
                    <Button
                      variant="outline"
                      className="w-full sm:w-auto h-10 px-5 rounded-full border-[#232529] bg-[#141517] text-[#f0f2f5] text-xs"
                    >
                      <LogIn className="w-3.5 h-3.5 mr-1.5 text-[#ff5c47]" />
                      Sign In for 300 Mins
                    </Button>
                  </Link>
                )}
              </div>
            </div>

            {/* Metric Tiles */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 pt-2">
              <div className="bg-[#141517] border border-[#232529] rounded-2xl p-5 sm:p-6 space-y-2 shadow-sm">
                <div className="w-8 h-8 rounded-lg bg-[#ff5c47]/10 flex items-center justify-center text-[#ff5c47]">
                  <FileText className="w-4 h-4" />
                </div>
                <div className="text-sm font-semibold text-[#f0f2f5] font-heading">
                  Executive Summaries
                </div>
                <div className="text-xs text-[#8b909a] leading-relaxed">
                  Structured past-tense narratives with zero bullet-point fluff.
                </div>
              </div>

              <div className="bg-[#141517] border border-[#232529] rounded-2xl p-5 sm:p-6 space-y-2 shadow-sm">
                <div className="w-8 h-8 rounded-lg bg-[#3ec98a]/10 flex items-center justify-center text-[#3ec98a]">
                  <CheckSquare className="w-4 h-4" />
                </div>
                <div className="text-sm font-semibold text-[#f0f2f5] font-heading">
                  Action Deliverables
                </div>
                <div className="text-xs text-[#8b909a] leading-relaxed">
                  Strictly assigned tasks, deliverables, deadlines, and owners.
                </div>
              </div>

              <div className="bg-[#141517] border border-[#232529] rounded-2xl p-5 sm:p-6 space-y-2 shadow-sm">
                <div className="w-8 h-8 rounded-lg bg-[#7cb0ff]/10 flex items-center justify-center text-[#7cb0ff]">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div className="text-sm font-semibold text-[#f0f2f5] font-heading">
                  SOC 2 Compliance
                </div>
                <div className="text-xs text-[#8b909a] leading-relaxed">
                  Automated governance audit tagging and risk identification.
                </div>
              </div>
            </div>

            {/* Recent Sessions List */}
            {sessions.length > 0 && (
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
                      className="bg-[#141517] border border-[#232529] hover:border-[#2e3238] rounded-2xl p-3.5 sm:p-4 sm:px-5 flex items-center justify-between cursor-pointer transition-all hover:bg-[#18191c]"
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
                        className="rounded-full text-xs text-[#8b909a] hover:text-[#f0f2f5] hover:bg-[#232529] shrink-0"
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

      {/* Upload & Transcribe Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={handleUploadSuccess}
      />
    </div>
  );
}
