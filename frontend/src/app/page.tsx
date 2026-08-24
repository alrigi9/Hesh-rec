"use client";

import React, { useState, useEffect } from "react";
import { 
  Sparkles, 
  Upload, 
  AudioWaveform, 
  FileText, 
  CheckSquare, 
  Clock, 
  Calendar,
  Layers,
  ArrowRight,
  ShieldCheck
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sidebar } from "@/components/Sidebar";
import { UploadModal } from "@/components/UploadModal";
import { MeetingView } from "@/components/MeetingView";
import { AudioPlayer } from "@/components/AudioPlayer";
import { fetchSessions } from "@/lib/api";
import { MeetingSession } from "@/types/meeting";
import { useAuth } from "@/context/AuthContext";

export default function Home() {
  const { user, token } = useAuth();
  const [sessions, setSessions] = useState<MeetingSession[]>([]);
  const [activeSession, setActiveSession] = useState<MeetingSession | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
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

  return (
    <div className="flex h-screen overflow-hidden bg-[#0c0d0e] text-[#f0f2f5]">
      {/* Left Sidebar */}
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSession?.metadata?.session_id || activeSession?.id || null}
        onSelectSession={(s) => setActiveSession(s)}
        onOpenUpload={() => setIsUploadOpen(true)}
      />

      {/* Main Content Area */}
      <main className="flex-1 h-screen overflow-y-auto relative">
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
          <div className="max-w-4xl mx-auto px-6 py-16 space-y-12">
            {/* Hero Banner */}
            <div className="space-y-4 text-center max-w-xl mx-auto pt-8">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#ff5c47]/10 border border-[#ff5c47]/20 text-[#ff5c47] text-xs font-medium">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Next-Gen Speech & Meeting Intelligence</span>
              </div>
              <h1 className="text-4xl font-bold tracking-tight text-[#f0f2f5] font-heading leading-tight">
                Turn recordings into SOC 2 executive intelligence.
              </h1>
              <p className="text-sm text-[#8b909a] leading-relaxed">
                Groq LPUs for ultra-fast Whisper transcription, paired with Gemini 2.5 Flash
                for granular deliverables, mind maps, and compliance governance.
              </p>
              <div className="pt-2">
                <Button
                  onClick={() => setIsUploadOpen(true)}
                  className="h-10 px-6 rounded-full bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-medium text-xs shadow-lg shadow-[#ff5c47]/20 transition-all gap-2"
                >
                  <Upload className="w-4 h-4" />
                  Transcribe & Extract Meeting
                </Button>
              </div>
            </div>

            {/* Metric Tiles */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
              <div className="bg-[#141517] border border-[#232529] rounded-2xl p-6 space-y-2 shadow-sm">
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

              <div className="bg-[#141517] border border-[#232529] rounded-2xl p-6 space-y-2 shadow-sm">
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

              <div className="bg-[#141517] border border-[#232529] rounded-2xl p-6 space-y-2 shadow-sm">
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

            {/* Recent Sessions Table */}
            {sessions.length > 0 && (
              <div className="space-y-4">
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
                      className="bg-[#141517] border border-[#232529] hover:border-[#2e3238] rounded-2xl p-4 px-5 flex items-center justify-between cursor-pointer transition-all hover:bg-[#18191c]"
                    >
                      <div className="space-y-1">
                        <div className="text-sm font-semibold text-[#f0f2f5]">
                          {s.title || "Untitled Session"}
                        </div>
                        <div className="flex items-center gap-3 text-xs text-[#8b909a]">
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
                        className="rounded-full text-xs text-[#8b909a] hover:text-[#f0f2f5] hover:bg-[#232529]"
                      >
                        Open Workspace <ArrowRight className="w-3.5 h-3.5 ml-1" />
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
