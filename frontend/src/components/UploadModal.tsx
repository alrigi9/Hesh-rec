"use client";

import React, { useState, useRef } from "react";
import { 
  Upload, 
  FileAudio, 
  Sparkles, 
  Loader2, 
  AlertCircle 
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
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isQuotaExceeded = (profile?.minutes_used_this_month ?? 0) >= (profile?.monthly_minutes_limit ?? 300) && !isAdmin;

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
      setError("Please select an audio file.");
      return;
    }

    if (isQuotaExceeded) {
      setError(`Monthly quota limit of ${profile?.monthly_minutes_limit ?? 300} minutes has been reached.`);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await processAudioFile(
        file, 
        template, 
        title || undefined, 
        user?.id, 
        token || undefined
      );
      setLoading(false);
      onSuccess(result);
      // Refresh user's quota badge in real-time
      refreshProfile();
      onClose();
      // Reset state
      setFile(null);
      setTitle("");
    } catch (err: unknown) {
      setLoading(false);
      const msg = err instanceof Error ? err.message : "Failed to process audio file.";
      setError(msg);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !loading && onClose()}>
      <DialogContent className="sm:max-w-[480px] bg-[#141517] border-[#232529] text-[#f0f2f5] p-6 rounded-2xl shadow-2xl">
        <DialogHeader className="space-y-1">
          <DialogTitle className="text-lg font-semibold tracking-tight text-[#f0f2f5] font-heading flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#ff5c47]" />
            Upload & Extract Intelligence
          </DialogTitle>
          <DialogDescription className="text-xs text-[#8b909a]">
            Fast, secure transcription with instant executive summaries and interactive mind maps.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {/* Drag and Drop Zone */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
              file
                ? "border-[#ff5c47]/50 bg-[#ff5c47]/5"
                : "border-[#2e3238] hover:border-[#3e434c] bg-[#18191c]"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".mp3,.wav,.m4a,.mp4,.aac,.ogg,.flac"
              className="hidden"
              onChange={handleFileChange}
            />

            {file ? (
              <div className="flex flex-col items-center gap-2">
                <div className="w-10 h-10 rounded-full bg-[#ff5c47]/10 flex items-center justify-center text-[#ff5c47]">
                  <FileAudio className="w-5 h-5" />
                </div>
                <div className="font-medium text-xs text-[#f0f2f5] max-w-[280px] truncate">
                  {file.name}
                </div>
                <div className="text-[11px] text-[#8b909a]">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB • Click to change
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <div className="w-10 h-10 rounded-full bg-[#232529] flex items-center justify-center text-[#8b909a]">
                  <Upload className="w-5 h-5" />
                </div>
                <div className="font-medium text-xs text-[#f0f2f5]">
                  Drop audio file or click to browse
                </div>
                <div className="text-[11px] text-[#8b909a]">
                  Supports MP3, WAV, M4A, MP4, AAC, FLAC (up to 50MB)
                </div>
              </div>
            )}
          </div>

          {/* Template Selection */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[#8b909a]">Summary Template</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: "executive", label: "Executive" },
                { id: "academic", label: "Academic" },
                { id: "brainstorm", label: "Ideation" },
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTemplate(t.id)}
                  className={`py-2 px-3 rounded-lg text-xs font-medium border transition-all ${
                    template === t.id
                      ? "bg-[#ff5c47]/10 border-[#ff5c47] text-[#ff5c47]"
                      : "bg-[#18191c] border-[#232529] text-[#8b909a] hover:text-[#f0f2f5]"
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
              placeholder="e.g., SOC 2 Architecture & Security Review"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full h-9 px-3 bg-[#18191c] text-xs text-[#f0f2f5] placeholder-[#8b909a] rounded-lg border border-[#232529] focus:outline-none focus:border-[#ff5c47]/50 transition-colors"
            />
          </div>

          {/* Error feedback */}
          {error && (
            <div className="p-3 bg-[#eb5757]/10 border border-[#eb5757]/20 rounded-lg text-xs text-[#eb5757] flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              disabled={loading}
              onClick={onClose}
              className="h-9 px-4 rounded-full text-xs border-[#232529] bg-[#18191c] text-[#8b909a] hover:text-[#f0f2f5]"
            >
              Cancel
            </Button>
            <Button
              type="button"
              disabled={loading || !file || isQuotaExceeded}
              onClick={handleProcess}
              className="h-9 px-5 rounded-full text-xs bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-medium shadow-sm transition-all"
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                  Transcribing & Analyzing...
                </>
              ) : isQuotaExceeded ? (
                "Quota Limit Reached"
              ) : (
                "Transcribe & Analyze"
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
