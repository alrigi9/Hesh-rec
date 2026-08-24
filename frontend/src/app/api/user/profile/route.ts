import { NextRequest, NextResponse } from "next/server";
import { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } from "@/lib/server-config";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const userId = searchParams.get("user_id");

    const defaultProfile = {
      id: userId || "guest",
      email: "guest@recmap.tech",
      role: "user",
      monthly_minutes_limit: 300.0,
      minutes_used_this_month: 0.0,
      minutes_remaining: 300.0,
      percent_used: 0.0,
      can_upload: true,
    };

    if (!userId || userId === "guest") {
      return NextResponse.json(defaultProfile);
    }

    // Query Supabase profiles table
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/profiles?id=eq.${encodeURIComponent(userId)}&select=*`,
      {
        headers: {
          apikey: SUPABASE_SERVICE_ROLE_KEY,
          Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
        },
      }
    );

    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        const p = data[0];
        const limit = Number(p.monthly_minutes_limit ?? 300.0);
        const used = Number(p.minutes_used_this_month ?? 0.0);
        const remaining = Math.max(0, limit - used);
        const percent = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
        return NextResponse.json({
          id: p.id,
          email: p.email || defaultProfile.email,
          role: p.role || "user",
          monthly_minutes_limit: limit,
          minutes_used_this_month: used,
          minutes_remaining: remaining,
          percent_used: percent,
          can_upload: used < limit || p.role === "admin",
        });
      }
    }

    return NextResponse.json(defaultProfile);
  } catch {
    return NextResponse.json({
      id: "guest",
      email: "guest@recmap.tech",
      role: "user",
      monthly_minutes_limit: 300.0,
      minutes_used_this_month: 0.0,
      minutes_remaining: 300.0,
      percent_used: 0.0,
      can_upload: true,
    });
  }
}
