import { NextRequest, NextResponse } from "next/server";
import { 
  GROQ_API_KEY, 
  GEMINI_API_KEY, 
  SUPABASE_URL, 
  SUPABASE_SERVICE_ROLE_KEY 
} from "@/lib/server-config";
import { callWithRetry } from "@/lib/groqRetry";
import { getAuthenticatedUser } from "@/lib/serverAuth";
import { normalizeTemplate, TEMPLATES_CONFIG } from "@/lib/templates";

export const maxDuration = 60; // 60s timeout (Compatible with Vercel Hobby & Pro; Groq LPU finishes in <15s)

export const dynamic = "force-dynamic";

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
  if (cleaned.startsWith("```")) {
    cleaned = cleaned.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "");
  }
  const firstBrace = cleaned.indexOf("{");
  const lastBrace = cleaned.lastIndexOf("}");
  if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
    cleaned = cleaned.substring(firstBrace, lastBrace + 1);
  }
  try {
    return JSON.parse(cleaned);
  } catch (err) {
    console.error("[Worker] JSON parsing error on text:", cleaned.substring(0, 200), err);
    return {};
  }
}

export async function POST(request: NextRequest) {
  let sessionId: string | null = null;
  let userId: string | null = null;

  try {
    // 0. Strict Server-Side Authentication & Session Ownership Guard
    const authUser = await getAuthenticatedUser(request);
    if (!authUser || !authUser.id) {
      return NextResponse.json(
        { error: "Unauthorized: Authentication required to process meeting audio." },
        { status: 401 }
      );
    }

    const body = await request.json();
    sessionId = body.session_id || body.id || null;

    if (!sessionId) {
      return NextResponse.json({ error: "Missing session_id in worker request" }, { status: 400 });
    }

    let dbAudioUrl: string | null = null;
    let sessionRow: any = null;

    // Verify session ownership and status in database
    if (SUPABASE_URL && SUPABASE_SERVICE_ROLE_KEY) {
      const sessionCheck = await fetch(
        `${SUPABASE_URL}/rest/v1/sessions?id=eq.${encodeURIComponent(sessionId)}&select=user_id,status,strategic_insights`,
        {
          headers: {
            apikey: SUPABASE_SERVICE_ROLE_KEY,
            Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
          },
        }
      );
      if (sessionCheck.ok) {
        const sRows = await sessionCheck.json();
        if (Array.isArray(sRows) && sRows.length > 0) {
          sessionRow = sRows[0];
          const ownerId = sessionRow.user_id || sessionRow.strategic_insights?.user_id;
          dbAudioUrl = sessionRow.strategic_insights?.audio_url || null;


          if (ownerId && ownerId !== authUser.id && authUser.role !== "admin") {
            return NextResponse.json(
              { error: "Forbidden: You cannot process a session belonging to another user." },
              { status: 403 }
            );
          }

          // If session is already completed, return safely without reprocessing
          if (sessionRow.status === "completed") {
            console.log(`[Worker] Session ${sessionId} is already completed. Skipping processing.`);
            return NextResponse.json({
              ok: true,
              status: "completed",
              session_id: sessionId,
              message: "Session is already completed.",
            });
          }
        }
      }

      // ------------------------------------------------------------------------
      // Step 0.5: Atomic Processing Claim & Concurrency Guard (CAS Lock)
      // ------------------------------------------------------------------------
      const nowIso = new Date().toISOString();
      const staleIso = new Date(Date.now() - 180000).toISOString(); // 180s stale threshold

      // Atomically claim the session:
      // Condition: status != 'completed' AND (processing_started_at IS NULL OR status = 'failed' OR processing_started_at < staleIso)
      const claimRes = await fetch(
        `${SUPABASE_URL}/rest/v1/sessions?id=eq.${encodeURIComponent(sessionId)}&status=neq.completed&or=(processing_started_at.is.null,status.eq.failed,processing_started_at.lt.${encodeURIComponent(staleIso)})`,
        {
          method: "PATCH",
          headers: {
            apikey: SUPABASE_SERVICE_ROLE_KEY,
            Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
            "Content-Type": "application/json",
            Prefer: "return=representation",
          },
          body: JSON.stringify({
            status: "processing",
            processing_started_at: nowIso,
            error_message: null,
          }),
        }
      );

      if (!claimRes.ok) {
        const claimErr = await claimRes.text();
        console.error(`[Worker] Atomic claim error for session ${sessionId}:`, claimRes.status, claimErr);
        return NextResponse.json({ error: "Failed to establish processing lock" }, { status: 500 });
      }

      const claimedRows = await claimRes.json();
      if (!Array.isArray(claimedRows) || claimedRows.length === 0) {
        console.log(`[Worker] Duplicate active processing invocation ignored for session: ${sessionId}`);
        return NextResponse.json({
          ok: true,
          status: "already_processing",
          session_id: sessionId,
          message: "Session is already being actively processed by another worker.",
        });
      }

      console.log(`[Worker] Processing claim acquired atomically for session: ${sessionId}`);
    }

    userId = authUser.id;
    let trustedStoragePath: string | null = sessionRow?.strategic_insights?.storage_path || body.storage_path || null;
    const legacyUrl = body.file_url || body.audioUrl || body.audio_url || sessionRow?.strategic_insights?.audio_url || null;

    // Resolve legacy URLs to storage_path if needed
    if (!trustedStoragePath && legacyUrl) {
      const match = legacyUrl.match(/\/storage\/v1\/object\/(?:public|authenticated|sign)\/recordings\/(.+)$/);
      if (match && match[1]) {
        trustedStoragePath = decodeURIComponent(match[1]);
      }
    }

    // Strict path validation and ownership guard
    if (trustedStoragePath) {
      if (trustedStoragePath.includes("..") || trustedStoragePath.includes("\\")) {
        throw new Error("Invalid storage path: Path traversal detected.");
      }
      const pathUserId = trustedStoragePath.split("/")[0];
      const sessionOwnerId = sessionRow?.user_id || sessionRow?.strategic_insights?.user_id || userId;
      if (sessionOwnerId && pathUserId && pathUserId !== sessionOwnerId && authUser.role !== "admin") {
        return NextResponse.json(
          { error: "Forbidden: Storage path belongs to another user." },
          { status: 403 }
        );
      }
    }

    let preTranscript = body.pre_transcript || body.transcript || "";
    let preSegmentsJson = body.pre_segments_json || body.transcript_segments || null;
    let preDurationSeconds = Number(body.duration_seconds || body.duration || 0.0);
    const rawTemplate = body.template || body.template_type || sessionRow?.strategic_insights?.template_type || sessionRow?.strategic_insights?.template || "auto";
    const templateType = normalizeTemplate(rawTemplate);
    const templateConfig = TEMPLATES_CONFIG[templateType] || TEMPLATES_CONFIG.auto;
    const language = body.language || "auto";
    const customTitle = body.title || body.custom_title || null;
    const originalFilename = body.filename || "meeting_audio.m4a";

    console.log(`[Worker] Starting background processing for session: ${sessionId} (template: ${templateType}, file: ${originalFilename}, storage_path: ${trustedStoragePath || "none"})`);


    let fullTranscript = (preTranscript || "").trim();
    let durationSeconds = preDurationSeconds;
    let formattedSegments: any[] = [];

    if (preSegmentsJson) {
      try {
        formattedSegments = typeof preSegmentsJson === "string" ? JSON.parse(preSegmentsJson) : preSegmentsJson;
      } catch {
        formattedSegments = [];
      }
    }

    // ------------------------------------------------------------------------
    // Step 1: Transcribe via Groq Whisper with Private Authenticated Storage Access
    // ------------------------------------------------------------------------
    if (!fullTranscript && trustedStoragePath) {
      console.log(`[Worker] Downloading private audio stream from storage: ${trustedStoragePath}`);
      
      const audioRes = await fetch(
        `${SUPABASE_URL}/storage/v1/object/authenticated/recordings/${encodeURIComponent(trustedStoragePath)}`,
        {
          headers: {
            Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
            apikey: SUPABASE_SERVICE_ROLE_KEY,
          },
        }
      );

      if (!audioRes.ok) {
        throw new Error(`Failed to download media from private storage: ${trustedStoragePath} (status: ${audioRes.status})`);
      }
      const audioBlob = await audioRes.blob();

      if (audioBlob.size > 25 * 1024 * 1024) {
        throw new Error(`Media file size (${(audioBlob.size / (1024 * 1024)).toFixed(1)} MB) exceeds the 25 MB transcription provider limit. Please upload a compressed audio/video file under 25 MB.`);
      }

      let safeName = originalFilename || "recording.m4a";
      if (!safeName.includes(".")) safeName += ".m4a";

      // Groq Whisper accepts: [flac, mp3, mp4, mpeg, mpga, m4a, ogg, opus, wav, webm]
      // QuickTime MOV (.mov, .qt) and M4V (.m4v) containers share the exact ISO-BMFF structure with MP4.
      // Mapping the extension to .mp4 allows Groq Whisper's internal demuxer to decode the audio track natively.
      let groqFilename = safeName;
      if (/\.(mov|qt|m4v)$/i.test(groqFilename)) {
        groqFilename = groqFilename.replace(/\.(mov|qt|m4v)$/i, ".mp4");
      }

      const groqData = await callWithRetry(async () => {
        const groqFormData = new FormData();
        groqFormData.append("file", audioBlob, groqFilename);
        groqFormData.append("model", "whisper-large-v3-turbo");
        groqFormData.append("response_format", "verbose_json");
        groqFormData.append("temperature", "0");

        if (language === "ar") {
          groqFormData.append("language", "ar");
        } else if (language === "en") {
          groqFormData.append("language", "en");
        }

        const res = await fetch("https://api.groq.com/openai/v1/audio/transcriptions", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${GROQ_API_KEY}`,
          },
          body: groqFormData,
        });

        if (!res.ok) {
          const errText = await res.text();
          const err: any = new Error(`Groq Whisper transcription failed: ${errText}`);
          err.status = res.status;
          throw err;
        }

        return await res.json();
      }, 3, 2500);

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

    if (!fullTranscript) {
      throw new Error("No audible speech or transcript could be extracted from the audio file.");
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

    // ------------------------------------------------------------------------
    // Step 2: Extract Intelligence & Mindmap with Gemini / Groq LLaMA 3.3
    // ------------------------------------------------------------------------
    const meetingDate = new Date().toISOString().split("T")[0];
    let langInstruction = "Detect the primary language of the transcript and produce the entire JSON output in that language with an authoritative executive tone.";
    if (language === "ar") {
      langInstruction = "Produce the entire JSON output strictly in formal executive business Arabic (اللغة العربية الفصحى المهنية). Translate, structure, and synthesize all titles, summaries, sections, and action items in clean Arabic while preserving technical acronyms.";
    } else if (language === "en") {
      langInstruction = "Produce the entire JSON output strictly in professional, authoritative executive English.";
    }

    const systemPrompt = `You are an expert executive meeting intelligence analyst.
Your primary directive is STRICT FACTUAL GROUNDING in the provided transcript.

### 🛡️ STRICT GROUNDING & ANTI-HALLUCINATION RULES:
1. ONLY USE EXPLICIT FACTS: Base all output strictly on facts, statements, and topics explicitly voiced in the transcript.
2. NEVER INVENT OR EXTRAPOLATE:
   - Do NOT invent participants, names, roles, job titles, or facilitators (e.g. do not invent "the facilitator said", "the team agreed", "participants decided" unless explicitly stated).
   - Do NOT invent decisions, agreements, policies, technical results, or future plans.
   - Do NOT invent action items, tasks, deadlines, or owners unless an explicit commitment or task assignment was made in the transcript.
   - Do NOT invent business context, strategic implications, risks, or background context not present in the recording.
   - Before including any claim, verify that it is directly supported by the transcript. If unsupported, omit it.
3. LOW-INFORMATION & SHORT RECORDINGS (CRITICAL):
   - If the transcript is short, a test utterance (e.g. "Test, test, this is a test for RICMA"), or contains minimal speech:
     - State factually and concisely what was recorded (e.g. "This was a short test recording for RICMA. No substantive discussion, decisions, or action items were present.").
     - Return empty arrays [] for "sections", "action_items", "strategic_insights", "open_questions", and "participants" (unless explicit names were stated).
     - Do NOT embellish or pad short transcripts to make them sound like full meetings.
4. SECTION-SPECIFIC RULES:
   - "title": Factual title reflecting what was actually spoken.
   - "summary" / "tldr": Summarize only what was actually said. Keep length strictly proportional to transcript length.
   - "sections": Return [] if no distinct discussion topics occurred. Each section must correspond to actual discussed content.
   - "action_items": Return [] if no explicit tasks/deliverables were assigned. Only extract direct task statements (e.g., "Ahmed will send the report by Friday"). Never convert a general topic mention into an action item.
   - "strategic_insights": Return [] if no strategic insights were explicitly stated. Do NOT generate speculative strategy.
   - "open_questions": Return [] if no unresolved questions were asked.
   - "participants": Return [] or only names explicitly introduced or mentioned in the transcript.
   - "mindmap_markdown": Construct a clean markdown tree of ONLY topics actually spoken. For short/test transcripts, provide only a minimal root and factual note.
5. TEMPLATE RULE: Meeting templates adjust analytical focus, NOT facts. Never invent domain facts to satisfy a template.

LANGUAGE DIRECTIVE: ${langInstruction}

${templateConfig.promptDirective}

OUTPUT SCHEMA (Return ONLY valid JSON matching this schema):
{
  "title": "Factual meeting or recording title",
  "meeting_date": "${meetingDate}",
  "duration_minutes": ${durationMinutes},
  "participants": [],
  "tags": ["${templateConfig.badge}"],
  "summary": "Factual summary of what was actually said.",
  "tldr": "Factual summary of what was actually said.",
  "sections": [
    {
      "n": 1,
      "title": "Discussion Topic Title",
      "narrative": "Factual narrative of this discussion.",
      "decisions": [],
      "action_items": []
    }
  ],
  "action_items": [],
  "open_questions": [],
  "strategic_insights": [],
  "mindmap_markdown": "# Title\\n## Topic\\n- Factual note"
}`;


    let intelligenceData: any = {};

    // Helper to validate model response quality
    const isValidIntelligence = (data: any): boolean => {
      if (!data || typeof data !== "object") return false;
      const hasTitle = typeof data.title === "string" && data.title.trim().length > 0;
      const hasSummary = (typeof data.summary === "string" && data.summary.trim().length > 5) ||
                         (typeof data.tldr === "string" && data.tldr.trim().length > 5) ||
                         (typeof data.executive_summary === "string" && data.executive_summary.trim().length > 5);
      return Boolean(hasTitle && hasSummary);
    };

    // 1. Primary: Groq Flagship GPT-OSS 120B / 20B for ultra-fast high-reasoning meeting synthesis
    if (GROQ_API_KEY) {
      const groqModelsToTry = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"];
      for (const mName of groqModelsToTry) {
        if (isValidIntelligence(intelligenceData)) break;
        try {
          intelligenceData = await callWithRetry(async () => {
            console.log(`[Worker] Requesting LLM synthesis from Groq model: ${mName}`);
            const groqChatRes = await fetch("https://api.groq.com/openai/v1/chat/completions", {
              method: "POST",
              headers: {
                Authorization: `Bearer ${GROQ_API_KEY}`,
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                model: mName,
                messages: [
                  { role: "system", content: systemPrompt },
                  { role: "user", content: `Meeting Transcript:\n${fullTranscript || "No audible speech detected."}` },
                ],
                response_format: { type: "json_object" },
                temperature: 0.1,
              }),
            });

            if (!groqChatRes.ok) {
              const errText = await groqChatRes.text();
              const err: any = new Error(`Groq ${mName} synthesis failed: ${errText}`);
              err.status = groqChatRes.status;
              throw err;
            }

            const groqChatJson = await groqChatRes.json();
            const rawContent = groqChatJson.choices?.[0]?.message?.content || "";
            console.log(`[Worker] Raw LLM Response preview (${mName}):`, rawContent.substring(0, 300));
            const parsed = cleanAndParseJson(rawContent);

            if (!isValidIntelligence(parsed)) {
              throw new Error(`LLM output from ${mName} failed validation (incomplete or empty intelligence structure)`);
            }

            return parsed;
          }, 3, 2000);
        } catch (groqErr) {
          console.warn(`[Worker] Groq ${mName} synthesis note:`, groqErr);
        }
      }
    }

    // 2. Secondary Fallback: Gemini Flash (if Groq was unavailable)
    if (!isValidIntelligence(intelligenceData) && GEMINI_API_KEY) {
      try {
        intelligenceData = await callWithRetry(async () => {
          console.log("[Worker] Requesting LLM synthesis fallback from Gemini...");
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
            `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${GEMINI_API_KEY}`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(geminiPayload),
            }
          );

          if (!geminiRes.ok) {
            const errText = await geminiRes.text();
            const err: any = new Error(`Gemini fallback synthesis failed: ${errText}`);
            err.status = geminiRes.status;
            throw err;
          }

          const geminiJson = await geminiRes.json();
          const rawContent = geminiJson.candidates?.[0]?.content?.parts?.[0]?.text || "";
          const parsed = cleanAndParseJson(rawContent);
          if (!isValidIntelligence(parsed)) {
            throw new Error("Gemini output failed validation");
          }
          return parsed;
        }, 2, 2000);
      } catch (geminiErr) {
        console.warn("[Worker] Gemini fallback extraction note:", geminiErr);
      }
    }

    // Strict validation: Do NOT allow fake placeholder summary to masquerade as completed analysis
    if (!isValidIntelligence(intelligenceData)) {
      throw new Error("AI meeting synthesis failed across all available LLM models. Please retry.");
    }

    const finalTitle = customTitle || intelligenceData.title || originalFilename.replace(/\.[^/.]+$/, "");
    const finalSummary = intelligenceData.summary || intelligenceData.tldr || intelligenceData.executive_summary || "";
    
    // Normalize sections (must be an array of real sections)
    let finalSections = Array.isArray(intelligenceData.sections) 
      ? intelligenceData.sections 
      : (Array.isArray(intelligenceData.discussion_pillars) ? intelligenceData.discussion_pillars : []);
    
    finalSections = finalSections.filter((s: any) => s && (s.title || s.narrative));

    // Normalize and consolidate action items
    let finalActions: any[] = Array.isArray(intelligenceData.action_items) ? intelligenceData.action_items : [];

    if (finalActions.length === 0 && finalSections.length > 0) {
      finalSections.forEach((s: any) => {
        if (Array.isArray(s.action_items)) {
          finalActions.push(...s.action_items);
        }
      });
    }

    // Filter valid action items
    finalActions = finalActions.filter((a: any) => a && (a.task || a.description));

    // Post-generation integrity check: sanitize generic boilerplate filler if present on short recordings
    const isVeryShort = fullTranscript.length < 200;
    if (isVeryShort) {
      finalActions = finalActions.filter((a: any) => {
        const text = (a.task || a.description || "").toLowerCase();
        return !text.includes("review and follow up") && !text.includes("strategic action points");
      });
    }

    // Build rich Mindmap hierarchy or minimal clean mindmap
    let finalMindmap = "";
    const isModelMindmapValid = typeof intelligenceData.mindmap_markdown === "string" &&
      intelligenceData.mindmap_markdown.trim().startsWith("#");

    if (isModelMindmapValid) {
      finalMindmap = intelligenceData.mindmap_markdown.trim();
    } else {
      const mmLines = [`# ${finalTitle}`];
      if (finalSections.length > 0) {
        finalSections.forEach((s: any, idx: number) => {
          mmLines.push(`## ${s.n || idx + 1}. ${s.title || "Topic"}`);
          if (s.narrative) {
            const sentences = String(s.narrative).split(/[\.\n]/).map((st: string) => st.trim()).filter((st: string) => st.length > 12);
            sentences.slice(0, 3).forEach((sent: string) => mmLines.push(`- ${sent}`));
          }
          if (Array.isArray(s.decisions) && s.decisions.length > 0) {
            mmLines.push(`### 📌 Decisions`);
            s.decisions.forEach((d: any) => mmLines.push(`- ${d}`));
          }
          if (Array.isArray(s.action_items) && s.action_items.length > 0) {
            mmLines.push(`### 🎯 Deliverables`);
            s.action_items.forEach((a: any) => mmLines.push(`- ${a.task || a.description}${a.owner ? ` (${a.owner})` : ""}`));
          }
        });
      } else if (finalSummary) {
        mmLines.push(`## 📋 Summary`);
        mmLines.push(`- ${finalSummary.substring(0, 160)}`);
      }
      if (finalActions.length > 0) {
        mmLines.push(`## ✅ Action Items`);
        finalActions.forEach((a: any) => {
          mmLines.push(`- ${a.task || a.description}${a.owner ? ` — ${a.owner}` : ""}`);
        });
      }
      finalMindmap = mmLines.join("\n");
    }

    const metadataObj = {
      user_id: userId || null,
      template: templateType,
      template_type: templateType,
      duration_minutes: durationMinutes,
      duration_seconds: durationSeconds,
      meeting_date: intelligenceData.meeting_date || meetingDate,
      tags: Array.isArray(intelligenceData.tags) && intelligenceData.tags.length > 0 ? intelligenceData.tags : [templateConfig.badge],
      participants: Array.isArray(intelligenceData.participants) ? intelligenceData.participants : [],
      open_questions: Array.isArray(intelligenceData.open_questions) ? intelligenceData.open_questions : [],
      audio_filename: originalFilename,
      storage_path: trustedStoragePath,
      tldr: finalSummary,
      insights: Array.isArray(intelligenceData.strategic_insights) ? intelligenceData.strategic_insights : [],
    };



    // ------------------------------------------------------------------------
    // Step 3: Update Supabase Session to status = 'completed'
    // ------------------------------------------------------------------------
    if (SUPABASE_URL && SUPABASE_SERVICE_ROLE_KEY) {
      const updatePayload = {
        title: finalTitle,
        summary: finalSummary,
        executive_summary: finalSummary,
        discussion_pillars: finalSections,
        action_items: finalActions,
        strategic_insights: metadataObj,
        mindmap_markdown: finalMindmap,
        transcript: fullTranscript,
        transcript_segments: formattedSegments,
        status: "completed",
        processing_completed_at: new Date().toISOString(),
        error_message: null,
      };

      const updateRes = await fetch(`${SUPABASE_URL}/rest/v1/sessions?id=eq.${encodeURIComponent(sessionId)}`, {
        method: "PATCH",
        headers: {
          apikey: SUPABASE_SERVICE_ROLE_KEY,
          Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
          "Content-Type": "application/json",
          Prefer: "return=representation",
        },
        body: JSON.stringify(updatePayload),
      });

      if (!updateRes.ok) {
        const updateErr = await updateRes.text();
        console.error(`[Worker] Failed to update session ${sessionId}:`, updateRes.status, updateErr);
        throw new Error(`Database update failed (${updateRes.status}): ${updateErr}`);
      }

      console.log(`[Worker] Successfully updated session ${sessionId} status to 'completed'`);

      console.log(`[Worker] Updated session ${sessionId} status to 'completed' (${updateRes.status})`);

      // Update user usage quota in Supabase profiles
      if (userId && userId !== "guest") {
        try {
          const profileRes = await fetch(
            `${SUPABASE_URL}/rest/v1/profiles?id=eq.${encodeURIComponent(userId)}&select=minutes_used_this_month`,
            {
              headers: {
                apikey: SUPABASE_SERVICE_ROLE_KEY,
                Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
              },
            }
          );
          if (profileRes.ok) {
            const prof = await profileRes.json();
            const currentUsed = Number(prof?.[0]?.minutes_used_this_month || 0);
            await fetch(`${SUPABASE_URL}/rest/v1/profiles?id=eq.${encodeURIComponent(userId)}`, {
              method: "PATCH",
              headers: {
                apikey: SUPABASE_SERVICE_ROLE_KEY,
                Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                minutes_used_this_month: currentUsed + durationMinutes,
              }),
            });
          }
        } catch (quotaErr) {
          console.warn("[Worker] Failed to update user quota:", quotaErr);
        }
      }
    }

    return NextResponse.json({
      ok: true,
      session_id: sessionId,
      status: "completed",
      duration_minutes: durationMinutes,
    });
  } catch (err: any) {
    console.error(`[Worker] Processing failed for session ${sessionId}:`, err);

    // Update status to 'failed' in Supabase so user sees the error and retry option
    if (sessionId && SUPABASE_URL && SUPABASE_SERVICE_ROLE_KEY) {
      try {
        await fetch(`${SUPABASE_URL}/rest/v1/sessions?id=eq.${encodeURIComponent(sessionId)}`, {
          method: "PATCH",
          headers: {
            apikey: SUPABASE_SERVICE_ROLE_KEY,
            Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            status: "failed",
            error_message: err?.message || "Unknown error during audio intelligence processing",
            processing_completed_at: new Date().toISOString(),
          }),
        });
        console.log(`[Worker] Updated session ${sessionId} status to 'failed'`);
      } catch (dbErr) {
        console.error("[Worker] Failed to record error status to Supabase:", dbErr);
      }
    }

    return NextResponse.json(
      {
        ok: false,
        session_id: sessionId,
        error: err?.message || "Internal processing error",
      },
      { status: 500 }
    );
  }
}
