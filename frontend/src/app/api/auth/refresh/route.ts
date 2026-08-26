import { NextRequest, NextResponse } from "next/server";
import { SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY } from "@/lib/server-config";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}));
    const { refresh_token } = body;

    if (!refresh_token || typeof refresh_token !== "string" || !refresh_token.trim()) {
      return NextResponse.json({ error: "Missing or invalid refresh_token" }, { status: 400 });
    }

    if (!SUPABASE_URL) {
      return NextResponse.json({ error: "Supabase configuration is missing on server" }, { status: 500 });
    }

    const apiKey = SUPABASE_ANON_KEY || SUPABASE_SERVICE_ROLE_KEY;

    // Call Supabase OAuth / Token Refresh REST API
    const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: apiKey,
      },
      body: JSON.stringify({ refresh_token: refresh_token.trim() }),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(
        { error: data.error_description || data.msg || data.error || "Failed to refresh token" },
        { status: response.status }
      );
    }

    return NextResponse.json({
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      expires_at: data.expires_at,
      expires_in: data.expires_in,
      token_type: data.token_type,
      user: data.user ? { id: data.user.id, email: data.user.email } : null,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Internal server error" }, { status: 500 });
  }
}
