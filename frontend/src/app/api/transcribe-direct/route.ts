import { NextRequest, NextResponse } from "next/server";
import { GROQ_API_KEY } from "@/lib/server-config";

export const maxDuration = 60; // 60s serverless timeout

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get("file") as File | null;
    const language = (formData.get("language") as string) || "auto";

    if (!file) {
      return NextResponse.json({ detail: "No audio or video file provided for transcription." }, { status: 400 });
    }

    const groqFormData = new FormData();
    groqFormData.append("file", file, file.name);
    groqFormData.append("model", "whisper-large-v3");
    groqFormData.append("response_format", "verbose_json");
    groqFormData.append("temperature", "0");
    if (language === "ar") {
      groqFormData.append("language", "ar");
    } else if (language === "en") {
      groqFormData.append("language", "en");
    }

    const groqRes = await fetch("https://api.groq.com/openai/v1/audio/transcriptions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${GROQ_API_KEY}`,
      },
      body: groqFormData,
    });

    if (!groqRes.ok) {
      const errText = await groqRes.text();
      return NextResponse.json(
        { detail: `Transcription failed: ${errText}` },
        { status: groqRes.status || 500 }
      );
    }

    const data = await groqRes.json();
    return NextResponse.json(data);
  } catch (err: any) {
    console.error("Transcribe-direct endpoint error:", err);
    return NextResponse.json(
      { detail: err.message || "Internal transcription error" },
      { status: 500 }
    );
  }
}
