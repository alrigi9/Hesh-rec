import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    status: "ok",
    service: "recmap-api",
    version: "3.0.0",
    default_model: "gemini-2.5-flash",
    monthly_quota_limit: 300.0,
    max_upload_size_mb: 50,
  });
}
