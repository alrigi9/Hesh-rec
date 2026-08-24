"use client";

import React, { useState, useRef, useEffect } from "react";
import { 
  Upload, 
  FileAudio, 
  Sparkles, 
  Loader2, 
  AlertCircle,
  Mic,
  Square,
  Pause,
  Play,
  CheckCircle2,
  Layers
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

  const [activeMode, setActiveMode] = useState<"upload" | "record">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [template, setTemplate] = useState("executive");
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [processingStage, setProcessingStage] = useState<"uploading" | "transcribing" | "synthesizing">("uploading");
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Live Recording States
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const isQuotaExceeded = (profile?.minutes_used_this_month ?? 0) >= (profile?.monthly_minutes_limit ?? 300) && !isAdmin;

  // Cleanup on unmount or close
  useEffect(() => {
    if (!isOpen) {
      stopRecordingCleanup();
      setFile(null);
      setTitle("");
      setError(null);
      setLoading(false);
    }
  }, [isOpen]);

  const stopRecordingCleanup = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    setIsPaused(false);
    setRecordingDuration(0);
  };

  const handleStartRecording = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        const recordedFile = new File([audioBlob], `recording-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.webm`, {
          type: "audio/webm",
        });
        setFile(recordedFile);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(250);
      setIsRecording(true);
      setIsPaused(false);
      setRecordingDuration(0);

      timerRef.current = setInterval(() => {
        setRecordingDuration((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      setError(err.message || "Microphone access denied. Please grant permission to record.");
    }
  };

  const handlePauseResumeRecording = () => {
    if (!mediaRecorderRef.current) return;
    if (isPaused) {
      mediaRecorderRef.current.resume();
      setIsPaused(false);
      timerRef.current = setInterval(() => {
        setRecordingDuration((prev) => prev + 1);
      }, 1000);
    } else {
      mediaRecorderRef.current.pause();
      setIsPaused(true);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const handleStopRecording = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    setIsPaused(false);
  };

  const formatTimer = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hrs > 0) {
      return `${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    }
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

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
      setError("Please select or record an audio file.");
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
      // Refresh user's quota badge in real-time
      refreshProfile();
      onClose();
      // Reset state
      setFile(null);
      setTitle("");
    } catch (err: unknown) {
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      setLoading(false);
      const msg = err instanceof Error ? err.message : "Failed to process audio file.";
      setError(msg);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !loading && onClose()}>
      <DialogContent className="sm:max-w-[500px] bg-[#13151B] border border-white/[0.08] text-[#f0f2f5] p-6 rounded-2xl shadow-2xl">
        <DialogHeader className="space-y-1">
          <DialogTitle className="text-lg font-semibold tracking-tight text-[#f0f2f5] font-heading flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#ff5c47]" />
            Ingest Audio Intelligence
          </DialogTitle>
          <DialogDescription className="text-xs text-[#8b909a]">
            High-fidelity speech transcription with instant executive summaries, mind maps, and action items.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {/* Mode Switcher: Upload File vs Record Live */}
          <div className="grid grid-cols-2 p-1 rounded-xl bg-[#0c0d0e] border border-white/[0.08] text-xs">
            <button
              type="button"
              disabled={loading || isRecording}
              onClick={() => {
                setActiveMode("upload");
                setError(null);
              }}
              className={`py-1.5 rounded-lg font-medium transition-all flex items-center justify-center gap-1.5 ${
                activeMode === "upload"
                  ? "bg-[#ff5c47] text-white shadow-sm"
                  : "text-[#8b909a] hover:text-[#f0f2f5]"
              }`}
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Upload Audio</span>
            </button>
            <button
              type="button"
              disabled={loading || isRecording}
              onClick={() => {
                setActiveMode("record");
                setError(null);
              }}
              className={`py-1.5 rounded-lg font-medium transition-all flex items-center justify-center gap-1.5 ${
                activeMode === "record"
                  ? "bg-[#ff5c47] text-white shadow-sm"
                  : "text-[#8b909a] hover:text-[#f0f2f5]"
              }`}
            >
              <Mic className="w-3.5 h-3.5" />
              <span>Record Live</span>
            </button>
          </div>

          {/* Active Mode Body */}
          {activeMode === "upload" ? (
            /* Drag and Drop Zone */
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
                file
                  ? "border-[#ff5c47]/50 bg-[#ff5c47]/5"
                  : "border-white/10 hover:border-white/20 bg-[#18191c]"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".mp3,.wav,.m4a,.mp4,.aac,.ogg,.flac,.webm"
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
                    {(file.size / (1024 * 1024)).toFixed(2)} MB • Click to replace
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center text-[#8b909a]">
                    <Upload className="w-5 h-5" />
                  </div>
                  <div className="font-medium text-xs text-[#f0f2f5]">
                    Drop audio file here or click to browse
                  </div>
                  <div className="text-[11px] text-[#8b909a]">
                    MP3, M4A, WAV, WebM, AAC, FLAC (up to 50MB)
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Live Audio Recorder */
            <div className="border border-white/10 rounded-xl p-6 bg-[#18191c] text-center space-y-4">
              <div className="flex flex-col items-center gap-3">
                {isRecording ? (
                  <div className="relative">
                    <div className="w-14 h-14 rounded-full bg-[#ff5c47]/15 border border-[#ff5c47]/30 flex items-center justify-center text-[#ff5c47] animate-pulse">
                      <Mic className="w-6 h-6" />
                    </div>
                  </div>
                ) : file ? (
                  <div className="w-14 h-14 rounded-full bg-[#3ec98a]/10 border border-[#3ec98a]/20 flex items-center justify-center text-[#3ec98a]">
                    <CheckCircle2 className="w-6 h-6" />
                  </div>
                ) : (
                  <div className="w-14 h-14 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-[#8b909a]">
                    <Mic className="w-6 h-6" />
                  </div>
                )}

                {/* Timer Counter */}
                <div className="font-mono text-2xl font-bold text-[#f0f2f5] tracking-wider">
                  {formatTimer(recordingDuration)}
                </div>

                <p className="text-xs text-[#8b909a]">
                  {isRecording
                    ? isPaused
                      ? "Recording paused • Press resume to continue"
                      : "Recording live meeting audio..."
                    : file
                    ? `Captured audio ready (${(file.size / 1024).toFixed(1)} KB)`
                    : "Click start to begin capturing browser audio"}
                </p>
              </div>

              {/* Recorder Controls */}
              <div className="flex items-center justify-center gap-2 pt-1">
                {!isRecording ? (
                  <Button
                    type="button"
                    onClick={handleStartRecording}
                    className="h-10 px-6 rounded-full bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white text-xs font-semibold gap-2 shadow-lg shadow-[#ff5c47]/20"
                  >
                    <Mic className="w-4 h-4" />
                    <span>{file ? "Record Again" : "Start Recording"}</span>
                  </Button>
                ) : (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handlePauseResumeRecording}
                      className="h-10 px-4 rounded-full border-white/10 bg-white/5 text-xs text-[#f0f2f5] hover:bg-white/10 gap-1.5"
                    >
                      {isPaused ? <Play className="w-3.5 h-3.5 text-[#3ec98a]" /> : <Pause className="w-3.5 h-3.5 text-[#f9ab00]" />}
                      <span>{isPaused ? "Resume" : "Pause"}</span>
                    </Button>
                    <Button
                      type="button"
                      onClick={handleStopRecording}
                      className="h-10 px-5 rounded-full bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white text-xs font-semibold gap-1.5 shadow-sm"
                    >
                      <Square className="w-3.5 h-3.5 fill-current" />
                      <span>Finish Recording</span>
                    </Button>
                  </>
                )}
              </div>
            </div>
          )}

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

          {/* Processing Progress Indicator */}
          {loading && (
            <div className="p-3.5 rounded-xl bg-white/5 border border-white/10 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-[#f0f2f5] flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 text-[#ff5c47] animate-spin" />
                  {processingStage === "uploading" && "Uploading audio stream..."}
                  {processingStage === "transcribing" && "Transcribing voice to text..."}
                  {processingStage === "synthesizing" && "Synthesizing mind map & action items..."}
                </span>
                <span className="text-[11px] text-[#ff5c47] font-mono">
                  {processingStage === "uploading" && "Stage 1/3"}
                  {processingStage === "transcribing" && "Stage 2/3"}
                  {processingStage === "synthesizing" && "Stage 3/3"}
                </span>
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

          {/* Error feedback */}
          {error && (
            <div className="p-3 bg-[#eb5757]/10 border border-[#eb5757]/20 rounded-xl text-xs text-[#eb5757] flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              disabled={loading || isRecording}
              onClick={onClose}
              className="h-10 px-4 rounded-full text-xs border-white/10 bg-[#18191c] text-[#8b909a] hover:text-[#f0f2f5]"
            >
              Cancel
            </Button>
            <Button
              type="button"
              disabled={loading || !file || isQuotaExceeded || isRecording}
              onClick={handleProcess}
              className="h-10 px-6 rounded-full text-xs bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-semibold shadow-lg shadow-[#ff5c47]/25 transition-all"
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                  Extracting Intelligence...
                </>
              ) : isQuotaExceeded ? (
                "Quota Limit Reached"
              ) : (
                "Transcribe & Extract"
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
