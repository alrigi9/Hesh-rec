"use client";

import React, { useEffect, useRef } from "react";
import { Markmap } from "markmap-view";
import { Transformer } from "markmap-lib";
import { ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MeetingSession } from "@/types/meeting";

interface MindmapViewProps {
  session: MeetingSession;
}

export function MindmapView({ session }: MindmapViewProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const mmRef = useRef<Markmap | null>(null);

  const buildMarkdown = (): string => {
    const title = session.title || "Meeting Intelligence";
    const lines = [`# ${title}`];

    const sections = session.sections || [];
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

    return lines.join("\n");
  };

  useEffect(() => {
    if (!svgRef.current) return;

    try {
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
            fitRatio: 0.95,
            maxWidth: 380,
            initialExpandLevel: 3,
            spacingVertical: 12,
            spacingHorizontal: 80,
            duration: 250,
          },
          root
        );
      }

      const timer = setTimeout(() => {
        if (mmRef.current) mmRef.current.fit();
      }, 350);

      const handleResize = () => {
        if (mmRef.current) mmRef.current.fit();
      };
      window.addEventListener("resize", handleResize);

      return () => {
        clearTimeout(timer);
        window.removeEventListener("resize", handleResize);
      };
    } catch (e) {
      console.error("Markmap render error:", e);
    }
  }, [session]);

  const handleFit = () => mmRef.current?.fit();
  const handleZoomIn = () => mmRef.current?.rescale(1.25);
  const handleZoomOut = () => mmRef.current?.rescale(0.8);

  return (
    <div className="relative w-full h-[450px] sm:h-[680px] bg-[#141517] border border-[#232529] rounded-2xl overflow-hidden shadow-sm">
      <div className="absolute top-4 right-4 z-10 flex items-center gap-1.5 bg-[#1c1e22]/90 backdrop-blur-md border border-[#2e3238] p-1 rounded-full shadow-lg">
        <Button
          size="sm"
          variant="ghost"
          onClick={handleFit}
          className="h-7 px-3 text-xs text-[#8b909a] hover:text-[#f0f2f5] rounded-full"
        >
          <Maximize2 className="w-3.5 h-3.5 mr-1" />
          Fit
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={handleZoomIn}
          className="w-7 h-7 text-[#8b909a] hover:text-[#f0f2f5] rounded-full"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={handleZoomOut}
          className="w-7 h-7 text-[#8b909a] hover:text-[#f0f2f5] rounded-full"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </Button>
      </div>

      <svg ref={svgRef} className="w-full h-full text-[#f0f2f5]" />
    </div>
  );
}
