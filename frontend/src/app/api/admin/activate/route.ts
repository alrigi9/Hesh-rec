import { NextRequest, NextResponse } from "next/server";
import { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } from "@/lib/server-config";
import { requireAdmin } from "@/lib/serverAuth";

export async function POST(request: NextRequest) {
  return handleActivation(request);
}

export async function PATCH(request: NextRequest) {
  return handleActivation(request);
}

async function handleActivation(request: NextRequest) {
  try {
    const { errorResponse } = await requireAdmin(request);
    if (errorResponse) {
      return errorResponse;
    }

    const body = await request.json().catch(() => ({}));
    const targetUserId = body.target_user_id || body.user_id;


    if (!targetUserId) {
      return NextResponse.json({ error: "Missing target_user_id or user_id" }, { status: 400 });
    }

    // 1. Update Supabase profiles table
    try {
      await fetch(`${SUPABASE_URL}/rest/v1/profiles?id=eq.${encodeURIComponent(targetUserId)}`, {
        method: "PATCH",
        headers: {
          apikey: SUPABASE_SERVICE_ROLE_KEY,
          Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
          "Content-Type": "application/json",
          Prefer: "return=representation",
        },
        body: JSON.stringify({
          email_confirmed: true,
          is_active: true,
          is_verified: true,
        }),
      });
    } catch (profileErr) {
      console.warn("Profile update note:", profileErr);
    }

    // 2. Update Supabase Auth Admin user (if auth user exists)
    try {
      await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${encodeURIComponent(targetUserId)}`, {
        method: "PUT",
        headers: {
          apikey: SUPABASE_SERVICE_ROLE_KEY,
          Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email_confirm: true,
          user_metadata: { email_confirmed: true, is_verified: true },
        }),
      });
    } catch (authErr) {
      console.warn("Auth admin update note:", authErr);
    }

    return NextResponse.json({ success: true, activated: true, is_verified: true });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Failed to activate user" }, { status: 500 });
  }
}
