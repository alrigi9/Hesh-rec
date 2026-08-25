import { NextRequest, NextResponse } from "next/server";
import { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } from "@/lib/server-config";

export const maxDuration = 30;

export async function POST(request: NextRequest) {
  try {
    const body = await request.json().catch(() => ({}));
    const filename = body.filename || "recording.m4a";
    const userId = body.user_id || "user";

    let safeFilename = filename.replace(/[^a-zA-Z0-9._-]/g, "_");
    if (!safeFilename.includes(".")) {
      safeFilename += ".m4a";
    }

    const storagePath = `${userId}/${Date.now()}_${safeFilename}`;

    const signRes = await fetch(
      `${SUPABASE_URL}/storage/v1/object/upload/sign/recordings/${storagePath}`,
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
    const publicUrl = `${SUPABASE_URL}/storage/v1/object/public/recordings/${storagePath}`;

    return NextResponse.json({
      upload_url: uploadUrl,
      file_url: publicUrl,
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
