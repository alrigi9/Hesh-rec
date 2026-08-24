import { NextRequest, NextResponse } from "next/server";
import { GEMINI_API_KEY } from "@/lib/server-config";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { session, query, messages = [] } = body;

    if (!query) {
      return NextResponse.json({ error: "Missing query" }, { status: 400 });
    }

    const sessionContext = `Meeting Title: ${session?.title || "Meeting"}
Date: ${session?.meeting_date || session?.date || "N/A"}
Executive Summary: ${session?.summary || session?.tldr || ""}
Action Items: ${JSON.stringify(session?.action_items || [])}
Transcript: ${(session?.transcript_segments || []).map((s: any) => `${s.speaker}: ${s.text}`).join("\n")}`;

    const prompt = `You are an AI meeting assistant. Answer the user's question based strictly on this meeting context:

${sessionContext}

User Question: ${query}`;

    const geminiPayload = {
      contents: [{ parts: [{ text: prompt }] }],
    };

    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${GEMINI_API_KEY}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(geminiPayload),
      }
    );

    if (!res.ok) {
      throw new Error("Failed to get answer from Gemini");
    }

    const data = await res.json();
    const answer =
      data.candidates?.[0]?.content?.parts?.[0]?.text ||
      "Unable to answer from meeting context.";

    return NextResponse.json({ answer });
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Failed to process chat query" },
      { status: 500 }
    );
  }
}
