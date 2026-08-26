"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Play, Pause, Volume2, VolumeX, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface AudioPlayerProps {
  src?: string | null;
  sessionId?: string;
  initialDuration?: number;
  currentTime?: number;
  onTimeUpdate?: (time: number) => void;
}

export function AudioPlayer({
  src,
  sessionId,
  initialDuration = 0,
  currentTime,
  onTimeUpdate,
}: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [duration, setDuration] = useState(initialDuration || 0);
  const [pos, setPos] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [playbackError, setPlaybackError] = useState<string | null>(null);

  // Cleanly reset player state whenever session or audio source changes
  useEffect(() => {
    setPos(0);
    setIsPlaying(false);
    setIsLoading(false);
    setPlaybackError(null);
    setDuration(initialDuration || 0);

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      if (src) {
        try {
          audioRef.current.load();
        } catch (e) {
          console.warn("[AudioPlayer] load() note:", e);
        }
      }
    }
  }, [src, sessionId, initialDuration]);

  // Seek time update from transcript or external trigger
  useEffect(() => {
    if (currentTime !== undefined && audioRef.current && isFinite(currentTime)) {
      audioRef.current.currentTime = currentTime;
      setPos(currentTime);
      if (!isPlaying) {
        audioRef.current.play().catch((err) => {
          console.warn("[AudioPlayer] play on seek note:", err);
        });
      }
    }
  }, [currentTime]);

  const togglePlay = async () => {
    if (!audioRef.current || !src) return;

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      try {
        setIsLoading(true);
        setPlaybackError(null);
        await audioRef.current.play();
        setIsPlaying(true);
      } catch (err: any) {
        console.error("[AudioPlayer] play() rejected:", err);
        setIsPlaying(false);
        if (err.name !== "AbortError") {
          setPlaybackError(err.message || "Failed to start playback. Audio stream might be unavailable.");
        }
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleTimeUpdate = () => {
    if (!audioRef.current) return;
    const current = audioRef.current.currentTime;
    if (isFinite(current)) {
      setPos(current);
      onTimeUpdate?.(current);
    }
  };

  const handleLoadedMetadata = useCallback(() => {
    if (!audioRef.current) return;
    const d = audioRef.current.duration;
    if (typeof d === "number" && isFinite(d) && d > 0) {
      setDuration(d);
    }
    setIsLoading(false);
    setPlaybackError(null);
  }, []);

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const targetTime = Number(e.target.value);
    if (audioRef.current && isFinite(targetTime)) {
      audioRef.current.currentTime = targetTime;
      setPos(targetTime);
    }
  };

  const handleMediaError = (e: React.SyntheticEvent<HTMLAudioElement, Event>) => {
    const target = e.currentTarget;
    const err = target.error;
    let detail = "Error loading media playback stream.";
    if (err) {
      switch (err.code) {
        case MediaError.MEDIA_ERR_ABORTED:
          detail = "Playback was aborted.";
          break;
        case MediaError.MEDIA_ERR_NETWORK:
          detail = "A network error caused audio download to fail.";
          break;
        case MediaError.MEDIA_ERR_DECODE:
          detail = "Audio playback failed due to a corruption or decoding issue.";
          break;
        case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
          detail = "Media format or private signed access URL is not supported by browser.";
          break;
      }
    }
    console.error("[AudioPlayer] Native Media Error:", err?.code, detail, "src:", src?.substring(0, 80));
    setPlaybackError(detail);
    setIsLoading(false);
    setIsPlaying(false);
  };

  const formatTime = (secs: number) => {
    if (!isFinite(secs) || isNaN(secs) || secs <= 0) return "00:00";
    const totalSecs = Math.floor(secs);
    const h = Math.floor(totalSecs / 3600);
    const m = Math.floor((totalSecs % 3600) / 60);
    const s = totalSecs % 60;
    if (h > 0) {
      return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    }
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  if (!src) return null;

  const effectiveDuration = duration > 0 ? duration : (initialDuration > 0 ? initialDuration : 0);

  return (
    <div className="fixed bottom-4 left-4 right-4 md:left-72 md:right-8 max-w-xl mx-auto z-40">
      <div className="bg-[#131418]/95 backdrop-blur-md border border-[#262830] rounded-lg p-2 px-3 shadow-lg flex flex-col gap-1 text-[#f3f4f6]">
        <div className="flex items-center gap-3">
          <audio
            ref={audioRef}
            src={src}
            preload="metadata"
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onLoadedData={handleLoadedMetadata}
            onDurationChange={handleLoadedMetadata}
            onCanPlay={() => {
              setIsLoading(false);
              setPlaybackError(null);
            }}
            onWaiting={() => setIsLoading(true)}
            onPlaying={() => {
              setIsLoading(false);
              setIsPlaying(true);
            }}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onEnded={() => {
              setIsPlaying(false);
              setPos(0);
            }}
            onError={handleMediaError}
          />

          {/* Play/Pause Button */}
          <Button
            size="icon"
            onClick={togglePlay}
            disabled={isLoading || Boolean(playbackError)}
            className="w-7 h-7 rounded-md bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white shrink-0 shadow-sm disabled:opacity-50"
          >
            {isLoading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : isPlaying ? (
              <Pause className="w-3.5 h-3.5" />
            ) : (
              <Play className="w-3.5 h-3.5 ml-0.5" />
            )}
          </Button>

          {/* Current Time */}
          <span className="text-[11px] font-mono text-[#9ca3af] shrink-0">
            {formatTime(pos)}
          </span>

          {/* Seek Bar Slider */}
          <input
            type="range"
            min={0}
            max={effectiveDuration > 0 ? effectiveDuration : 100}
            step={0.1}
            value={Math.min(pos, effectiveDuration > 0 ? effectiveDuration : 100)}
            onChange={handleSeek}
            className="flex-1 h-1 bg-[#22242a] rounded accent-[#ff5c47] cursor-pointer"
          />

          {/* Total Duration */}
          <span className="text-[11px] font-mono text-[#9ca3af] shrink-0">
            {formatTime(effectiveDuration)}
          </span>

          {/* Mute Button */}
          <Button
            size="icon"
            variant="ghost"
            onClick={() => {
              if (audioRef.current) {
                audioRef.current.muted = !isMuted;
                setIsMuted(!isMuted);
              }
            }}
            className="w-7 h-7 rounded-md text-[#9ca3af] hover:text-[#f3f4f6] hover:bg-[#18191f]"
          >
            {isMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
          </Button>
        </div>

        {/* Error notice if playback stream failed */}
        {playbackError && (
          <div className="flex items-center gap-1.5 text-[10px] text-[#ef4444] px-1">
            <AlertCircle className="w-3 h-3 shrink-0" />
            <span className="truncate">{playbackError}</span>
          </div>
        )}
      </div>
    </div>
  );
}
