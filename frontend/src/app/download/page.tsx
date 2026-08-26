"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Download,
  Monitor,
  CheckCircle2,
  ShieldCheck,
  AlertCircle,
  Copy,
  Check,
  ArrowRight,
  AudioWaveform,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  HardDrive,
  Sparkles,
  KeyRound,
  FolderOpen,
  FileCheck,
  RefreshCw,
  PlayCircle,
  Smartphone
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { DESKTOP_APP_CONFIG } from "@/lib/desktop-app";

export default function DownloadPage() {
  const [copiedHash, setCopiedHash] = useState(false);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const userAgent = navigator.userAgent || navigator.vendor || (window as any).opera;
      const isMobileDevice = /android|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(userAgent.toLowerCase());
      setIsMobile(isMobileDevice || window.innerWidth < 768);
    }
  }, []);

  const handleCopyHash = () => {
    navigator.clipboard.writeText(DESKTOP_APP_CONFIG.SHA256);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  return (
    <div className="min-h-screen bg-[#0c0d0e] text-[#f0f2f5] flex flex-col font-sans selection:bg-[#ff5c47]/30 selection:text-white">
      {/* Navigation Header */}
      <header className="h-16 border-b border-[#22242a] bg-[#121316]/80 backdrop-blur-md sticky top-0 z-50 px-4 sm:px-8 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47] shadow-sm">
            <AudioWaveform className="w-4 h-4" />
          </div>
          <span className="font-semibold text-base tracking-tight text-[#f3f4f6]">
            RecMap
          </span>
        </Link>

        <div className="flex items-center gap-3">
          <Link href="/login">
            <Button
              variant="ghost"
              size="sm"
              className="text-xs text-[#9ca3af] hover:text-[#f3f4f6] hover:bg-[#18191f] h-8 rounded-md"
            >
              Sign In
            </Button>
          </Link>
          <Link href="/">
            <Button
              size="sm"
              className="text-xs bg-[#18191f] hover:bg-[#22242a] text-[#f3f4f6] border border-[#22242a] h-8 rounded-md"
            >
              Web Workspace
            </Button>
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-12 sm:py-16 space-y-16">
        
        {/* Mobile Device Banner Notice */}
        {isMobile && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-4 rounded-xl bg-[#18191f] border border-[#ff5c47]/30 flex items-start gap-3 text-xs text-[#9ca3af]"
          >
            <Smartphone className="w-4 h-4 text-[#ff5c47] shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-[#f3f4f6]">
                RecMap Desktop is currently available for Windows 10 & 11 (64-bit).
              </p>
              <p className="mt-0.5 text-[11px]">
                You can download the installer on your PC or email this link to your desktop.
              </p>
            </div>
          </motion.div>
        )}

        {/* Hero Section */}
        <section className="text-center space-y-6 max-w-3xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-[#ff5c47]/10 text-[#ff5c47] border border-[#ff5c47]/20 shadow-sm"
          >
            <Monitor className="w-3.5 h-3.5" />
            <span>Windows Desktop App • v{DESKTOP_APP_CONFIG.VERSION}</span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.05 }}
            className="text-3xl sm:text-5xl font-bold tracking-tight text-[#f3f4f6] leading-tight"
          >
            Record your meetings securely from your desktop
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.1 }}
            className="text-sm sm:text-base text-[#9ca3af] leading-relaxed max-w-2xl mx-auto"
          >
            Capture system audio and microphone, keep a local backup, and send recordings directly to RecMap for transcription and meeting intelligence.
          </motion.p>

          {/* Primary CTA Area */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.15 }}
            className="pt-4 flex flex-col items-center gap-3"
          >
            <a
              href={DESKTOP_APP_CONFIG.DOWNLOAD_URL}
              className="inline-flex items-center justify-center gap-2.5 px-8 py-3.5 rounded-xl bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-semibold text-sm shadow-lg shadow-[#ff5c47]/20 hover:scale-[1.02] active:scale-[0.98] transition-all cursor-pointer"
            >
              <Download className="w-4 h-4" />
              <span>Download for Windows</span>
            </a>

            <div className="text-xs text-[#9ca3af] flex flex-wrap items-center justify-center gap-x-2 gap-y-1 font-mono">
              <span>{DESKTOP_APP_CONFIG.MIN_OS}</span>
              <span>•</span>
              <span>v{DESKTOP_APP_CONFIG.VERSION}</span>
              <span>•</span>
              <span>{DESKTOP_APP_CONFIG.SIZE_MB} MB</span>
            </div>

            <div className="pt-1">
              <a
                href={DESKTOP_APP_CONFIG.PORTABLE_DOWNLOAD_URL}
                className="text-[11px] text-[#9ca3af] hover:text-[#f3f4f6] underline underline-offset-4 transition-colors"
              >
                Prefer standalone portable executable? Download .exe ({DESKTOP_APP_CONFIG.PORTABLE_FILENAME})
              </a>
            </div>
          </motion.div>
        </section>

        {/* Feature Highlights Grid */}
        <section className="space-y-6">
          <div className="text-center space-y-1">
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-[#f3f4f6]">
              Engineered for Seamless Meeting Capture
            </h2>
            <p className="text-xs sm:text-sm text-[#9ca3af]">
              Designed to sit unobtrusively in your workspace while guaranteeing perfect audio fidelity.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="p-5 rounded-xl bg-[#121316] border border-[#22242a] space-y-2.5 hover:border-[#ff5c47]/30 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47]">
                <AudioWaveform className="w-4 h-4" />
              </div>
              <h3 className="font-semibold text-sm text-[#f3f4f6]">System Audio + Microphone</h3>
              <p className="text-xs text-[#9ca3af] leading-relaxed">
                Crystal-clear simultaneous capture of Windows loopback audio (remote participants) and your local microphone with gain balancing.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-[#121316] border border-[#22242a] space-y-2.5 hover:border-[#ff5c47]/30 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-[#3b82f6]/10 border border-[#3b82f6]/20 flex items-center justify-center text-[#3b82f6]">
                <HardDrive className="w-4 h-4" />
              </div>
              <h3 className="font-semibold text-sm text-[#f3f4f6]">Crash-Safe Local Streaming</h3>
              <p className="text-xs text-[#9ca3af] leading-relaxed">
                Incremental disk streaming writes chunks directly to disk in real time, ensuring no audio is lost during unexpected shutdowns.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-[#121316] border border-[#22242a] space-y-2.5 hover:border-[#ff5c47]/30 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-[#10b981]/10 border border-[#10b981]/20 flex items-center justify-center text-[#10b981]">
                <RefreshCw className="w-4 h-4" />
              </div>
              <h3 className="font-semibold text-sm text-[#f3f4f6]">Automatic Recovery</h3>
              <p className="text-xs text-[#9ca3af] leading-relaxed">
                Interrupted sessions are automatically detected, validated, and repaired into standard WebM files on the next application launch.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-[#121316] border border-[#22242a] space-y-2.5 hover:border-[#ff5c47]/30 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-[#8b5cf6]/10 border border-[#8b5cf6]/20 flex items-center justify-center text-[#8b5cf6]">
                <KeyRound className="w-4 h-4" />
              </div>
              <h3 className="font-semibold text-sm text-[#f3f4f6]">Private Encrypted Auth</h3>
              <p className="text-xs text-[#9ca3af] leading-relaxed">
                Credentials and session tokens are encrypted with OS-level safeStorage with zero plaintext secrets and proactive refresh.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-[#121316] border border-[#22242a] space-y-2.5 hover:border-[#ff5c47]/30 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-[#f59e0b]/10 border border-[#f59e0b]/20 flex items-center justify-center text-[#f59e0b]">
                <Sparkles className="w-4 h-4" />
              </div>
              <h3 className="font-semibold text-sm text-[#f3f4f6]">Automatic AI Analysis</h3>
              <p className="text-xs text-[#9ca3af] leading-relaxed">
                Direct authenticated upload to RecMap triggers AI transcription, executive summaries, interactive mind maps, and task assignments.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-[#121316] border border-[#22242a] space-y-2.5 hover:border-[#ff5c47]/30 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-[#ec4899]/10 border border-[#ec4899]/20 flex items-center justify-center text-[#ec4899]">
                <FolderOpen className="w-4 h-4" />
              </div>
              <h3 className="font-semibold text-sm text-[#f3f4f6]">Offline Backup Preservation</h3>
              <p className="text-xs text-[#9ca3af] leading-relaxed">
                Even if network connectivity drops, full recordings remain safe in your local Recordings directory for manual inspection or playback.
              </p>
            </div>
          </div>
        </section>

        {/* Installation Instructions */}
        <section className="p-6 sm:p-8 rounded-2xl bg-[#121316] border border-[#22242a] space-y-6">
          <div className="space-y-1">
            <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#f3f4f6]">
              Quick Installation & Setup Guide
            </h2>
            <p className="text-xs sm:text-sm text-[#9ca3af]">
              Get started with desktop recording in under two minutes.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex items-start gap-3 p-3.5 rounded-lg bg-[#18191f] border border-[#22242a]">
              <span className="w-6 h-6 rounded-full bg-[#ff5c47]/20 text-[#ff5c47] font-semibold text-xs flex items-center justify-center shrink-0">
                1
              </span>
              <div className="space-y-0.5">
                <h4 className="text-xs font-semibold text-[#f3f4f6]">Download Installer</h4>
                <p className="text-[11.5px] text-[#9ca3af]">
                  Download <code className="text-[#f3f4f6] font-mono text-[10.5px]">RecMap Desktop Recorder Setup 1.0.0.exe</code>.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3.5 rounded-lg bg-[#18191f] border border-[#22242a]">
              <span className="w-6 h-6 rounded-full bg-[#ff5c47]/20 text-[#ff5c47] font-semibold text-xs flex items-center justify-center shrink-0">
                2
              </span>
              <div className="space-y-0.5">
                <h4 className="text-xs font-semibold text-[#f3f4f6]">Run the Installer</h4>
                <p className="text-[11.5px] text-[#9ca3af]">
                  Launch the setup file to install the floating companion recorder.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3.5 rounded-lg bg-[#18191f] border border-[#22242a]">
              <span className="w-6 h-6 rounded-full bg-[#ff5c47]/20 text-[#ff5c47] font-semibold text-xs flex items-center justify-center shrink-0">
                3
              </span>
              <div className="space-y-0.5">
                <h4 className="text-xs font-semibold text-[#f3f4f6]">Sign in to RecMap</h4>
                <p className="text-[11.5px] text-[#9ca3af]">
                  Log in with your existing RecMap account to sync with your cloud quota.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3.5 rounded-lg bg-[#18191f] border border-[#22242a]">
              <span className="w-6 h-6 rounded-full bg-[#ff5c47]/20 text-[#ff5c47] font-semibold text-xs flex items-center justify-center shrink-0">
                4
              </span>
              <div className="space-y-0.5">
                <h4 className="text-xs font-semibold text-[#f3f4f6]">Record Your Meetings</h4>
                <p className="text-[11.5px] text-[#9ca3af]">
                  Press <strong>Start Recording</strong> during meetings. Stop when finished to automatically analyze.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Windows SmartScreen Notice */}
        <section className="p-5 sm:p-6 rounded-xl bg-[#18191f] border border-[#22242a] flex items-start gap-4">
          <div className="w-9 h-9 rounded-lg bg-[#3b82f6]/10 border border-[#3b82f6]/20 flex items-center justify-center text-[#3b82f6] shrink-0 mt-0.5">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div className="space-y-1.5 text-xs text-[#9ca3af]">
            <h3 className="font-semibold text-sm text-[#f3f4f6]">
              Windows SmartScreen Notice
            </h3>
            <p className="leading-relaxed">
              Windows may display a SmartScreen warning because this is an early release that is not yet code-signed with an EV certificate.
            </p>
            <p className="text-[11px] text-[#9ca3af] bg-[#121316] p-2.5 rounded-md border border-[#22242a] font-mono">
              To proceed: Click <span className="text-[#f3f4f6] font-semibold">More info</span> → Select <span className="text-[#ff5c47] font-semibold">Run anyway</span>.
            </p>
          </div>
        </section>

        {/* Collapsible Advanced / Checksum Section */}
        <section className="p-5 rounded-xl bg-[#121316] border border-[#22242a] space-y-3">
          <button
            onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
            className="w-full flex items-center justify-between text-xs font-semibold text-[#9ca3af] hover:text-[#f3f4f6] transition-colors cursor-pointer"
          >
            <span>Advanced / Verify Download & Checksums</span>
            {isAdvancedOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {isAdvancedOpen && (
            <div className="pt-2 space-y-3 border-t border-[#22242a] text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[#9ca3af]">
                <div>
                  <span className="text-[11px] text-[#6b7280] block">File Name</span>
                  <span className="font-mono text-[#f3f4f6] text-[11px]">{DESKTOP_APP_CONFIG.FILENAME}</span>
                </div>
                <div>
                  <span className="text-[11px] text-[#6b7280] block">Release Tag</span>
                  <span className="font-mono text-[#f3f4f6] text-[11px]">{DESKTOP_APP_CONFIG.RELEASE_TAG}</span>
                </div>
                <div>
                  <span className="text-[11px] text-[#6b7280] block">Size</span>
                  <span className="font-mono text-[#f3f4f6] text-[11px]">{DESKTOP_APP_CONFIG.SIZE_MB} MB ({DESKTOP_APP_CONFIG.SIZE_BYTES.toLocaleString()} bytes)</span>
                </div>
                <div>
                  <span className="text-[11px] text-[#6b7280] block">Release Target</span>
                  <span className="font-mono text-[#f3f4f6] text-[11px]">Windows x64 NSIS Setup</span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] text-[#6b7280] block">SHA-256 Checksum</span>
                <div className="flex items-center gap-2 p-2 rounded bg-[#18191f] border border-[#22242a]">
                  <code className="text-[10px] sm:text-[11px] text-[#f3f4f6] font-mono break-all flex-1">
                    {DESKTOP_APP_CONFIG.SHA256}
                  </code>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={handleCopyHash}
                    className="w-7 h-7 shrink-0 text-[#9ca3af] hover:text-[#f3f4f6] hover:bg-[#22242a]"
                    title="Copy SHA-256 Hash"
                  >
                    {copiedHash ? <Check className="w-3.5 h-3.5 text-[#10b981]" /> : <Copy className="w-3.5 h-3.5" />}
                  </Button>
                </div>
              </div>

              <div className="pt-1 flex items-center justify-between text-[11px]">
                <a
                  href={DESKTOP_APP_CONFIG.GITHUB_RELEASE_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[#ff5c47] hover:underline"
                >
                  <span>View Release on GitHub</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          )}
        </section>

      </main>

      {/* Footer */}
      <footer className="border-t border-[#22242a] bg-[#121316] py-8 px-4 sm:px-8 text-xs text-[#9ca3af]">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <AudioWaveform className="w-4 h-4 text-[#ff5c47]" />
            <span className="font-medium text-[#f3f4f6]">RecMap Technologies</span>
            <span>•</span>
            <span>Intelligent Voice & Meeting Companion</span>
          </div>

          <div className="flex items-center gap-4">
            <Link href="/" className="hover:text-[#f3f4f6] transition-colors">
              Workspace
            </Link>
            <Link href="/login" className="hover:text-[#f3f4f6] transition-colors">
              Sign In
            </Link>
            <a
              href={DESKTOP_APP_CONFIG.GITHUB_RELEASE_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-[#f3f4f6] transition-colors"
            >
              GitHub Release
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
