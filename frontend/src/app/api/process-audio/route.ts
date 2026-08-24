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

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get("file") as File | null;
    const templateType = (formData.get("template_type") as string) || "executive";
    const customTitle = formData.get("custom_title") as string | null;
    const userId = formData.get("user_id") as string | null;

    if (!file) {
      return NextResponse.json({ detail: "No audio or video file uploaded" }, { status: 400 });
    }

    // Check user quota in Supabase
    let userLimit = 300.0;
    let userUsed = 0.0;
    let userRole = "user";

    if (userId) {
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

    // 1. Send file to Groq Whisper for transcription
    const groqFormData = new FormData();
    groqFormData.append("file", file, file.name);
    groqFormData.append("model", "whisper-large-v3");
    groqFormData.append("response_format", "verbose_json");
    groqFormData.append("temperature", "0");

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
    const fullTranscript = (groqData.text || "").trim();
    const durationSeconds = Number(groqData.duration || 0.0);
    const durationMinutes = Math.max(1, Math.round(durationSeconds / 60));

    // Format transcript segments
    const rawSegments = groqData.segments || [];
    const formattedSegments = rawSegments.map((seg: any, idx: number) => ({
      index: idx + 1,
      start: Number(seg.start || 0.0),
      end: Number(seg.end || 0.0),
      timestamp: formatSecondsToHhmmss(Number(seg.start || 0.0)),
      speaker: `Speaker ${(idx % 3) + 1}`,
      text: (seg.text || "").trim(),
    }));

    // If segments empty, create a single segment
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

    // 2. Synthesize Meeting Intelligence using Gemini
    const meetingDate = new Date().toISOString().split("T")[0];
    const systemPrompt = `You are an expert executive meeting intelligence analyst.
Analyze the provided transcript and produce a rich, highly specific JSON response following this EXACT schema. Return ONLY valid JSON:

{
  "title": "Clear, informative meeting title",
  "meeting_date": "${meetingDate}",
  "duration_minutes": ${durationMinutes},
  "participants": ["Speaker 1", "Speaker 2"],
  "tags": ["Strategy", "Roadmap", "Execution"],
  "tldr": "3-4 concise executive sentences highlighting the main decisions and objectives.",
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

    let intelligenceData: any = {};
    try {
      const geminiRes = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${GEMINI_API_KEY}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(geminiPayload),
        }
      );

      if (geminiRes.ok) {
        const geminiJson = await geminiRes.json();
        const rawContent =
          geminiJson.candidates?.[0]?.content?.parts?.[0]?.text || "{}";
        intelligenceData = JSON.parse(rawContent);
      }
    } catch (err) {
      console.error("Gemini intelligence extraction error:", err);
    }

    const sessionId = `session_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const finalTitle = customTitle || intelligenceData.title || file.name.replace(/\.[^/.]+$/, "");

    const fullSessionPayload = {
      id: sessionId,
      title: finalTitle,
      meeting_date: intelligenceData.meeting_date || meetingDate,
      duration_minutes: durationMinutes,
      duration: `${durationMinutes}m`,
      tags: intelligenceData.tags || ["Intelligence", "Meeting"],
      participants: intelligenceData.participants || ["Participants"],
      summary: intelligenceData.tldr || "Meeting transcript captured and analyzed.",
      sections: intelligenceData.sections || [],
      action_items: intelligenceData.action_items || [],
      open_questions: intelligenceData.open_questions || [],
      strategic_insights: intelligenceData.strategic_insights || [],
      mindmap_markdown: intelligenceData.mindmap_markdown || `# ${finalTitle}\n## Key Points\n- Ingested`,
      transcript_segments: formattedSegments,
      raw_markdown: `# ${finalTitle}\n\n${intelligenceData.tldr || ""}`,
      metadata: {
        session_id: sessionId,
        audio_filename: file.name,
        file_size_bytes: file.size,
        duration: `${durationMinutes}m`,
      },
      user_id: userId || null,
      created_at: new Date().toISOString(),
    };

    // 3. Save to Supabase meeting_sessions table
    try {
      await fetch(`${SUPABASE_URL}/rest/v1/meeting_sessions`, {
        method: "POST",
        headers: {
          apikey: SUPABASE_SERVICE_ROLE_KEY,
          Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
          "Content-Type": "application/json",
          Prefer: "return=representation",
        },
        body: JSON.stringify({
          id: sessionId,
          user_id: userId || null,
          title: finalTitle,
          duration_minutes: durationMinutes,
          meeting_date: intelligenceData.meeting_date || meetingDate,
          tags: intelligenceData.tags || [],
          session_data: fullSessionPayload,
        }),
      });

      // Update user usage quota
      if (userId) {
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

    return NextResponse.json(fullSessionPayload);
  } catch (err: any) {
    console.error("Audio processing pipeline failed:", err);
    return NextResponse.json(
      { detail: err.message || "Failed to process audio file" },
      { status: 500 }
    );
  }
}
