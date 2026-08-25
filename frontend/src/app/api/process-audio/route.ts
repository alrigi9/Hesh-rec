import { NextRequest, NextResponse } from "next/server";
import { 
  GROQ_API_KEY, 
  GEMINI_API_KEY, 
  SUPABASE_URL, 
  SUPABASE_SERVICE_ROLE_KEY 
} from "@/lib/server-config";

export const maxDuration = 60; // 60s serverless timeout

function formatSecondsToHhmmss(seconds: number): string {
  const s = Math.floor(seconds);
  const hours = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  if (hours > 0) {
    return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

function cleanAndParseJson(text: string): Record<string, any> {
  if (!text) return {};
  let cleaned = text.trim();
  // Strip code block backticks
  if (cleaned.startsWith("```")) {
    cleaned = cleaned.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "");
  }
  // Extract outermost JSON block if any extra text exists
  const firstBrace = cleaned.indexOf("{");
  const lastBrace = cleaned.lastIndexOf("}");
  if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
    cleaned = cleaned.substring(firstBrace, lastBrace + 1);
  }
  try {
    return JSON.parse(cleaned);
  } catch (err) {
    console.error("JSON parsing error on text:", cleaned.substring(0, 200), err);
    return {};
  }
}

export async function POST(request: NextRequest) {
  try {
    let file: File | null = null;
    let fileUrl: string | null = null;
    let templateType = "executive";
    let language = "auto";
    let customTitle: string | null = null;
    let userId: string | null = null;
    let preTranscript: string | null = null;
    let preSegmentsJson: string | null = null;
    let preDurationSeconds = 0.0;
    let originalFilename = "meeting_audio.m4a";

    const contentType = request.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
      const jsonBody = await request.json();
      fileUrl = jsonBody.file_url || jsonBody.url || null;
      preTranscript = jsonBody.transcript || jsonBody.transcript_text || jsonBody.text || "";
      templateType = jsonBody.template || jsonBody.template_type || "executive";
      language = jsonBody.language || "auto";
      customTitle = jsonBody.custom_title || jsonBody.title || null;
      userId = jsonBody.user_id || null;
      if (jsonBody.transcript_segments) {
        if (typeof jsonBody.transcript_segments === "string") {
          preSegmentsJson = jsonBody.transcript_segments;
        } else {
          preSegmentsJson = JSON.stringify(jsonBody.transcript_segments);
        }
      }
      preDurationSeconds = Number(jsonBody.duration_seconds || jsonBody.duration || 0.0);
      originalFilename = jsonBody.filename || "meeting_audio.m4a";
    } else {
      const formData = await request.formData();
      file = formData.get("file") as File | null;
      fileUrl = (formData.get("file_url") as string) || null;
      templateType = (formData.get("template_type") as string) || (formData.get("template") as string) || "executive";
      language = (formData.get("language") as string) || "auto";
      customTitle = (formData.get("custom_title") as string) || (formData.get("title") as string) || null;
      userId = (formData.get("user_id") as string) || null;
      preTranscript = (formData.get("transcript_text") as string) || (formData.get("transcript") as string) || null;
      preSegmentsJson = (formData.get("transcript_segments") as string) || null;
      preDurationSeconds = Number(formData.get("duration_seconds") || 0.0);
      originalFilename = (formData.get("filename") as string) || (file ? file.name : "meeting_audio.m4a");
    }

    if (!file && !preTranscript && !fileUrl) {
      return NextResponse.json({ detail: "No audio file, storage URL, or transcript provided." }, { status: 400 });
    }

    // Check user quota in Supabase
    let userLimit = 300.0;
    let userUsed = 0.0;
    let userRole = "user";

    if (userId && userId !== "guest") {
      try {
        const profileRes = await fetch(
          `${SUPABASE_URL}/rest/v1/profiles?id=eq.${encodeURIComponent(userId)}&select=*`,
          {
            headers: {
              apikey: SUPABASE_SERVICE_ROLE_KEY,
              Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
            },
          }
        );
        if (profileRes.ok) {
          const profiles = await profileRes.json();
          if (Array.isArray(profiles) && profiles.length > 0) {
            userLimit = Number(profiles[0].monthly_minutes_limit ?? 300.0);
            userUsed = Number(profiles[0].minutes_used_this_month ?? 0.0);
            userRole = profiles[0].role || "user";
          }
        }
      } catch (err) {
        console.error("Profile check error:", err);
      }
    }

    if (userRole !== "admin" && userUsed >= userLimit) {
      return NextResponse.json(
        { detail: `Monthly quota limit of ${userLimit} minutes has been reached.` },
        { status: 403 }
      );
    }

    let fullTranscript = (preTranscript || "").trim();
    let durationSeconds = preDurationSeconds;
    let formattedSegments: any[] = [];

    if (preSegmentsJson) {
      try {
        formattedSegments = JSON.parse(preSegmentsJson);
      } catch {
        formattedSegments = [];
      }
    }

    // 1. If not pre-transcribed, transcribe audio from File or Storage URL via Groq Whisper LPU
    if (!fullTranscript && (file || fileUrl)) {
      let audioBlob: Blob | File | null = file;
      if (!audioBlob && fileUrl) {
        const audioRes = await fetch(fileUrl);
        if (!audioRes.ok) {
          return NextResponse.json(
            { detail: `Failed to download audio from storage URL: ${fileUrl}` },
            { status: 400 }
          );
        }
        audioBlob = await audioRes.blob();
      }

      if (audioBlob) {
        let safeName = originalFilename || "recording.m4a";
        if (!safeName.includes(".")) safeName += ".m4a";

        const groqFormData = new FormData();
        groqFormData.append("file", audioBlob, safeName);
        groqFormData.append("model", "whisper-large-v3");
        groqFormData.append("response_format", "verbose_json");
        groqFormData.append("temperature", "0");
        if (language === "ar") {
          groqFormData.append("language", "ar");
        } else if (language === "en") {
          groqFormData.append("language", "en");
        }

        const groqRes = await fetch("https://api.groq.com/openai/v1/audio/transcriptions", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${GROQ_API_KEY}`,
          },
          body: groqFormData,
        });

        if (!groqRes.ok) {
          const errText = await groqRes.text();
          return NextResponse.json(
            { detail: `Transcription failed: ${errText}` },
            { status: 500 }
          );
        }

        const groqData = await groqRes.json();
        fullTranscript = (groqData.text || "").trim();
        durationSeconds = Number(groqData.duration || 0.0);

        const rawSegments = groqData.segments || [];
        formattedSegments = rawSegments.map((seg: any, idx: number) => ({
          index: idx + 1,
          start: Number(seg.start || 0.0),
          end: Number(seg.end || 0.0),
          timestamp: formatSecondsToHhmmss(Number(seg.start || 0.0)),
          speaker: `Speaker ${(idx % 3) + 1}`,
          text: (seg.text || "").trim(),
        }));
      }
    }

    const durationMinutes = Math.max(1, Math.round(durationSeconds / 60));

    if (formattedSegments.length === 0 && fullTranscript) {
      formattedSegments.push({
        index: 1,
        start: 0.0,
        end: durationSeconds,
        timestamp: "00:00",
        speaker: "Speaker 1",
        text: fullTranscript,
      });
    }

    // 2. Synthesize Meeting Intelligence using Gemini (gemini-3.6-flash with Groq Fallback)
    const meetingDate = new Date().toISOString().split("T")[0];
    let langInstruction = "Detect the primary language of the transcript and produce the entire JSON output in that language with an authoritative executive business tone.";
    if (language === "ar") {
      langInstruction = "Produce the entire JSON output strictly in formal executive business Arabic (اللغة العربية الفصحى المهنية). Translate, structure, and synthesize all titles, summaries, sections, and action items in clean Arabic while preserving technical acronyms.";
    } else if (language === "en") {
      langInstruction = "Produce the entire JSON output strictly in professional, authoritative executive English.";
    }

    const systemPrompt = `You are an expert executive meeting intelligence analyst.
Analyze the provided transcript and produce a rich, highly specific JSON response following this EXACT schema. Return ONLY valid JSON:

LANGUAGE DIRECTIVE: ${langInstruction}

{
  "title": "Clear, informative meeting title",
  "meeting_date": "${meetingDate}",
  "duration_minutes": ${durationMinutes},
  "participants": ["Speaker 1", "Speaker 2"],
  "tags": ["Strategy", "Roadmap", "Execution"],
  "summary": "3-4 concise executive sentences highlighting the main decisions, roadmap, and objectives.",
  "tldr": "3-4 concise executive sentences highlighting the main decisions, roadmap, and objectives.",
  "sections": [
    {
      "n": 1,
      "title": "Topic or Discussion Area Title",
      "narrative": "Comprehensive 3-5 sentence paragraph detailing discussion points, technical trade-offs, and agreed roadmap.",
      "decisions": ["Key team decision reached"],
      "action_items": [
        {
          "id": "A1",
          "task": "Concrete actionable deliverable",
          "owner": "Team",
          "priority": "HIGH",
          "due_date": "${meetingDate}"
        }
      ]
    }
  ],
  "action_items": [
    {
      "id": "A1",
      "task": "Specific actionable deliverable with clear requirements",
      "owner": "Team",
      "priority": "HIGH",
      "status": "pending",
      "due_date": "${meetingDate}"
    }
  ],
  "open_questions": ["Key unresolved question or dependency"],
  "strategic_insights": [
    {
      "title": "Strategic Recommendation",
      "detail": "Actionable insight to mitigate risk and accelerate delivery."
    }
  ],
  "mindmap_markdown": "# Meeting Overview\\n## Key Decisions\\n- Action Plan\\n## Next Steps\\n- Deliverables"
}`;

    let intelligenceData: any = {};

    // 1. Try Gemini 3.6 Flash
    try {
      const geminiPayload = {
        contents: [
          {
            parts: [
              { text: systemPrompt },
              { text: `Meeting Transcript:\n${fullTranscript || "No audible speech detected."}` },
            ],
          },
        ],
        generationConfig: {
          responseMimeType: "application/json",
          temperature: 0.2,
        },
      };

      const geminiRes = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key=${GEMINI_API_KEY}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(geminiPayload),
        }
      );

      if (geminiRes.ok) {
        const geminiJson = await geminiRes.json();
        const rawContent = geminiJson.candidates?.[0]?.content?.parts?.[0]?.text || "";
        intelligenceData = cleanAndParseJson(rawContent);
      }
    } catch (err) {
      console.warn("Gemini 3.6 Flash extraction note:", err);
    }

    // 2. Fallback to Groq LLM (openai/gpt-oss-120b or qwen/qwen3.6-27b) if Gemini returned empty
    if (!intelligenceData.title && !intelligenceData.summary && !intelligenceData.tldr && GROQ_API_KEY) {
      try {
        const groqChatRes = await fetch("https://api.groq.com/openai/v1/chat/completions", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${GROQ_API_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            model: "openai/gpt-oss-120b",
            messages: [
              { role: "system", content: systemPrompt },
              { role: "user", content: `Meeting Transcript:\n${fullTranscript || "No audible speech detected."}` },
            ],
            response_format: { type: "json_object" },
            temperature: 0.2,
          }),
        });

        if (groqChatRes.ok) {
          const groqChatJson = await groqChatRes.json();
          const rawContent = groqChatJson.choices?.[0]?.message?.content || "";
          intelligenceData = cleanAndParseJson(rawContent);
        }
      } catch (groqErr) {
        console.warn("Groq LLM fallback note:", groqErr);
      }
    }

    const sessionId = typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `00000000-0000-4000-8000-${Date.now().toString(16).padStart(12, "0")}`;
    const finalTitle = customTitle || intelligenceData.title || originalFilename.replace(/\.[^/.]+$/, "");
    const finalSummary = intelligenceData.summary || intelligenceData.tldr || intelligenceData.executive_summary || "Executive brief generated from captured transcript.";
    const finalSections = intelligenceData.sections || intelligenceData.discussion_pillars || [];
    let finalActions = intelligenceData.action_items || [];

    if (finalActions.length === 0) {
      finalActions = [
        {
          id: "A1",
          task: "Review and follow up on strategic action points from session",
          owner: "Team",
          priority: "MEDIUM",
          status: "pending",
          due_date: meetingDate,
        },
      ];
    }

    // Ensure mindmap_markdown exists with valid hierarchy
    let finalMindmap = intelligenceData.mindmap_markdown;
    if (!finalMindmap || !finalMindmap.startsWith("#")) {
      const mmLines = [`# ${finalTitle}`];
      if (finalSections.length > 0) {
        finalSections.forEach((s: any, idx: number) => {
          mmLines.push(`## ${s.n || idx + 1}. ${s.title || "Topic"}`);
          if (s.narrative) mmLines.push(`- ${s.narrative.substring(0, 80)}...`);
        });
      } else {
        mmLines.push(`## Overview`);
        mmLines.push(`- ${finalSummary.substring(0, 80)}...`);
      }
      if (finalActions.length > 0) {
        mmLines.push(`## Action Items`);
        finalActions.forEach((a: any) => {
          mmLines.push(`- ${a.task || a.description || "Deliverable"} (${a.owner || "Team"})`);
        });
      }
      finalMindmap = mmLines.join("\n");
    }

    const metadataObj = {
      user_id: userId || null,
      duration_minutes: durationMinutes,
      meeting_date: intelligenceData.meeting_date || meetingDate,
      tags: intelligenceData.tags || ["Intelligence", "Strategy"],
      participants: intelligenceData.participants || ["Speaker 1"],
      open_questions: intelligenceData.open_questions || [],
      audio_filename: originalFilename,
      file_size_bytes: file ? file.size : 0,
      tldr: finalSummary,
      insights: intelligenceData.strategic_insights || [],
    };

    const fullSessionPayload = {
      id: sessionId,
      title: finalTitle,
      meeting_date: intelligenceData.meeting_date || meetingDate,
      date: intelligenceData.meeting_date || meetingDate,
      duration_minutes: durationMinutes,
      duration: `${durationMinutes}m`,
      tags: intelligenceData.tags || ["Intelligence", "Strategy"],
      participants: intelligenceData.participants || ["Speaker 1"],
      tldr: finalSummary,
      summary: finalSummary,
      executive_summary: finalSummary,
      sections: finalSections,
      discussion_pillars: finalSections,
      action_items: finalActions,
      open_questions: intelligenceData.open_questions || [],
      strategic_insights: intelligenceData.strategic_insights || [],
      mindmap_markdown: finalMindmap,
      transcript_segments: formattedSegments,
      transcript: fullTranscript,
      full_transcript_text: fullTranscript,
      raw_markdown: `# ${finalTitle}\n\n${finalSummary}`,
      metadata: {
        session_id: sessionId,
        audio_filename: originalFilename,
        file_size_bytes: file ? file.size : 0,
        duration: `${durationMinutes}m`,
      },
      user_id: userId || null,
      created_at: new Date().toISOString(),
    };

    // 3. Save to Supabase sessions table
    if (SUPABASE_URL && SUPABASE_SERVICE_ROLE_KEY) {
      try {
        const dbPayload = {
          id: sessionId,
          title: finalTitle,
          summary: finalSummary,
          executive_summary: finalSummary,
          discussion_pillars: finalSections,
          action_items: finalActions,
          strategic_insights: metadataObj,
          mindmap_markdown: finalMindmap,
          transcript: fullTranscript,
          transcript_segments: formattedSegments,
          is_public: false,
        };

        const dbRes = await fetch(`${SUPABASE_URL}/rest/v1/sessions`, {
          method: "POST",
          headers: {
            apikey: SUPABASE_SERVICE_ROLE_KEY,
            Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
            "Content-Type": "application/json",
            Prefer: "return=representation",
          },
          body: JSON.stringify(dbPayload),
        });
        const dbResText = await dbRes.text();
        console.log("Supabase insert session response:", dbRes.status, dbResText.substring(0, 150));

        // Update user usage quota
        if (userId && userId !== "guest") {
          const newUsed = userUsed + durationMinutes;
          await fetch(`${SUPABASE_URL}/rest/v1/profiles?id=eq.${encodeURIComponent(userId)}`, {
            method: "PATCH",
            headers: {
              apikey: SUPABASE_SERVICE_ROLE_KEY,
              Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              minutes_used_this_month: newUsed,
            }),
          });
        }
      } catch (err) {
        console.error("Failed to persist session to Supabase:", err);
      }
    }

    return NextResponse.json(fullSessionPayload);
  } catch (err: any) {
    console.error("Audio processing pipeline failed:", err);
    return NextResponse.json(
      { detail: err.message || "Failed to process audio file" },
      { status: 500 }
    );
  }
}
