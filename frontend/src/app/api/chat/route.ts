import { NextRequest, NextResponse } from "next/server";
import { GEMINI_API_KEY, GROQ_API_KEY } from "@/lib/server-config";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { session, query, messages = [] } = body;

    if (!query) {
      return NextResponse.json({ error: "Missing query" }, { status: 400 });
    }

    const sessionContext = `Meeting Title: ${session?.title || "Meeting"}
Date: ${session?.meeting_date || session?.date || "N/A"}
Executive Summary: ${session?.executive_summary || session?.summary || session?.tldr || ""}
Discussion Pillars & Decisions: ${JSON.stringify(session?.discussion_pillars || session?.sections || [])}
Action Items: ${JSON.stringify(session?.action_items || [])}
Mind Map Structure: ${session?.mindmap_markdown || ""}
Transcript: ${(session?.transcript_segments || []).map((s: any) => `${s.speaker}: ${s.text}`).join("\n") || session?.transcript || ""}`;

    const prompt = `You are an AI meeting assistant. Answer the user's question clearly and concisely based strictly on this meeting context:

${sessionContext}

User Question: ${query}`;

    let answer = "";

    // 1. Try Gemini 3.6 Flash
    try {
      const geminiPayload = {
        contents: [{ parts: [{ text: prompt }] }],
      };

      const res = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key=${GEMINI_API_KEY}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(geminiPayload),
        }
      );

      if (res.ok) {
        const data = await res.json();
        answer = data.candidates?.[0]?.content?.parts?.[0]?.text || "";
      }
    } catch (err) {
      console.warn("Gemini chat error:", err);
    }

    // 2. Fallback to Groq LLM
    if (!answer && GROQ_API_KEY) {
      try {
        const groqRes = await fetch("https://api.groq.com/openai/v1/chat/completions", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${GROQ_API_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            model: "openai/gpt-oss-120b",
            messages: [
              { role: "system", content: "You are an AI meeting assistant." },
              { role: "user", content: prompt },
            ],
            temperature: 0.3,
          }),
        });

        if (groqRes.ok) {
          const groqData = await groqRes.json();
          answer = groqData.choices?.[0]?.message?.content || "";
        }
      } catch (groqErr) {
        console.warn("Groq chat error:", groqErr);
      }
    }

    if (!answer) {
      answer = "Unable to answer from the provided meeting context.";
    }

    return NextResponse.json({ answer });
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Failed to process chat query" },
      { status: 500 }
    );
  }
}
