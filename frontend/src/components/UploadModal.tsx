"use client";

import React, { useState, useRef, useEffect } from "react";
import { 
  Upload, 
  FileAudio, 
  Sparkles, 
  Loader2, 
  AlertCircle,
  CheckCircle2,
  WifiOff
} from "lucide-react";
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription 
} from "@/components/ui/dialog";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { processAudioFile } from "@/lib/api";
import { MeetingSession } from "@/types/meeting";
import { useAuth } from "@/context/AuthContext";

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (session: MeetingSession) => void;
}

export function UploadModal({ isOpen, onClose, onSuccess }: UploadModalProps) {
  const router = useRouter();
  const { user, token, profile, isAdmin, refreshProfile } = useAuth();

  const [file, setFile] = useState<File | null>(null);
  const [template, setTemplate] = useState("executive");
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [processingStage, setProcessingStage] = useState<"uploading" | "transcribing" | "synthesizing">("uploading");
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isQuotaExceeded = (profile?.minutes_used_this_month ?? 0) >= (profile?.monthly_minutes_limit ?? 300) && !isAdmin;

  // Cleanup on modal close
  useEffect(() => {
    if (!isOpen) {
      setFile(null);
      setTitle("");
      setError(null);
      setLoading(false);
    }
  }, [isOpen]);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setError(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleProcess = async () => {
    if (!user) {
      onClose();
      router.push("/login?msg=" + encodeURIComponent("Please sign in or create an account to transcribe audio (300 free mins/month)"));
      return;
    }

    if (!file) {
      setError("Please select an audio or video file.");
      return;
    }

    if (isQuotaExceeded) {
      setError(`Monthly quota limit of ${profile?.monthly_minutes_limit ?? 300} minutes has been reached.`);
      return;
    }

    setLoading(true);
    setError(null);
    setProcessingStage("uploading");

    const stageTimer1 = setTimeout(() => setProcessingStage("transcribing"), 1500);
    const stageTimer2 = setTimeout(() => setProcessingStage("synthesizing"), 4500);

    try {
      const result = await processAudioFile(
        file, 
        template, 
        title || undefined, 
        user?.id, 
        token || undefined
      );
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      setLoading(false);
      onSuccess(result);
      refreshProfile();
      onClose();
      setFile(null);
      setTitle("");
    } catch (err: unknown) {
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      setLoading(false);
      
      let msg = err instanceof Error ? err.message : "Failed to process media file.";
      if (msg.includes("Failed to fetch") || msg.includes("NetworkError") || msg.includes("Load failed")) {
        msg = "Server unreachable. Please check your connection or try again in a few moments.";
      }
      setError(msg);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !loading && onClose()}>
      <DialogContent className="sm:max-w-[480px] bg-[#13151B] border border-white/[0.08] text-[#f0f2f5] p-6 rounded-2xl shadow-2xl">
        <DialogHeader className="space-y-1">
          <DialogTitle className="text-lg font-semibold tracking-tight text-[#f0f2f5] font-heading flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#ff5c47]" />
            Upload File
          </DialogTitle>
          <DialogDescription className="text-xs text-[#8b909a]">
            Fast, secure transcription with instant executive summaries, mind maps, and action items.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {/* Drag and Drop Zone */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-7 text-center cursor-pointer transition-all ${
              file
                ? "border-[#ff5c47]/50 bg-[#ff5c47]/5"
                : "border-white/10 hover:border-white/20 bg-[#18191c]"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".mp3,.m4a,.wav,.webm,.mp4,.mov,.aac,.flac"
              className="hidden"
              onChange={handleFileChange}
            />

            {file ? (
              <div className="flex flex-col items-center gap-2">
                <div className="w-11 h-11 rounded-full bg-[#ff5c47]/10 flex items-center justify-center text-[#ff5c47]">
                  <FileAudio className="w-5 h-5" />
                </div>
                <div className="font-medium text-xs text-[#f0f2f5] max-w-[280px] truncate">
                  {file.name}
                </div>
                <div className="text-[11px] text-[#8b909a]">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB • Click to replace
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2.5">
                <div className="w-11 h-11 rounded-full bg-white/5 flex items-center justify-center text-[#8b909a]">
                  <Upload className="w-5 h-5 text-[#ff5c47]" />
                </div>
                <div className="font-medium text-xs text-[#f0f2f5]">
                  Drop audio or video file here, or click to browse
                </div>
                <div className="text-[11px] text-[#8b909a]">
                  MP3, M4A, WAV, WebM, MP4, MOV, AAC, FLAC (Up to 50MB)
                </div>
              </div>
            )}
          </div>

          {/* Template Selection */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[#8b909a]">Intelligence Template</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: "executive", label: "Executive Summary" },
                { id: "academic", label: "Structured Deep-Dive" },
                { id: "brainstorm", label: "Ideation & Strategy" },
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTemplate(t.id)}
                  className={`py-2 px-2.5 rounded-xl text-xs font-medium border transition-all text-center ${
                    template === t.id
                      ? "bg-[#ff5c47]/10 border-[#ff5c47] text-[#ff5c47]"
                      : "bg-[#18191c] border-white/[0.08] text-[#8b909a] hover:text-[#f0f2f5]"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Optional Title */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[#8b909a]">Meeting Title (Optional)</label>
            <input
              type="text"
              placeholder="e.g., Executive Strategy & Roadmap Review"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full h-10 px-3.5 bg-[#18191c] text-xs text-[#f0f2f5] placeholder-[#8b909a] rounded-xl border border-white/[0.08] focus:outline-none focus:border-[#ff5c47]/50 transition-colors"
            />
          </div>

          {/* Active Step Progression Indicator */}
          {loading && (
            <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-[#f0f2f5] flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 text-[#ff5c47] animate-spin" />
                  {processingStage === "uploading" && "Uploading File..."}
                  {processingStage === "transcribing" && "Transcribing Speech..."}
                  {processingStage === "synthesizing" && "Generating Executive Summary & Mind Map..."}
                </span>
                <span className="text-[11px] text-[#ff5c47] font-mono font-semibold">
                  {processingStage === "uploading" && "Step 1/3"}
                  {processingStage === "transcribing" && "Step 2/3"}
                  {processingStage === "synthesizing" && "Step 3/3"}
                </span>
              </div>

              {/* Step Progression Badges */}
              <div className="grid grid-cols-3 gap-1.5 text-[10px] font-medium text-center">
                <div className={`py-1 px-1.5 rounded-lg transition-all ${
                  processingStage === "uploading" 
                    ? "bg-[#ff5c47]/20 border border-[#ff5c47]/40 text-[#ff5c47]" 
                    : "bg-white/5 text-[#3ec98a]"
                }`}>
                  1. Upload
                </div>
                <div className={`py-1 px-1.5 rounded-lg transition-all ${
                  processingStage === "transcribing" 
                    ? "bg-[#ff5c47]/20 border border-[#ff5c47]/40 text-[#ff5c47]" 
                    : processingStage === "synthesizing"
                    ? "bg-white/5 text-[#3ec98a]"
                    : "bg-white/5 text-[#8b909a]"
                }`}>
                  2. Transcribe
                </div>
                <div className={`py-1 px-1.5 rounded-lg transition-all ${
                  processingStage === "synthesizing" 
                    ? "bg-[#ff5c47]/20 border border-[#ff5c47]/40 text-[#ff5c47]" 
                    : "bg-white/5 text-[#8b909a]"
                }`}>
                  3. Summarize
                </div>
              </div>

              <div className="w-full bg-white/10 h-1.5 rounded-full overflow-hidden">
                <div 
                  className="bg-[#ff5c47] h-full rounded-full transition-all duration-500"
                  style={{
                    width: processingStage === "uploading" ? "33%" : processingStage === "transcribing" ? "66%" : "95%"
                  }}
                />
              </div>
            </div>
          )}

          {/* User-friendly Error Banner */}
          {error && (
            <div className="p-3.5 bg-[#eb5757]/10 border border-[#eb5757]/20 rounded-xl text-xs text-[#eb5757] flex items-start gap-2.5">
              {error.includes("Server unreachable") ? (
                <WifiOff className="w-4 h-4 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              )}
              <div className="space-y-0.5">
                <div className="font-semibold">{error.includes("Server unreachable") ? "Connection Error" : "Upload Failed"}</div>
                <div className="text-[11px] text-[#eb5757]/90 leading-relaxed">{error}</div>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              disabled={loading}
              onClick={onClose}
              className="h-10 px-4 rounded-full text-xs border-white/10 bg-[#18191c] text-[#8b909a] hover:text-[#f0f2f5]"
            >
              Cancel
            </Button>
            <Button
              type="button"
              disabled={loading || !file || isQuotaExceeded}
              onClick={handleProcess}
              className="h-10 px-6 rounded-full text-xs bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-semibold shadow-lg shadow-[#ff5c47]/25 transition-all"
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                  Processing Audio...
                </>
              ) : isQuotaExceeded ? (
                "Quota Limit Reached"
              ) : (
                "Upload File"
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
