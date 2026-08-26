import { NextRequest, NextResponse, after } from "next/server";
import { 
  SUPABASE_URL, 
  SUPABASE_SERVICE_ROLE_KEY 
} from "@/lib/server-config";
import { getAuthenticatedUser } from "@/lib/serverAuth";
import { normalizeTemplate } from "@/lib/templates";

export const maxDuration = 60;
 // Max allowed serverless duration
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    const authUser = await getAuthenticatedUser(request);
    if (!authUser || !authUser.id) {
      return NextResponse.json(
        { error: "Unauthorized: Authentication required" },
        { status: 401 }
      );
    }

    const { session_id } = await request.json();
    if (!session_id) {
      return NextResponse.json({ error: "Missing session_id" }, { status: 400 });
    }

    // 1. Fetch current session details from Supabase
    const res = await fetch(`${SUPABASE_URL}/rest/v1/sessions?id=eq.${encodeURIComponent(session_id)}&select=*`, {
      headers: {
        apikey: SUPABASE_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
      },
    });

    if (!res.ok) {
      return NextResponse.json({ error: "Session not found" }, { status: 404 });
    }

    const rows = await res.json();
    if (!rows || rows.length === 0) {
      return NextResponse.json({ error: "Session not found" }, { status: 404 });
    }

    const session = rows[0];
    const meta = (typeof session.strategic_insights === "object" && session.strategic_insights !== null)
      ? session.strategic_insights
      : {};

    const sessionOwnerId = session.user_id || meta.user_id;
    if (sessionOwnerId && sessionOwnerId !== authUser.id && authUser.role !== "admin") {
      return NextResponse.json(
        { error: "Forbidden: You cannot retry a session belonging to another user." },
        { status: 403 }
      );
    }

    const storagePath = meta.storage_path || null;
    const fileUrl = meta.audio_url || null;
    const title = session.title || "Meeting Session";
    const template = normalizeTemplate(meta.template || meta.template_type || session.template || "auto");

    const language = meta.language || "auto";
    const userId = authUser.id;
    const filename = meta.audio_filename || "meeting_audio.m4a";


    // 2. Reject retry immediately if session is already completed
    if (session.status === "completed") {
      return NextResponse.json({
        ok: true,
        status: "completed",
        session_id,
        message: "Session is already completed.",
      });
    }

    // 3. Atomic Conditional Reset for Retry:
    // Only allows resetting the lock if:
    //   - status is 'failed'
    //   - OR status is 'processing' AND processing_started_at is older than stale threshold (180s)
    // If status is 'processing' with a recent processing_started_at or null (just created), it returns 0 rows!
    const staleIso = new Date(Date.now() - 180000).toISOString();
    const retryClaimRes = await fetch(
      `${SUPABASE_URL}/rest/v1/sessions?id=eq.${encodeURIComponent(session_id)}&status=neq.completed&or=(status.eq.failed,and(status.eq.processing,processing_started_at.not.is.null,processing_started_at.lt.${encodeURIComponent(staleIso)}))`,
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
          error_message: null,
          processing_started_at: null,
          processing_completed_at: null,
        }),
      }
    );

    if (!retryClaimRes.ok) {
      const errText = await retryClaimRes.text();
      console.error("[Retry] Failed to claim session for retry:", retryClaimRes.status, errText);
      return NextResponse.json({ error: "Failed to initialize retry lock" }, { status: 500 });
    }

    const claimedRows = await retryClaimRes.json();
    if (!Array.isArray(claimedRows) || claimedRows.length === 0) {
      console.log(`[Retry] Session ${session_id} is already actively processing or completed. Ignoring redundant retry.`);
      return NextResponse.json({
        ok: true,
        status: "already_processing",
        session_id,
        message: "Session is currently being actively processed by a worker.",
      });
    }

    console.log(`[Retry] Retry lock acquired atomically for session ${session_id}`);

    // 4. Dispatch background worker via after()
    const protocol = request.headers.get("x-forwarded-proto") || "https";
    const host = request.headers.get("x-forwarded-host") || request.headers.get("host") || "localhost:3000";
    const appOrigin = process.env.NEXT_PUBLIC_APP_URL || `${protocol}://${host}`;
    const workerUrl = `${appOrigin.replace(/\/+$/, "")}/api/process-audio/worker`;

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
            session_id,
            storage_path: storagePath,
            title,
            template,
            language,
            user_id: userId,
            filename,
            pre_transcript: session.transcript || null,
            pre_segments_json: session.transcript_segments || null,
            duration_seconds: meta.duration_seconds || (session.duration_minutes ? session.duration_minutes * 60 : 0),
          }),


        });
      } catch (err) {
        console.error("[Retry] Background worker dispatch failed:", err);
      }
    });

    return NextResponse.json({ ok: true, session_id, status: "processing" });
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || "Failed to retry processing" }, { status: 500 });
  }
}


