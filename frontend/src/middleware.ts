import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Protect /admin routes at the server/edge layer
  if (pathname.startsWith("/admin")) {
    const allCookies = request.cookies.getAll();
    const hasAuthCookie = allCookies.some(
      (c) =>
        c.name.includes("sb-") &&
        (c.name.includes("auth-token") || c.name.includes("access-token")) &&
        Boolean(c.value && c.value.trim().length > 0)
    );

    const authHeader = request.headers.get("authorization");
    const hasAuthHeader = Boolean(authHeader && authHeader.startsWith("Bearer "));

    // If client is navigating without any session cookie or header, redirect to /login
    if (!hasAuthCookie && !hasAuthHeader) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("redirect", pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/admin", "/admin/:path*"],
};
