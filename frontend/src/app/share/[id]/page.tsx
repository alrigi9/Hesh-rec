"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { 
  AudioWaveform, 
  ArrowLeft, 
  Globe, 
  ShieldCheck, 
  Loader2,
  AlertCircle 
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MeetingView } from "@/components/MeetingView";
import { MeetingSession } from "@/types/meeting";
import { fetchSessionById } from "@/lib/api";

interface SharePageProps {
  params: Promise<{ id: string }> | { id: string };
}

export default function SharePage({ params }: SharePageProps) {
  // Unwrap params safely for Next.js App Router
  const resolvedParams = params instanceof Promise ? use(params) : params;
  const sessionId = resolvedParams.id;

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
    <div className="min-h-screen bg-[#0c0d0e] text-[#f0f2f5] flex flex-col font-sans selection:bg-[#ff5c47]/30 selection:text-white">
      {/* Top Public Header */}
      <header className="h-14 border-b border-[#232529] px-6 flex items-center justify-between bg-[#111215]/80 backdrop-blur-md sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2 text-xs text-[#8b909a] hover:text-[#f0f2f5] transition-colors">
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Dashboard</span>
          </Link>
          <span className="text-[#232529]">/</span>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47]">
              <AudioWaveform className="w-3.5 h-3.5" />
            </div>
            <span className="font-semibold text-xs text-[#f0f2f5] font-heading">
              Hesh Rec
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="flex items-center gap-1 text-[11px] py-1 px-3 border-[#232529] bg-[#18191c] text-[#8b909a]"
          >
            <Globe className="w-3 h-3 text-[#3ec98a]" />
            <span>Public Read-Only</span>
          </Badge>
          <Badge
            variant="outline"
            className="flex items-center gap-1 text-[11px] py-1 px-3 border-[#232529] bg-[#18191c] text-[#8b909a]"
          >
            <ShieldCheck className="w-3 h-3 text-[#3ec98a]" />
            <span>SOC 2 Verified</span>
          </Badge>
        </div>
      </header>

      {/* Main Content Body */}
      <main className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3 text-[#8b909a]">
            <Loader2 className="w-6 h-6 animate-spin text-[#ff5c47]" />
            <span className="text-xs">Loading shared meeting record...</span>
          </div>
        )}

        {!loading && error && (
          <div className="max-w-md mx-auto my-20 p-8 rounded-2xl bg-[#141517] border border-[#232529] text-center space-y-4 shadow-sm">
            <div className="w-12 h-12 rounded-full bg-[#f9ab00]/10 border border-[#f9ab00]/20 flex items-center justify-center text-[#f9ab00] mx-auto">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h2 className="text-base font-semibold text-[#f0f2f5] font-heading">
              Meeting Not Found
            </h2>
            <p className="text-xs text-[#8b909a] leading-relaxed">
              {error}
            </p>
            <Link href="/">
              <Button className="h-9 px-4 rounded-full bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white text-xs mt-2">
                Open Hesh Rec Studio
              </Button>
            </Link>
          </div>
        )}

        {!loading && session && (
          <MeetingView session={session} />
        )}
      </main>
    </div>
  );
}
