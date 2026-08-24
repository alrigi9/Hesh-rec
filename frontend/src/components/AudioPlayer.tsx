"use client";

import React, { useState, useRef, useEffect } from "react";
import { Play, Pause, Volume2, VolumeX, RotateCcw, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface AudioPlayerProps {
  src?: string;
  currentTime?: number;
  onTimeUpdate?: (time: number) => void;
}

export function AudioPlayer({ src, currentTime, onTimeUpdate }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [pos, setPos] = useState(0);
  const [isMuted, setIsMuted] = useState(false);

  useEffect(() => {
    if (currentTime !== undefined && audioRef.current) {
      audioRef.current.currentTime = currentTime;
      if (!isPlaying) {
        audioRef.current.play().catch(() => {});
        setIsPlaying(true);
      }
    }
  }, [currentTime]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  };

  const handleTimeUpdate = () => {
    if (!audioRef.current) return;
    setPos(audioRef.current.currentTime);
    onTimeUpdate?.(audioRef.current.currentTime);
  };

  const handleLoadedMetadata = () => {
    if (!audioRef.current) return;
    setDuration(audioRef.current.duration);
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const targetTime = Number(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = targetTime;
      setPos(targetTime);
    }
  };

  const formatTime = (secs: number) => {
    if (isNaN(secs)) return "00:00";
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  if (!src) return null;

  return (
    <div className="sticky bottom-6 left-0 right-0 max-w-2xl mx-auto z-40 px-4">
      <div className="bg-[#141517]/95 backdrop-blur-xl border border-[#2e3238] rounded-full p-3 px-5 shadow-2xl flex items-center gap-4 text-[#f0f2f5]">
        <audio
          ref={audioRef}
          src={src}
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onEnded={() => setIsPlaying(false)}
        />

        {/* Play/Pause */}
        <Button
          size="icon"
          onClick={togglePlay}
          className="w-9 h-9 rounded-full bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white shrink-0 shadow-md"
        >
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
        </Button>

        {/* Current Time */}
        <span className="text-xs font-mono text-[#8b909a] shrink-0">
          {formatTime(pos)}
        </span>

        {/* Seek Bar */}
        <input
          type="range"
          min={0}
          max={duration || 100}
          value={pos}
          onChange={handleSeek}
          className="flex-1 h-1.5 bg-[#232529] rounded-full accent-[#ff5c47] cursor-pointer"
        />

        {/* Total Duration */}
        <span className="text-xs font-mono text-[#8b909a] shrink-0">
          {formatTime(duration)}
        </span>

        {/* Mute */}
        <Button
          size="icon"
          variant="ghost"
          onClick={() => {
            if (audioRef.current) {
              audioRef.current.muted = !isMuted;
              setIsMuted(!isMuted);
            }
          }}
          className="w-8 h-8 rounded-full text-[#8b909a] hover:text-[#f0f2f5]"
        >
          {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  );
}
