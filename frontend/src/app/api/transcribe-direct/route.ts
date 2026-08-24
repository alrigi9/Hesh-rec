import { NextRequest, NextResponse } from "next/server";
import { GROQ_API_KEY } from "@/lib/server-config";

export const maxDuration = 60; // 60s serverless timeout

export async function POST(request: NextRequest) {
  try {
    let fileBlob: Blob | null = null;
    let filename = "recording.m4a";
    let language = "auto";

    const contentType = request.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const jsonBody = await request.json();
      language = jsonBody.language || "auto";
      const fileUrl = jsonBody.file_url || jsonBody.url;
      if (fileUrl) {
        const fileRes = await fetch(fileUrl);
        if (!fileRes.ok) {
          return NextResponse.json({ detail: "Failed to download media file from storage." }, { status: 400 });
        }
        fileBlob = await fileRes.blob();
        filename = jsonBody.filename || "recording.m4a";
      }
    } else {
      const formData = await request.formData();
      const file = formData.get("file") as File | null;
      language = (formData.get("language") as string) || "auto";
      if (file) {
        fileBlob = file;
        filename = file.name || "recording.m4a";
      }
    }

    if (!fileBlob) {
      return NextResponse.json({ detail: "No audio or video file provided for transcription." }, { status: 400 });
    }

    if (!filename.includes(".")) {
      filename += ".m4a";
    }

    const groqFormData = new FormData();
    groqFormData.append("file", fileBlob, filename);
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
        { detail: `Transcription service error: ${errText}` },
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
