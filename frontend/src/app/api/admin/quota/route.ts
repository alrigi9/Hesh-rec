import { NextRequest, NextResponse } from "next/server";
import { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } from "@/lib/server-config";
import { requireAdmin } from "@/lib/serverAuth";

export async function POST(request: NextRequest) {
  return handleQuotaUpdate(request);
}

export async function PATCH(request: NextRequest) {
  return handleQuotaUpdate(request);
}

async function handleQuotaUpdate(request: NextRequest) {
  try {
    const { errorResponse } = await requireAdmin(request);
    if (errorResponse) {
      return errorResponse;
    }

    const body = await request.json().catch(() => ({}));
    const targetUserId = body.target_user_id || body.user_id;

    const limitValue =
      body.monthly_minutes_limit !== undefined
        ? Number(body.monthly_minutes_limit)
        : body.quota_limit !== undefined
        ? Number(body.quota_limit)
        : body.monthly_quota !== undefined
        ? Number(body.monthly_quota)
        : body.limit !== undefined
        ? Number(body.limit)
        : 300;

    if (!targetUserId) {
      return NextResponse.json({ error: "Missing target_user_id or user_id" }, { status: 400 });
    }

    const updatePayload: Record<string, any> = {
      monthly_minutes_limit: limitValue,
    };
    if (body.role) {
      updatePayload.role = body.role;
    }

    const res = await fetch(`${SUPABASE_URL}/rest/v1/profiles?id=eq.${encodeURIComponent(targetUserId)}`, {
      method: "PATCH",
      headers: {
        apikey: SUPABASE_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
        "Content-Type": "application/json",
        Prefer: "return=representation",
      },
      body: JSON.stringify(updatePayload),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Failed to update quota limit: ${errText}`);
    }

    // Also update auth user metadata if present
    try {
      await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${encodeURIComponent(targetUserId)}`, {
        method: "PUT",
        headers: {
          apikey: SUPABASE_SERVICE_ROLE_KEY,
          Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_metadata: { monthly_minutes_limit: limitValue },
        }),
      });
    } catch {
      // Non-blocking
    }

    return NextResponse.json({ success: true, monthly_minutes_limit: limitValue });
  } catch (err: any) {
    console.error("Quota update error:", err);
    return NextResponse.json({ error: err.message || "Internal server error" }, { status: 500 });
  }
}
