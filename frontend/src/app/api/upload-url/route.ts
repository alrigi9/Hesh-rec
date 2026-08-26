import { NextRequest, NextResponse } from "next/server";
import { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } from "@/lib/server-config";
import { getAuthenticatedUser } from "@/lib/serverAuth";

export const maxDuration = 30;

export async function POST(request: NextRequest) {
  try {
    const authUser = await getAuthenticatedUser(request);
    if (!authUser || !authUser.id) {
      return NextResponse.json(
        { detail: "Unauthorized: You must be logged in to request an upload URL." },
        { status: 401 }
      );
    }
    const userId = authUser.id;

    const body = await request.json().catch(() => ({}));
    const filename = body.filename || "recording.m4a";

    // 1. Sanitize filename and strictly prevent path traversal
    let safeFilename = filename
      .replace(/[/\\]/g, "")
      .replace(/\.\./g, "")
      .replace(/[^a-zA-Z0-9._-]/g, "_")
      .trim();

    if (!safeFilename || safeFilename.startsWith(".")) {
      safeFilename = `recording_${Date.now()}.m4a`;
    }

    if (!safeFilename.includes(".")) {
      safeFilename += ".m4a";
    }

    // 2. Enforce strict server-side user-isolated storage path
    const safeUniqueId = typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
    const storagePath = `${userId}/${safeUniqueId}_${safeFilename}`;

    // 3. Create signed upload URL via Supabase Storage
    const signRes = await fetch(
      `${SUPABASE_URL}/storage/v1/object/upload/sign/recordings/${encodeURIComponent(storagePath)}`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
          apikey: SUPABASE_SERVICE_ROLE_KEY,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ upsert: true }),
      }
    );

    if (!signRes.ok) {
      const errText = await signRes.text();
      return NextResponse.json(
        { detail: `Failed to create signed upload URL: ${errText}` },
        { status: signRes.status || 500 }
      );
    }

    const signData = await signRes.json();
    const uploadUrl = `${SUPABASE_URL}/storage/v1${signData.url}`;

    return NextResponse.json({
      upload_url: uploadUrl,
      storage_path: storagePath,
      filename: safeFilename,
    });

  } catch (err: any) {
    console.error("Upload-url endpoint error:", err);
    return NextResponse.json(
      { detail: err.message || "Failed to generate upload URL" },
      { status: 500 }
    );
  }
}
