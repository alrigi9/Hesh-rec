import { NextRequest, NextResponse } from "next/server";
import { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } from "@/lib/server-config";
import { getAuthenticatedUser } from "@/lib/serverAuth";

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
    const userId = authUser.id;

    if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
      return NextResponse.json(
        { error: "Server configuration missing" },
        { status: 500 }
      );
    }

    // 1. List user's storage objects strictly in recordings/${userId}
    const listRes = await fetch(
      `${SUPABASE_URL}/storage/v1/object/list/recordings`,
      {
        method: "POST",
        headers: {
          apikey: SUPABASE_SERVICE_ROLE_KEY,
          Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prefix: `${userId}`,
          limit: 100,
          offset: 0,
        }),
      }
    );

    let storageFilesDeleted = 0;
    if (listRes.ok) {
      const files = await listRes.json();
      if (Array.isArray(files) && files.length > 0) {
        const filePaths = files.map((f: any) => `${userId}/${f.name}`);
        const delRes = await fetch(
          `${SUPABASE_URL}/storage/v1/object/recordings`,
          {
            method: "DELETE",
            headers: {
              apikey: SUPABASE_SERVICE_ROLE_KEY,
              Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              prefixes: filePaths,
            }),
          }
        );
        if (delRes.ok) {
          storageFilesDeleted = filePaths.length;
        }
      }
    }

    // 2. Delete any remaining sessions for this user
    const delSessionsRes = await fetch(
      `${SUPABASE_URL}/rest/v1/sessions?user_id=eq.${encodeURIComponent(userId)}`,
      {
        method: "DELETE",
        headers: {
          apikey: SUPABASE_SERVICE_ROLE_KEY,
          Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
          Prefer: "return=representation",
        },
      }
    );

    let sessionsDeleted = 0;
    if (delSessionsRes.ok) {
      const deletedRows = await delSessionsRes.json();
      sessionsDeleted = Array.isArray(deletedRows) ? deletedRows.length : 0;
    }

    return NextResponse.json({
      success: true,
      user_id: userId,
      storage_objects_deleted: storageFilesDeleted,
      sessions_deleted: sessionsDeleted,
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Failed to cleanup user data" },
      { status: 500 }
    );
  }
}
