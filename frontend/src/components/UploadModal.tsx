"use client";

export const dynamic = "force-dynamic";

import React, { useState, useRef, useEffect } from "react";
import { 
  Upload, 
  FileAudio, 
  Sparkles, 
  Loader2, 
  AlertCircle,
  CheckCircle2,
  WifiOff,
  Globe,
  Clock,
  X
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
import { TemplateId, TEMPLATES_CONFIG, VALID_TEMPLATES } from "@/lib/templates";

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (session: MeetingSession) => void;
}

type ProcessingStage = "uploading" | "extracting" | "transcribing" | "synthesizing";

export function UploadModal({ isOpen, onClose, onSuccess }: UploadModalProps) {
  const router = useRouter();
  const { user, token, profile, isAdmin, refreshProfile } = useAuth();

  const [file, setFile] = useState<File | null>(null);
  const [template, setTemplate] = useState<TemplateId>("auto");
  const [language, setLanguage] = useState<"auto" | "en" | "ar">("auto");

  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadPercent, setUploadPercent] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [processingStage, setProcessingStage] = useState<ProcessingStage>("uploading");
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
      setUploadPercent(0);
      setElapsedSeconds(0);
    }
  }, [isOpen]);

  const SUPPORTED_EXTENSIONS = [
    ".mp3", ".m4a", ".wav", ".webm", ".mp4", ".mov", ".aac", ".flac", ".ogg", ".opus", ".m4v"
  ];

  const validateSelectedFile = (selectedFile: File): boolean => {
    const ext = "." + (selectedFile.name.split(".").pop() || "").toLowerCase();
    const isAudioOrVideo = selectedFile.type.startsWith("audio/") || selectedFile.type.startsWith("video/");
    const isSupportedExt = SUPPORTED_EXTENSIONS.includes(ext);

    if (!isAudioOrVideo && !isSupportedExt) {
      setError("This format is not supported for transcription. Please upload MP4, MOV, WebM, M4A, MP3, or WAV.");
      return false;
    }

    if (selectedFile.size > 25 * 1024 * 1024) {
      setError(`File size (${(selectedFile.size / (1024 * 1024)).toFixed(1)} MB) exceeds the 25 MB transcription limit. Please upload a file under 25 MB.`);
      return false;
    }

    return true;
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (validateSelectedFile(droppedFile)) {
        setFile(droppedFile);
        setError(null);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const chosenFile = e.target.files[0];
      if (validateSelectedFile(chosenFile)) {
        setFile(chosenFile);
        setError(null);
      }
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

    if (!validateSelectedFile(file)) {
      return;
    }

    if (isQuotaExceeded) {
      setError(`Monthly quota limit of ${profile?.monthly_minutes_limit ?? 300} minutes has been reached.`);
      return;
    }

    setLoading(true);
    setError(null);

    setProcessingStage("uploading");
    setUploadPercent(25);
    setElapsedSeconds(0);

    const elapsedTimer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    const uploadTimer = setInterval(() => {
      setUploadPercent((prev) => (prev < 90 ? prev + 10 : prev));
    }, 500);

    const stageTimer1 = setTimeout(() => {
      setProcessingStage("extracting");
      setUploadPercent(100);
    }, 3000);

    const stageTimer2 = setTimeout(() => {
      setProcessingStage("transcribing");
    }, 7000);

    const stageTimer3 = setTimeout(() => {
      setProcessingStage("synthesizing");
    }, 16000);

    const safetyTimeout = setTimeout(() => {
      clearInterval(elapsedTimer);
      clearInterval(uploadTimer);
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      clearTimeout(stageTimer3);
      setLoading(false);
      setError("Processing took longer than expected. Please check your network connection.");
    }, 300000);

    try {
      const result = await processAudioFile(
        file, 
        template, 
        title || undefined, 
        user?.id, 
        token || undefined,
        language
      );
      
      clearTimeout(safetyTimeout);
      clearInterval(elapsedTimer);
      clearInterval(uploadTimer);
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      clearTimeout(stageTimer3);
      setLoading(false);
      onSuccess(result);
      refreshProfile();
      onClose();
      setFile(null);
      setTitle("");
    } catch (err: unknown) {
      clearTimeout(safetyTimeout);
      clearInterval(elapsedTimer);
      clearInterval(uploadTimer);
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      clearTimeout(stageTimer3);
      setLoading(false);
      
      let msg = "Failed to process media file.";
      if (typeof err === "string") {
        msg = err;
      } else if (err instanceof Error) {
        msg = err.message;
      } else if (typeof err === "object" && err !== null) {
        const anyErr = err as any;
        msg = anyErr.detail || anyErr.message || anyErr.error || JSON.stringify(err);
      }
      if (typeof msg === "object") {
        msg = JSON.stringify(msg);
      }
      if (msg.includes("Failed to fetch") || msg.includes("NetworkError") || msg.includes("Load failed")) {
        msg = "Network connection lost or server unreachable. Please try again.";
      }
      setError(msg);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !loading && onClose()}>
      <DialogContent className="sm:max-w-[480px] bg-[#131418] border border-[#22242a] text-[#f3f4f6] p-5 sm:p-6 rounded-xl shadow-xl">
        <DialogHeader className="space-y-1 text-left">
          <DialogTitle className="text-base font-semibold tracking-tight text-[#f3f4f6]">
            Upload Meeting Recording
          </DialogTitle>
          <DialogDescription className="text-xs text-[#9ca3af]">
            Upload an audio or video file to extract transcript, structured summary, and action items.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {/* Drag and Drop Zone */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border border-dashed rounded-lg p-5 text-center cursor-pointer transition-colors ${
              file
                ? "border-[#ff5c47]/60 bg-[#ff5c47]/5"
                : "border-[#2a2c36] hover:border-[#ff5c47]/40 bg-[#18191f]"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*,video/*,.mp3,.m4a,.wav,.webm,.mp4,.mov,.aac,.flac,.ogg,.opus,.m4v"
              className="hidden"
              onChange={handleFileChange}
            />

            {file ? (
              <div className="flex items-center justify-between gap-3 text-left">
                <div className="flex items-center gap-2.5 truncate">
                  <div className="w-8 h-8 rounded bg-[#ff5c47]/10 flex items-center justify-center text-[#ff5c47] shrink-0">
                    <FileAudio className="w-4 h-4" />
                  </div>
                  <div className="truncate">
                    <div className="font-medium text-xs text-[#f3f4f6] truncate">
                      {file.name}
                    </div>
                    <div className="text-[10.5px] text-[#9ca3af] font-mono">
                      {(file.size / (1024 * 1024)).toFixed(2)} MB
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                  }}
                  className="p-1 rounded hover:bg-[#22242a] text-[#9ca3af] hover:text-[#f3f4f6]"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <div className="w-9 h-9 rounded-md bg-[#22242a] flex items-center justify-center text-[#9ca3af]">
                  <Upload className="w-4 h-4 text-[#f3f4f6]" />
                </div>
                <div>
                  <div className="font-medium text-xs text-[#f3f4f6]">
                    Click to browse or drop file here
                  </div>
                  <div className="text-[10.5px] text-[#9ca3af] mt-0.5">
                    MP4, MOV, WebM, M4A, MP3, WAV (Up to 25 MB)
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Language Selection */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-[#9ca3af]">
              Output Language
            </label>
            <div className="grid grid-cols-3 gap-1.5">
              {[
                { id: "auto", label: "Auto-Detect" },
                { id: "en", label: "English" },
                { id: "ar", label: "العربية" },
              ].map((l) => (
                <button
                  key={l.id}
                  type="button"
                  onClick={() => setLanguage(l.id as any)}
                  className={`py-1.5 px-2 rounded-md text-xs font-medium border transition-colors text-center ${
                    language === l.id
                      ? "bg-[#1e2027] border-[#ff5c47] text-[#ff5c47]"
                      : "bg-[#18191f] border-[#22242a] text-[#9ca3af] hover:text-[#f3f4f6]"
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          {/* Meeting Template Selection */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-medium text-[#9ca3af]">
                Analysis Template
              </label>
              <span className="text-[10px] text-[#ff5c47] font-mono uppercase">
                {TEMPLATES_CONFIG[template]?.badge}
              </span>
            </div>

            <div className="grid grid-cols-4 gap-1">
              {VALID_TEMPLATES.map((tId) => {
                const tConfig = TEMPLATES_CONFIG[tId];
                const isSelected = template === tId;
                return (
                  <button
                    key={tId}
                    type="button"
                    onClick={() => setTemplate(tId)}
                    className={`py-1.5 px-1 rounded-md text-[11px] font-medium border transition-colors text-center truncate ${
                      isSelected
                        ? "bg-[#1e2027] border-[#ff5c47] text-[#ff5c47]"
                        : "bg-[#18191f] border-[#22242a] text-[#9ca3af] hover:text-[#f3f4f6]"
                    }`}
                  >
                    {tConfig.label.split(" ")[0]}
                  </button>
                );
              })}
            </div>

            {/* Template dynamic description */}
            <div className="p-2.5 rounded-md bg-[#18191f] border border-[#22242a] text-[11px] text-[#9ca3af] leading-relaxed">
              <span className="text-[#f3f4f6] font-medium block">
                {language === "ar" ? TEMPLATES_CONFIG[template]?.labelAr : TEMPLATES_CONFIG[template]?.label}
              </span>
              {language === "ar" ? TEMPLATES_CONFIG[template]?.descriptionAr : TEMPLATES_CONFIG[template]?.description}
            </div>
          </div>

          {/* Optional Title */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-[#9ca3af]">Meeting Title (Optional)</label>
            <input
              type="text"
              placeholder="e.g. Q3 Strategic Planning & Roadmap"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full h-8 px-3 bg-[#18191f] text-xs text-[#f3f4f6] placeholder-[#9ca3af] rounded-md border border-[#22242a] focus:outline-none focus:border-[#ff5c47]/50 transition-colors"
            />
          </div>

          {/* 4-Step Progress Tracker */}
          {loading && (
            <div className="p-3.5 rounded-lg bg-[#18191f] border border-[#22242a] space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-[#f3f4f6] flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 text-[#ff5c47] animate-spin" />
                  {processingStage === "uploading" && `Uploading (${uploadPercent}%)...`}
                  {processingStage === "extracting" && "Ingesting stream..."}
                  {processingStage === "transcribing" && "Transcribing speech..."}
                  {processingStage === "synthesizing" && "Synthesizing summary..."}
                </span>
                <span className="text-[11px] text-[#9ca3af] font-mono">
                  {elapsedSeconds}s
                </span>
              </div>

              <div className="grid grid-cols-4 gap-1 text-[10px] text-center font-medium">
                <div className={`py-1 rounded ${processingStage === "uploading" ? "bg-[#ff5c47]/20 text-[#ff5c47]" : "bg-[#22242a] text-[#10b981]"}`}>
                  1. Upload
                </div>
                <div className={`py-1 rounded ${processingStage === "extracting" ? "bg-[#ff5c47]/20 text-[#ff5c47]" : ["transcribing", "synthesizing"].includes(processingStage) ? "bg-[#22242a] text-[#10b981]" : "bg-[#22242a] text-[#9ca3af]"}`}>
                  2. Extract
                </div>
                <div className={`py-1 rounded ${processingStage === "transcribing" ? "bg-[#ff5c47]/20 text-[#ff5c47]" : processingStage === "synthesizing" ? "bg-[#22242a] text-[#10b981]" : "bg-[#22242a] text-[#9ca3af]"}`}>
                  3. Transcribe
                </div>
                <div className={`py-1 rounded ${processingStage === "synthesizing" ? "bg-[#ff5c47]/20 text-[#ff5c47]" : "bg-[#22242a] text-[#9ca3af]"}`}>
                  4. Synthesize
                </div>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="p-3 bg-[#ef4444]/10 border border-[#ef4444]/20 rounded-md text-xs text-[#ef4444] flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <div className="font-semibold">Upload Error</div>
                <div className="text-[11px] text-[#ef4444]/90">{error}</div>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              disabled={loading}
              onClick={onClose}
              className="h-8 px-3 rounded-md text-xs border-[#22242a] bg-[#18191f] text-[#9ca3af] hover:text-[#f3f4f6] hover:bg-[#22242a]"
            >
              Cancel
            </Button>
            <Button
              type="button"
              disabled={loading || !file || isQuotaExceeded}
              onClick={handleProcess}
              className="h-8 px-4 rounded-md text-xs bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-medium shadow-sm transition-colors"
            >
              {loading ? (
                <>
                  <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />
                  Processing...
                </>
              ) : isQuotaExceeded ? (
                "Quota Limit Reached"
              ) : (
                "Process Recording"
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
