import { NextResponse } from "next/server";
import { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } from "@/lib/server-config";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/sessions?select=id&limit=1`, {
      headers: {
        apikey: SUPABASE_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
      },
    });

    return NextResponse.json({
      ok: res.ok,
      status: res.status,
      message: "Supabase Keep-Alive heartbeat acknowledged",
      timestamp: new Date().toISOString(),
    });
  } catch (err: any) {
    return NextResponse.json(
      {
        ok: false,
        error: err?.message || "Keep-alive ping failed",
        timestamp: new Date().toISOString(),
      },
      { status: 500 }
    );
  }
}
