"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { 
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
  Zap,
  Plus,
  Monitor
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sidebar } from "@/components/Sidebar";
import { UploadModal } from "@/components/UploadModal";
import { AdminPortalModal } from "@/components/AdminPortalModal";
import { MeetingView } from "@/components/MeetingView";
import { AudioPlayer } from "@/components/AudioPlayer";
import { fetchSessions, fetchSessionById } from "@/lib/api";
import { MeetingSession } from "@/types/meeting";
import { useAuth } from "@/context/AuthContext";
import { supabase } from "@/lib/supabaseClient";

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
      setActiveSession(null);
      return;
    }

    try {
      const cached = localStorage.getItem(`recmap_sessions_${user.id}`);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setSessions(parsed);
          const cachedActive = localStorage.getItem(`recmap_active_session_${user.id}`);
          if (cachedActive) {
            const parsedActive = JSON.parse(cachedActive);
            if (parsedActive && parsedActive.id) {
              setActiveSession(parsedActive);
            } else {
              setActiveSession(parsed[0]);
            }
          } else {
            setActiveSession(parsed[0]);
          }
        }
      }
    } catch (e) {
      console.warn("Local storage hydration note:", e);
    }

    fetchSessions(user.id, token || undefined).then((data) => {
      if (data && data.length > 0) {
        setSessions(data);
        try {
          localStorage.setItem(`recmap_sessions_${user.id}`, JSON.stringify(data));
        } catch (e) {}

        setActiveSession((currentActive) => {
          if (currentActive) {
            const matched = data.find((s) => s.id === currentActive.id);
            return matched || data[0];
          }
          return data[0];
        });
      }
    });

    const channel = supabase
      .channel(`user-sessions-${user.id}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "sessions",
        },
        () => {
          fetchSessions(user.id, token || undefined).then((data) => {
            if (data && data.length > 0) {
              setSessions(data);
              try {
                localStorage.setItem(`recmap_sessions_${user.id}`, JSON.stringify(data));
              } catch (e) {}
            }
          });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [user, token]);

  // Sync active session selection to local storage
  useEffect(() => {
    if (user && user.id && activeSession) {
      try {
        localStorage.setItem(`recmap_active_session_${user.id}`, JSON.stringify(activeSession));
      } catch (e) {}
    }
  }, [user, activeSession]);

  // Fetch fresh session details and on-demand signed audio URL whenever active session ID changes
  useEffect(() => {
    if (activeSession?.id && user && token) {
      let isMounted = true;
      fetchSessionById(activeSession.id, token).then((full: MeetingSession | null) => {
        if (isMounted && full && full.id === activeSession.id) {
          setActiveSession((prev) => (prev && prev.id === full.id ? { ...prev, ...full } : prev));
        }
      });
      return () => {
        isMounted = false;
      };
    }
  }, [activeSession?.id, user, token]);

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
    setSessions((prev) => {
      const updated = [newSession, ...prev.filter((s) => s.id !== newSession.id)];
      if (user && user.id) {
        try {
          localStorage.setItem(`recmap_sessions_${user.id}`, JSON.stringify(updated));
          localStorage.setItem(`recmap_active_session_${user.id}`, JSON.stringify(newSession));
        } catch (e) {}
      }
      return updated;
    });
    setActiveSession(newSession);
  };

  const handleSessionUpdated = (updatedSession: MeetingSession) => {
    setActiveSession(updatedSession);
    setSessions((prev) => {
      const next = prev.map((s) => (s.id === updatedSession.id ? updatedSession : s));
      if (user && user.id) {
        try {
          localStorage.setItem(`recmap_sessions_${user.id}`, JSON.stringify(next));
          localStorage.setItem(`recmap_active_session_${user.id}`, JSON.stringify(updatedSession));
        } catch (e) {}
      }
      return next;
    });
  };

  const handleSeekAudio = (seconds: number) => {
    setAudioSeekTime(seconds);
  };

  const minutesUsed = profile?.minutes_used_this_month ?? 0.0;
  const minutesLimit = profile?.monthly_minutes_limit ?? 300.0;
  const minutesRemaining = Math.max(0, Math.round(minutesLimit - minutesUsed));

  return (
    <div className="flex h-screen overflow-hidden bg-[#0d0e11] text-[#f3f4f6] flex-col md:flex-row font-sans selection:bg-[#ff5c47]/30 selection:text-white">
      {/* Mobile Top Header */}
      <header className="md:hidden h-14 bg-[#121316] border-b border-[#22242a] px-4 flex items-center justify-between shrink-0 sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => setIsMobileDrawerOpen(true)}
            className="w-8 h-8 text-[#9ca3af] hover:text-[#f3f4f6] hover:bg-[#18191f] rounded-md"
            aria-label="Open Navigation Menu"
          >
            <Menu className="w-4 h-4" />
          </Button>

          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47]">
              <AudioWaveform className="w-3.5 h-3.5" />
            </div>
            <span className="font-semibold text-sm text-[#f3f4f6]">
              RecMap
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isUserAdmin && (
            <Button
              size="sm"
              onClick={() => setIsAdminModalOpen(true)}
              className="h-7 px-2 rounded-md bg-[#18191f] text-[#ff5c47] border border-[#22242a] text-xs font-medium gap-1"
            >
              <ShieldCheck className="w-3 h-3" />
              <span>Admin</span>
            </Button>
          )}

          {user ? (
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[#18191f] border border-[#22242a] text-[11px] font-mono text-[#9ca3af]">
                <Zap className="w-3 h-3 text-[#ff5c47]" />
                {minutesRemaining}m
              </span>
              <div className="w-6 h-6 rounded-md bg-[#22242a] flex items-center justify-center text-[11px] font-medium text-[#f3f4f6]">
                {user.email ? user.email[0].toUpperCase() : "U"}
              </div>
            </div>
          ) : (
            <Link href="/login">
              <Button
                size="sm"
                variant="outline"
                className="h-7 px-2.5 rounded-md border-[#22242a] bg-[#18191f] text-[#f3f4f6] text-xs font-medium"
              >
                <LogIn className="w-3 h-3 mr-1 text-[#ff5c47]" />
                Sign In
              </Button>
            </Link>
          )}
        </div>
      </header>

      {/* Sidebar (Desktop Static & Mobile Drawer) */}
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSession?.metadata?.session_id || activeSession?.id || null}
        onSelectSession={(s) => {
          setAudioSeekTime(undefined);
          setActiveSession(s);
          setIsMobileDrawerOpen(false);
          if (s.id) {
            fetchSessionById(s.id, token || undefined).then((full: MeetingSession | null) => {
              if (full) {
                setActiveSession(full);
                setSessions((prev) => prev.map((item) => (item.id === full.id ? full : item)));
              }
            });
          }
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
      <main className="flex-1 h-[calc(100vh-3.5rem)] md:h-screen overflow-y-auto overflow-x-hidden relative bg-[#0d0e11]">
        {/* Desktop Admin Bar */}
        {isUserAdmin && (
          <div className="hidden md:flex items-center justify-between px-6 py-1.5 bg-[#0f1013] border-b border-[#22242a] text-xs">
            <div className="flex items-center gap-2 text-[#9ca3af]">
              <ShieldCheck className="w-3.5 h-3.5 text-[#ff5c47]" />
              <span>Admin Console • <span className="text-[#f3f4f6] font-mono">{user?.email}</span></span>
            </div>
            <Button
              size="sm"
              onClick={() => setIsAdminModalOpen(true)}
              className="h-6 px-2.5 rounded-md bg-[#18191f] hover:bg-[#22242a] text-[#ff5c47] border border-[#22242a] text-[11px] font-medium gap-1"
            >
              <Sliders className="w-3 h-3" />
              <span>Manage Quotas & Users</span>
            </Button>
          </div>
        )}

        {activeSession ? (
          <>
            <MeetingView
              session={activeSession}
              onSeekAudio={handleSeekAudio}
              onSessionUpdated={handleSessionUpdated}
            />
            <AudioPlayer
              key={activeSession.id}
              sessionId={activeSession.id}
              src={activeSession.metadata?.audio_url}
              initialDuration={
                typeof (activeSession as any).duration_seconds === "number" && (activeSession as any).duration_seconds > 0
                  ? (activeSession as any).duration_seconds
                  : (activeSession.metadata?.duration_seconds || (activeSession.duration_minutes ? activeSession.duration_minutes * 60 : 0))
              }
              currentTime={audioSeekTime}
            />
          </>
        ) : (
          /* Studio Empty State / Workspace Landing */
          <div className="max-w-3xl mx-auto px-4 sm:px-6 pt-12 sm:pt-20 pb-16 space-y-8">
            <div className="space-y-3 text-center max-w-lg mx-auto">
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#f3f4f6]">
                Meeting Intelligence Workspace
              </h1>
              <p className="text-xs sm:text-sm text-[#9ca3af] leading-relaxed">
                Upload audio or video recordings to generate structured executive summaries, action items with assignees, interactive mind maps, and diarized transcripts.
              </p>
              
              {/* Primary Action Button */}
              <div className="pt-3 flex flex-col sm:flex-row items-center justify-center gap-2.5">
                <Button
                  onClick={handleOpenUpload}
                  className="w-full sm:w-auto h-9 px-5 rounded-md bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-medium text-xs shadow-sm gap-1.5 cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Upload Recording</span>
                </Button>

                <Link href="/download" className="w-full sm:w-auto">
                  <Button
                    variant="outline"
                    className="w-full sm:w-auto h-9 px-4 rounded-md border-[#22242a] bg-[#131418] hover:bg-[#18191f] text-[#f3f4f6] text-xs font-medium gap-1.5 cursor-pointer"
                  >
                    <Monitor className="w-3.5 h-3.5 text-[#ff5c47]" />
                    <span>Download Desktop App</span>
                  </Button>
                </Link>

                {!user && (
                  <Link href="/login" className="w-full sm:w-auto">
                    <Button
                      variant="outline"
                      className="w-full sm:w-auto h-9 px-4 rounded-md border-[#22242a] bg-[#131418] hover:bg-[#18191f] text-[#f3f4f6] text-xs font-medium gap-1.5 cursor-pointer"
                    >
                      <LogIn className="w-3.5 h-3.5 text-[#ff5c47]" />
                      <span>Sign In</span>
                    </Button>
                  </Link>
                )}
              </div>
            </div>

            {/* Clean Feature Overview */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="bg-[#131418] border border-[#22242a] rounded-lg p-4 space-y-1.5">
                <div className="w-7 h-7 rounded-md bg-[#18191f] flex items-center justify-center text-[#ff5c47]">
                  <FileText className="w-3.5 h-3.5" />
                </div>
                <div className="text-xs font-semibold text-[#f3f4f6]">
                  Executive Summaries
                </div>
                <div className="text-[11px] text-[#9ca3af] leading-relaxed">
                  Structured meeting breakdowns with discussion topics and core decisions.
                </div>
              </div>

              <div className="bg-[#131418] border border-[#22242a] rounded-lg p-4 space-y-1.5">
                <div className="w-7 h-7 rounded-md bg-[#18191f] flex items-center justify-center text-[#10b981]">
                  <CheckSquare className="w-3.5 h-3.5" />
                </div>
                <div className="text-xs font-semibold text-[#f3f4f6]">
                  Action Items & Tasks
                </div>
                <div className="text-[11px] text-[#9ca3af] leading-relaxed">
                  Deliverables mapped with owners, priority tags, and due dates.
                </div>
              </div>

              <div className="bg-[#131418] border border-[#22242a] rounded-lg p-4 space-y-1.5">
                <div className="w-7 h-7 rounded-md bg-[#18191f] flex items-center justify-center text-[#60a5fa]">
                  <Network className="w-3.5 h-3.5" />
                </div>
                <div className="text-xs font-semibold text-[#f3f4f6]">
                  Interactive Mind Maps
                </div>
                <div className="text-[11px] text-[#9ca3af] leading-relaxed">
                  Visual concept and decision mapping for instant structural clarity.
                </div>
              </div>
            </div>

            {/* Recent Workspaces List if user has meetings */}
            {user && sessions && sessions.length > 0 && (
              <div className="space-y-2 pt-4 border-t border-[#22242a]">
                <div className="text-xs font-semibold text-[#9ca3af] uppercase tracking-wider flex items-center justify-between px-1">
                  <span>Recent Meetings</span>
                  <span className="font-mono text-[11px] lowercase">{sessions.length} total</span>
                </div>

                <div className="space-y-1.5">
                  {sessions.slice(0, 4).map((s, idx) => (
                    <div
                      key={idx}
                      onClick={() => setActiveSession(s)}
                      className="bg-[#131418] border border-[#22242a] hover:border-[#2e3238] rounded-lg p-3 px-4 flex items-center justify-between cursor-pointer transition-colors hover:bg-[#18191f]"
                    >
                      <div className="space-y-0.5 truncate pr-3">
                        <div className="text-xs font-medium text-[#f3f4f6] truncate">
                          {s.title || "Untitled Session"}
                        </div>
                        <div className="flex items-center gap-2 text-[11px] text-[#9ca3af]">
                          <span className="font-mono">{s.metadata?.duration || `${s.duration_minutes || 0}m`}</span>
                          <span>•</span>
                          <span>{s.meeting_date || "Recent"}</span>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs text-[#9ca3af] hover:text-[#f3f4f6] shrink-0"
                      >
                        <span className="mr-1">Open</span>
                        <ArrowRight className="w-3 h-3" />
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
