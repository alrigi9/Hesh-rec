import { NextRequest, NextResponse } from "next/server";
import { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } from "@/lib/server-config";

export async function GET(_request: NextRequest) {
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/profiles?select=*&order=created_at.desc`, {
      headers: {
        apikey: SUPABASE_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
      },
    });

    if (!res.ok) {
      return NextResponse.json({ users: [], stats: null });
    }

    const profiles = await res.json();
    const users = (profiles || []).map((p: any) => {
      const limit = Number(p.monthly_minutes_limit ?? p.monthly_quota_limit ?? p.quota_limit ?? p.monthly_quota ?? 300.0);
      const used = Number(p.minutes_used_this_month ?? 0.0);
      const remaining = Math.max(0, limit - used);
      const percent = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
      return {
        id: p.id,
        email: p.email || "user@recmap.tech",
        role: p.role || "user",
        created_at: p.created_at || new Date().toISOString(),
        email_confirmed: p.email_confirmed ?? true,
        monthly_minutes_limit: limit,
        minutes_used_this_month: used,
        minutes_remaining: remaining,
        percent_used: percent,
        can_upload: used < limit || p.role === "admin",
      };
    });

    const totalUsers = users.length;
    const totalMinutes = users.reduce((acc: number, u: any) => acc + (u.minutes_used_this_month || 0), 0);
    const avgUsage = totalUsers > 0 ? totalMinutes / totalUsers : 0;

    const stats = {
      total_users: totalUsers,
      total_minutes_processed: totalMinutes,
      average_usage_per_user: avgUsage,
      system_limit_per_user: 300.0,
      active_users_this_month: users.filter((u: any) => u.minutes_used_this_month > 0).length,
    };

    return NextResponse.json({ users, stats });
  } catch (err: any) {
    return NextResponse.json({ users: [], stats: null, error: err.message });
  }
}
