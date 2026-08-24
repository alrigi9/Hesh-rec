import { NextRequest, NextResponse } from "next/server";
import { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } from "@/lib/server-config";

export async function POST(request: NextRequest) {
  try {
    const { target_user_id, monthly_minutes_limit } = await request.json();
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
        monthly_minutes_limit: Number(monthly_minutes_limit),
      }),
    });

    if (!res.ok) {
      throw new Error("Failed to update quota limit");
    }

    return NextResponse.json({ success: true, monthly_minutes_limit });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
