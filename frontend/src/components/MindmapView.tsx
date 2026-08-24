"use client";

import React, { useEffect, useRef, useCallback } from "react";
import { Markmap } from "markmap-view";
import { Transformer } from "markmap-lib";
import { ZoomIn, ZoomOut, Maximize2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MeetingSession } from "@/types/meeting";

interface MindmapViewProps {
  session: MeetingSession;
}

export function MindmapView({ session }: MindmapViewProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const mmRef = useRef<Markmap | null>(null);

  const buildMarkdown = useCallback((): string => {
    if (session.mindmap_markdown && session.mindmap_markdown.trim().startsWith("#")) {
      return session.mindmap_markdown;
    }
    const title = session.title || "Meeting Intelligence";
    const lines = [`# ${title}`];

    const sections = (session.discussion_pillars && session.discussion_pillars.length > 0)
      ? session.discussion_pillars
      : (session.sections || []);

    if (sections.length > 0) {
      sections.forEach((sec, idx) => {
        const n = sec.n || idx + 1;
        const t = (sec.title || `Topic ${n}`).replace(/^\d+\.\s*/, "");
        lines.push(`## ${n}. ${t}`);

        if (sec.narrative) {
          const cleanNarrative = sec.narrative.replace(/\n+/g, " ").trim();
          lines.push(`- ${cleanNarrative}`);
        }

        if (sec.decisions && sec.decisions.length > 0) {
          lines.push(`### Decisions`);
          sec.decisions.forEach((d) => lines.push(`- ${d}`));
        }

        if (sec.action_items && sec.action_items.length > 0) {
          lines.push(`### Action Items`);
          sec.action_items.forEach((a) => {
            const task = a.task || a.description || "Deliverable";
            const owner = a.owner || a.assignee || "Team";
            const due = a.due_date || a.due_text || "";
            const dueStr = due && due !== "—" ? ` (${due})` : "";
            lines.push(`- [ ] ${task} — *${owner}*${dueStr}`);
          });
        }
      });
    } else {
      const summaryText = session.executive_summary || session.summary || session.tldr || "";
      if (summaryText) {
        lines.push(`## Executive Summary`);
        lines.push(`- ${summaryText.substring(0, 160)}...`);
      }
      const actions = session.action_items || [];
      if (actions.length > 0) {
        lines.push(`## Action Items`);
        actions.forEach((a) => {
          lines.push(`- [ ] ${a.task || a.description} (${a.owner || "Team"})`);
        });
      }
    }

    return lines.join("\n");
  }, [session]);

  const fitMindmap = useCallback(() => {
    if (mmRef.current) {
      mmRef.current.fit();
    }
  }, []);

  useEffect(() => {
    if (!svgRef.current) return;

    try {
      const isMobile = typeof window !== "undefined" && window.innerWidth < 768;
      const transformer = new Transformer();
      const md = buildMarkdown();
      const { root } = transformer.transform(md);

      if (mmRef.current) {
        mmRef.current.setData(root);
        mmRef.current.fit();
      } else {
        mmRef.current = Markmap.create(
          svgRef.current,
          {
            autoFit: true,
            fitRatio: isMobile ? 0.9 : 0.95,
            maxWidth: isMobile ? 220 : 380,
            initialExpandLevel: isMobile ? 2 : 3,
            spacingVertical: isMobile ? 10 : 14,
            spacingHorizontal: isMobile ? 45 : 80,
            duration: 250,
          },
          root
        );
      }

      // Multi-stage auto-fit to account for layout animations and mobile viewport rendering
      const t1 = setTimeout(fitMindmap, 100);
      const t2 = setTimeout(fitMindmap, 350);
      const t3 = setTimeout(fitMindmap, 700);

      const handleResize = () => {
        fitMindmap();
      };
      window.addEventListener("resize", handleResize);

      return () => {
        clearTimeout(t1);
        clearTimeout(t2);
        clearTimeout(t3);
        window.removeEventListener("resize", handleResize);
      };
    } catch (e) {
      console.error("Markmap render error:", e);
    }
  }, [session, buildMarkdown, fitMindmap]);

  const handleFit = () => fitMindmap();
  const handleZoomIn = () => mmRef.current?.rescale(1.25);
  const handleZoomOut = () => mmRef.current?.rescale(0.8);

  return (
    <div className="relative w-full h-[520px] sm:h-[680px] bg-[#141517] border border-[#232529] rounded-2xl overflow-hidden shadow-sm touch-none">
      {/* Floating Controls Toolbar */}
      <div className="absolute top-3 right-3 sm:top-4 sm:right-4 z-10 flex items-center gap-1 sm:gap-1.5 bg-[#1c1e22]/90 backdrop-blur-md border border-[#2e3238] p-1 rounded-full shadow-lg">
        <Button
          size="sm"
          variant="ghost"
          onClick={handleFit}
          className="h-7 px-2.5 sm:px-3 text-xs text-[#8b909a] hover:text-[#f0f2f5] rounded-full gap-1"
        >
          <Maximize2 className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Fit View</span>
          <span className="sm:hidden">Fit</span>
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={handleZoomIn}
          className="w-7 h-7 text-[#8b909a] hover:text-[#f0f2f5] rounded-full"
          aria-label="Zoom in"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={handleZoomOut}
          className="w-7 h-7 text-[#8b909a] hover:text-[#f0f2f5] rounded-full"
          aria-label="Zoom out"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </Button>
      </div>

      {/* SVG Canvas */}
      <svg 
        ref={svgRef} 
        className="w-full h-full text-[#f0f2f5] cursor-grab active:cursor-grabbing select-none" 
      />
    </div>
  );
}
