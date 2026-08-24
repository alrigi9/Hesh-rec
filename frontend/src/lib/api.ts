import { MeetingSession } from "@/types/meeting";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function checkApiHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    return res.ok;
  } catch {
    return false;
  }
}

export async function processAudioFile(
  file: File,
  templateType: string = "executive",
  customTitle?: string,
  userId?: string
): Promise<MeetingSession> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("template_type", templateType);
  if (customTitle) formData.append("custom_title", customTitle);
  if (userId) formData.append("user_id", userId);

  const response = await fetch(`${API_BASE}/api/process-audio`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Audio processing failed: ${errText || response.statusText}`);
  }

  return response.json();
}

export async function fetchSessions(userId?: string): Promise<MeetingSession[]> {
  try {
    const url = userId
      ? `${API_BASE}/api/sessions?user_id=${encodeURIComponent(userId)}`
      : `${API_BASE}/api/sessions`;
    const res = await fetch(url);
    if (!res.ok) return [];
    const data = await res.json();
    return data.sessions || [];
  } catch {
    return [];
  }
}

export async function fetchSessionById(id: string): Promise<MeetingSession | null> {
  try {
    const res = await fetch(`${API_BASE}/api/sessions/${encodeURIComponent(id)}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function togglePublicSession(id: string, isPublic: boolean = true): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/sessions/${encodeURIComponent(id)}/public?is_public=${isPublic}`, {
      method: "PATCH",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function askMeetingAssistant(
  sessionData: MeetingSession,
  query: string,
  history: Array<{ role: string; content: string }> = []
): Promise<string> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_data: sessionData,
      user_query: query,
      chat_history: history,
    }),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Assistant query failed: ${err}`);
  }

  const data = await response.json();
  return data.answer || "I could not generate an answer for that query.";
}
