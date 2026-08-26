"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { 
  AudioWaveform, 
  ArrowLeft, 
  Globe, 
  ShieldCheck, 
  Loader2, 
  AlertCircle 
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { MeetingView } from "@/components/MeetingView";
import { MeetingSession } from "@/types/meeting";
import { fetchSessionById } from "@/lib/api";

export default function SharePage() {
  const routeParams = useParams();
  const sessionId = Array.isArray(routeParams?.id) ? routeParams.id[0] : (routeParams?.id as string);

  const [session, setSession] = useState<MeetingSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadSharedMeeting() {
      if (!sessionId) return;
      try {
        setLoading(true);
        const data = await fetchSessionById(sessionId);
        if (!data) {
          setError("Meeting session not found or link has expired.");
        } else {
          setSession(data);
        }
      } catch (err: any) {
        setError(err.message || "Failed to load shared meeting.");
      } finally {
        setLoading(false);
      }
    }

    loadSharedMeeting();
  }, [sessionId]);

  return (
    <div className="min-h-screen bg-[#0d0e11] text-[#f3f4f6] flex flex-col font-sans selection:bg-[#ff5c47]/30 selection:text-white">
      {/* Top Public Header */}
      <header className="h-14 border-b border-[#22242a] px-4 sm:px-6 flex items-center justify-between bg-[#121316] sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-1.5 text-xs text-[#9ca3af] hover:text-[#f3f4f6] transition-colors">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Workspace</span>
          </Link>
          <span className="text-[#22242a]">/</span>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47]">
              <AudioWaveform className="w-3.5 h-3.5" />
            </div>
            <span className="font-semibold text-xs text-[#f3f4f6]">
              RecMap
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 text-[11px] py-0.5 px-2 rounded bg-[#18191f] border border-[#22242a] text-[#9ca3af]">
            <Globe className="w-3 h-3 text-[#10b981]" />
            <span>Public View</span>
          </span>
        </div>
      </header>

      {/* Main Content Body */}
      <main className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] gap-2.5 text-[#9ca3af]">
            <Loader2 className="w-5 h-5 animate-spin text-[#ff5c47]" />
            <span className="text-xs">Loading shared meeting record...</span>
          </div>
        )}

        {!loading && error && (
          <div className="max-w-md mx-auto my-20 p-6 rounded-xl bg-[#131418] border border-[#22242a] text-center space-y-3 shadow-lg">
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mx-auto">
              <AlertCircle className="w-5 h-5" />
            </div>
            <h2 className="text-base font-semibold text-[#f3f4f6]">
              Meeting Not Found
            </h2>
            <p className="text-xs text-[#9ca3af] leading-relaxed">
              {error}
            </p>
            <Link href="/">
              <Button className="h-8 px-4 rounded-md bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white text-xs mt-2 font-medium">
                Open Workspace
              </Button>
            </Link>
          </div>
        )}

        {!loading && session && (
          <MeetingView session={session} onSessionUpdated={setSession} readOnly={true} />
        )}
      </main>
    </div>
  );
}
