import "server-only";
import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } from "@/lib/server-config";

export interface AuthenticatedUser {
  id: string;
  email?: string;
  role?: string;
}

/**
 * Server-side authentication guard for Next.js App Router API endpoints.
 * Validates the Supabase JWT access token from the Authorization header or cookies.
 * NEVER trusts client-supplied user_id parameters.
 */
export async function getAuthenticatedUser(request: NextRequest): Promise<AuthenticatedUser | null> {
  try {
    if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
      console.error("[ServerAuth] Supabase server credentials not configured");
      return null;
    }

    const authHeader = request.headers.get("authorization") || request.headers.get("Authorization") || "";
    let token = "";

    if (authHeader.toLowerCase().startsWith("bearer ")) {
      token = authHeader.substring(7).trim();
    }

    if (!token) {
      // Check cookies for Supabase auth token
      const cookieHeader = request.headers.get("cookie") || "";
      const match = cookieHeader.match(/sb-[a-z0-9_-]+-auth-token=([^;]+)/i);
      if (match) {
        try {
          const decoded = decodeURIComponent(match[1]);
          const parsed = JSON.parse(decoded);
          token = Array.isArray(parsed) ? parsed[0] : (parsed.access_token || parsed[0] || "");
        } catch {}
      }
    }

    if (!token) {
      return null;
    }

    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
      auth: {
        persistSession: false,
        autoRefreshToken: false,
      },
    });

    const { data, error } = await supabase.auth.getUser(token);

    if (error || !data?.user || !data.user.id) {
      return null;
    }

    // Retrieve trusted role from the database profiles table
    let trustedRole = (data.user.app_metadata?.role as string) || "user";
    try {
      const { data: profile } = await supabase
        .from("profiles")
        .select("role")
        .eq("id", data.user.id)
        .maybeSingle();

      if (profile?.role) {
        trustedRole = profile.role;
      }
    } catch (profileErr) {
      console.warn("[ServerAuth] Error fetching user profile role:", profileErr);
    }

    return {
      id: data.user.id,
      email: data.user.email,
      role: trustedRole,
    };
  } catch (err) {
    console.error("[ServerAuth] Error validating token:", err);
    return null;
  }
}

/**
 * Server-side admin authorization guard.
 * Returns { user, errorResponse: null } if the caller is an authenticated admin.
 * Returns { user: null, errorResponse: NextResponse } (401 or 403) if unauthorized.
 */
export async function requireAdmin(request: NextRequest): Promise<{
  user: AuthenticatedUser | null;
  errorResponse: NextResponse | null;
}> {
  const user = await getAuthenticatedUser(request);
  if (!user || !user.id) {
    return {
      user: null,
      errorResponse: NextResponse.json(
        { error: "Unauthorized: Authentication required" },
        { status: 401 }
      ),
    };
  }

  if (user.role !== "admin") {
    return {
      user: null,
      errorResponse: NextResponse.json(
        { error: "Forbidden: Administrative privileges required" },
        { status: 403 }
      ),
    };
  }

  return { user, errorResponse: null };
}

