import { NextRequest, NextResponse, after } from "next/server";

import { 
  SUPABASE_URL, 
  SUPABASE_SERVICE_ROLE_KEY 
} from "@/lib/server-config";
import { getAuthenticatedUser } from "@/lib/serverAuth";
import { normalizeTemplate, TEMPLATES_CONFIG, TemplateId } from "@/lib/templates";

export const maxDuration = 60; // Max allowed serverless duration
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    // 0. Strict Server-Side Authentication Guard
    const authUser = await getAuthenticatedUser(request);
    if (!authUser || !authUser.id) {
      return NextResponse.json(
        { error: "Unauthorized: You must be logged in to process audio sessions." },
        { status: 401 }
      );
    }
    const userId = authUser.id;

    let fileUrl: string | null = null;
    let storagePath: string | null = null;
    let templateType: TemplateId = "auto";
    let language = "auto";

    let customTitle: string | null = null;
    let preTranscript: string | null = null;
    let preSegmentsJson: string | null = null;
    let preDurationSeconds = 0.0;
    let originalFilename = "meeting_audio.m4a";

    const contentType = request.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
      const jsonBody = await request.json();
      storagePath = jsonBody.storage_path || null;
      fileUrl = jsonBody.audioUrl || jsonBody.audio_url || jsonBody.file_url || jsonBody.url || null;
      preTranscript = jsonBody.transcript || jsonBody.transcript_text || jsonBody.text || "";
      templateType = normalizeTemplate(jsonBody.template || jsonBody.template_type || "auto");
      language = jsonBody.language || "auto";
      customTitle = jsonBody.custom_title || jsonBody.title || null;
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
      storagePath = (formData.get("storage_path") as string) || null;
      fileUrl = (formData.get("audioUrl") as string) || (formData.get("audio_url") as string) || (formData.get("file_url") as string) || null;
      templateType = normalizeTemplate((formData.get("template_type") as string) || (formData.get("template") as string) || "auto");
      language = (formData.get("language") as string) || "auto";
      customTitle = (formData.get("custom_title") as string) || (formData.get("title") as string) || null;
      preTranscript = (formData.get("transcript_text") as string) || (formData.get("transcript") as string) || null;
      preSegmentsJson = (formData.get("transcript_segments") as string) || null;
      preDurationSeconds = Number(formData.get("duration_seconds") || 0.0);
      originalFilename = (formData.get("filename") as string) || "meeting_audio.m4a";
    }


    // 1. Resolve & strictly validate storage_path ownership
    if (!storagePath && fileUrl) {
      // Extract storage path from legacy Supabase storage URL if possible
      const match = fileUrl.match(/\/storage\/v1\/object\/(?:public|authenticated|sign)\/recordings\/(.+)$/);
      if (match && match[1]) {
        storagePath = decodeURIComponent(match[1]);
      } else {
        // Reject arbitrary external URLs to prevent SSRF and cross-tenant access
        return NextResponse.json(
          { detail: "Invalid audio URL: Only official Supabase recordings storage paths are permitted." },
          { status: 400 }
        );
      }
    }

    if (storagePath) {
      // Validate storage path against path traversal and verify user ownership
      if (storagePath.includes("..") || storagePath.includes("\\")) {
        return NextResponse.json({ detail: "Invalid storage path." }, { status: 400 });
      }

      const pathUserId = storagePath.split("/")[0];
      if (userId && pathUserId && pathUserId !== userId && authUser.role !== "admin") {
        return NextResponse.json(
          { detail: "Forbidden: You cannot process audio belonging to another user account." },
          { status: 403 }
        );
      }
    }

    if (!storagePath && !preTranscript) {
      return NextResponse.json({ detail: "No audio storage path or transcript provided." }, { status: 400 });
    }

    // 2. Quota Pre-Check
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
        console.error("[ProcessAudio] Profile check error:", err);
      }
    }

    if (userRole !== "admin" && userUsed >= userLimit) {
      return NextResponse.json(
        { detail: `Monthly quota limit of ${userLimit} minutes has been reached.` },
        { status: 403 }
      );
    }

    // 3. Generate Session ID & Initial Record
    const sessionId = typeof crypto !== "undefined" && crypto.randomUUID 
      ? crypto.randomUUID() 
      : `00000000-0000-4000-8000-${Date.now().toString(16).padStart(12, "0")}`;

    const finalTitle = customTitle || originalFilename.replace(/\.[^/.]+$/, "") || "New Audio Session";
    const meetingDate = new Date().toISOString().split("T")[0];
    const startedAt = new Date().toISOString();

    const metadataObj = {
      session_id: sessionId,
      user_id: userId || null,
      meeting_date: meetingDate,
      audio_filename: originalFilename,
      storage_path: storagePath,
      template: templateType,
      template_type: templateType,
      language,
    };

    const initialSessionPayload = {
      id: sessionId,
      title: finalTitle,
      meeting_date: meetingDate,
      date: meetingDate,
      duration: "Processing...",
      duration_minutes: 0,
      tags: ["Processing", TEMPLATES_CONFIG[templateType]?.badge || templateType],
      participants: ["Speaker 1"],

      tldr: "Audio processing and AI synthesis underway...",
      summary: "Audio processing and AI synthesis underway...",
      executive_summary: "Audio processing and AI synthesis underway...",
      sections: [],
      discussion_pillars: [],
      action_items: [],
      open_questions: [],
      strategic_insights: metadataObj,
      mindmap_markdown: `# ${finalTitle}\n## Status\n- Processing in progress...`,
      transcript_segments: [],
      transcript: preTranscript || "",
      full_transcript_text: preTranscript || "",
      raw_markdown: `# ${finalTitle}\n\n*Processing audio...*`,
      metadata: metadataObj,
      user_id: userId || null,
      created_at: startedAt,
      status: "processing",
      processing_started_at: startedAt,
      processing_completed_at: null,
      error_message: null,
      is_public: false,
    };

    // 3. Insert initial session with status = 'processing' into Supabase
    if (SUPABASE_URL && SUPABASE_SERVICE_ROLE_KEY) {
      const dbInsertPayload = {
        id: sessionId,
        user_id: (userId && userId !== "guest") ? userId : null,
        title: finalTitle,
        status: "processing",
        processing_started_at: null,
        summary: "",
        executive_summary: "",
        discussion_pillars: [],
        action_items: [],
        strategic_insights: metadataObj,
        mindmap_markdown: `# ${finalTitle}\n## Status\n- Processing...`,
        transcript: preTranscript || "",
        transcript_segments: [],
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
        body: JSON.stringify(dbInsertPayload),
      });

      if (!dbRes.ok) {
        const dbErrText = await dbRes.text();
        console.error("[ProcessAudio] Failed to insert initial session:", dbRes.status, dbErrText);
      } else {
        console.log(`[ProcessAudio] Created processing session: ${sessionId}`);
      }
    }

    // 4. Trigger Background Worker via after() to prevent serverless freeze
    const protocol = request.headers.get("x-forwarded-proto") || "https";
    const host = request.headers.get("x-forwarded-host") || request.headers.get("host") || "localhost:3000";
    const appOrigin = process.env.NEXT_PUBLIC_APP_URL || `${protocol}://${host}`;

    const workerUrl = `${appOrigin.replace(/\/+$/, "")}/api/process-audio/worker`;
    console.log(`[ProcessAudio] Dispatching background worker via after(): ${workerUrl} for session ${sessionId}`);

    const authHeader = request.headers.get("authorization") || request.headers.get("Authorization") || "";

    after(async () => {
      try {
        await fetch(workerUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(authHeader ? { Authorization: authHeader } : (SUPABASE_SERVICE_ROLE_KEY ? { Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}` } : {})),
          },
          body: JSON.stringify({
            session_id: sessionId,
            storage_path: storagePath,
            title: finalTitle,
            template: templateType,
            language,
            user_id: userId,
            filename: originalFilename,
            pre_transcript: preTranscript,
            pre_segments_json: preSegmentsJson,
            duration_seconds: preDurationSeconds,
          }),

        });
      } catch (workerErr) {
        console.error("[ProcessAudio] Background worker dispatch failed:", workerErr);
      }
    });

    // 5. Fast Instant Response back to client (<1s)
    return NextResponse.json({
      ...initialSessionPayload,
      session_id: sessionId,
      status: "processing",
    });

  } catch (err: any) {
    console.error("[ProcessAudio] Immediate handler failed:", err);
    return NextResponse.json(
      { detail: err.message || "Failed to initialize audio processing" },
      { status: 500 }
    );
  }
}
