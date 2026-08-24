import { NextRequest, NextResponse } from "next/server";
import { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } from "@/lib/server-config";

export async function POST(request: NextRequest) {
  try {
    const { target_user_id } = await request.json();
    if (!target_user_id) {
      return NextResponse.json({ error: "Missing target_user_id" }, { status: 400 });
    }

    const res = await fetch(`${SUPABASE_URL}/rest/v1/profiles?id=eq.${encodeURIComponent(target_user_id)}`, {
      method: "PATCH",
      headers: {
        apikey: SUPABASE_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        minutes_used_this_month: 0.0,
      }),
    });

    if (!res.ok) {
      throw new Error("Failed to reset user quota");
    }

    return NextResponse.json({ success: true, minutes_used_this_month: 0.0 });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
