import { MeetingSession } from "@/types/meeting";
import { UserProfile, AdminUserRecord, AdminDashboardStats } from "@/types/auth";

const rawApiBase =
  process.env.NEXT_PUBLIC_API_URL !== undefined
    ? process.env.NEXT_PUBLIC_API_URL
    : typeof window !== "undefined" && window.location.hostname !== "localhost"
    ? ""
    : "http://localhost:8000";
const API_BASE = rawApiBase.replace(/\/+$/, "");

function formatErrorMessage(errData: any, status: number, statusText: string): string {
  if (!errData) return `Request failed with status ${status}: ${statusText}`;
  if (typeof errData === "string") return errData;

  // Handle FastAPI validation error list: [{ loc: [...], msg: "...", type: "..." }]
  if (Array.isArray(errData.detail)) {
    const msgs = errData.detail.map((d: any) => d.msg || d.message || JSON.stringify(d)).filter(Boolean);
    if (msgs.length > 0) return msgs.join("; ");
  }

  if (typeof errData.detail === "string" && errData.detail.trim()) {
    return errData.detail;
  }
  if (typeof errData.detail === "object" && errData.detail !== null) {
    return errData.detail.msg || errData.detail.message || errData.detail.detail || JSON.stringify(errData.detail);
  }

  if (typeof errData.error === "string" && errData.error.trim()) {
    return errData.error;
  }
  if (typeof errData.error === "object" && errData.error !== null) {
    return errData.error.message || errData.error.detail || JSON.stringify(errData.error);
  }

  if (typeof errData.message === "string" && errData.message.trim()) {
    return errData.message;
  }

  try {
    return JSON.stringify(errData);
  } catch {
    return `Request failed with status ${status}: ${statusText}`;
  }
}

async function safeReadResponse(res: Response): Promise<any> {
  const responseText = await res.text();
  let data: any = {};
  try {
    data = JSON.parse(responseText);
  } catch {
    data = { error: responseText || `HTTP ${res.status}: ${res.statusText}` };
  }

  if (!res.ok) {
    const errorMsg = formatErrorMessage(data, res.status, res.statusText);
    throw new Error(errorMsg);
  }

  return data;
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    return res.ok;
  } catch {
    return false;
  }
}

export async function fetchUserProfile(
  token?: string,
  userId?: string
): Promise<UserProfile> {
  try {
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const url = userId
      ? `${API_BASE}/api/user/profile?user_id=${encodeURIComponent(userId)}`
      : `${API_BASE}/api/user/profile`;

    const res = await fetch(url, { headers });
    if (!res.ok) {
      return {
        id: userId || "guest",
        email: "guest@recmap.tech",
        role: "user",
        monthly_minutes_limit: 300.0,
        minutes_used_this_month: 0.0,
        minutes_remaining: 300.0,
        percent_used: 0.0,
        can_upload: true,
      };
    }
    return await safeReadResponse(res);
  } catch {
    return {
      id: userId || "guest",
      email: "guest@recmap.tech",
      role: "user",
      monthly_minutes_limit: 300.0,
      minutes_used_this_month: 0.0,
      minutes_remaining: 300.0,
      percent_used: 0.0,
      can_upload: true,
    };
  }
}

export async function processAudioFile(
  file: File,
  templateType: string = "executive",
  customTitle?: string,
  userId?: string,
  token?: string,
  language: string = "auto"
): Promise<MeetingSession> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // If local development backend on localhost:8000, post direct
  if (API_BASE && API_BASE.includes("localhost:8000")) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("template_type", templateType);
    formData.append("language", language);
    if (customTitle) formData.append("custom_title", customTitle);
    if (userId) formData.append("user_id", userId);

    const response = await fetch(`${API_BASE}/api/process-audio`, {
      method: "POST",
      headers,
      body: formData,
    });
    return await safeReadResponse(response);
  }

  // 1. Step 1: Direct High-Speed Speech Transcription
  let transcriptText = "";
  let durationSeconds = 0;
  let formattedSegments: any[] = [];

  // Try direct serverless transcription endpoint (/api/transcribe-direct)
  try {
    const transcribeFormData = new FormData();
    transcribeFormData.append("file", file, file.name);
    transcribeFormData.append("language", language);

    const transcribeRes = await fetch("/api/transcribe-direct", {
      method: "POST",
      body: transcribeFormData,
    });

    if (transcribeRes.ok) {
      const groqData = await transcribeRes.json();
      transcriptText = (groqData.text || "").trim();
      durationSeconds = Number(groqData.duration || 0.0);

      const rawSegments = groqData.segments || [];
      formattedSegments = rawSegments.map((seg: any, idx: number) => ({
        index: idx + 1,
        start: Number(seg.start || 0.0),
        end: Number(seg.end || 0.0),
        timestamp: `${Math.floor(Number(seg.start || 0) / 60).toString().padStart(2, "0")}:${Math.floor(Number(seg.start || 0) % 60).toString().padStart(2, "0")}`,
        speaker: `Speaker ${(idx % 3) + 1}`,
        text: (seg.text || "").trim(),
      }));
    }
  } catch (err) {
    console.warn("Direct transcription endpoint note, falling back to full pipeline:", err);
  }

  // 2. Step 2: Synthesize Meeting Intelligence via /api/process-audio
  const synthFormData = new FormData();
  if (transcriptText) {
    synthFormData.append("transcript_text", transcriptText);
    synthFormData.append("transcript_segments", JSON.stringify(formattedSegments));
    synthFormData.append("duration_seconds", durationSeconds.toString());
  } else {
    // If transcription was not pre-computed, include audio file directly
    synthFormData.append("file", file);
  }
  synthFormData.append("filename", file.name);
  synthFormData.append("template_type", templateType);
  synthFormData.append("language", language);
  if (customTitle) synthFormData.append("custom_title", customTitle);
  if (userId) synthFormData.append("user_id", userId);

  const endpoint = "/api/process-audio";
  const response = await fetch(endpoint, {
    method: "POST",
    headers,
    body: synthFormData,
  });

  return await safeReadResponse(response);
}

export async function fetchSessions(
  userId?: string,
  token?: string
): Promise<MeetingSession[]> {
  try {
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const url = userId
      ? `${API_BASE}/api/sessions?user_id=${encodeURIComponent(userId)}`
      : `${API_BASE}/api/sessions`;

    const res = await fetch(url, { headers });
    if (!res.ok) return [];
    const data = await safeReadResponse(res);
    return Array.isArray(data) ? data : data.sessions || [];
  } catch {
    return [];
  }
}

export async function fetchSessionById(
  id: string,
  token?: string
): Promise<MeetingSession | null> {
  try {
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}/api/sessions/${encodeURIComponent(id)}`, { headers });
    if (!res.ok) return null;
    return await safeReadResponse(res);
  } catch {
    return null;
  }
}

export async function deleteSession(id: string, token?: string): Promise<boolean> {
  try {
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}/api/sessions/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers,
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function updateSessionTitle(
  id: string,
  title: string,
  token?: string
): Promise<boolean> {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}/api/sessions/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ title }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function togglePublicSession(
  id: string,
  isPublic: boolean,
  token?: string
): Promise<boolean> {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}/api/sessions/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ is_public: isPublic }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function askMeetingAssistant(
  session: MeetingSession,
  query: string,
  messages: Array<{ role: string; content: string }> = []
): Promise<string> {
  try {
    const res = await fetch(`/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session, query, messages }),
    });

    const data = await safeReadResponse(res);
    return data.answer || "No response received.";
  } catch (err: any) {
    return `Assistant Error: ${err.message || "Failed to analyze meeting."}`;
  }
}

// ----------------------------------------------------------------------------
// Admin Portal API Helpers
// ----------------------------------------------------------------------------
export async function fetchAdminUsers(
  token?: string,
  adminUserId?: string
): Promise<{ users: AdminUserRecord[]; stats: AdminDashboardStats }> {
  try {
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const url = adminUserId
      ? `/api/admin/users?admin_user_id=${encodeURIComponent(adminUserId)}`
      : `/api/admin/users`;

    const res = await fetch(url, { headers });
    if (!res.ok) {
      return {
        users: [],
        stats: {
          total_users: 0,
          total_minutes_processed: 0,
          average_usage_per_user: 0,
          system_limit_per_user: 300,
        },
      };
    }
    const data = await safeReadResponse(res);
    if (Array.isArray(data)) {
      const totUsers = data.length;
      const totMin = data.reduce((acc: number, u: any) => acc + (u.minutes_used_this_month || 0), 0);
      return {
        users: data,
        stats: {
          total_users: totUsers,
          total_minutes_processed: totMin,
          average_usage_per_user: totUsers > 0 ? Math.round(totMin / totUsers) : 0,
          system_limit_per_user: 300,
        },
      };
    }
    return {
      users: data.users || [],
      stats: data.stats || {
        total_users: 0,
        total_minutes_processed: 0,
        average_usage_per_user: 0,
        system_limit_per_user: 300,
      },
    };
  } catch {
    return {
      users: [],
      stats: {
        total_users: 0,
        total_minutes_processed: 0,
        average_usage_per_user: 0,
        system_limit_per_user: 300,
      },
    };
  }
}

export async function updateAdminUserLimit(
  userId: string,
  updates: { monthly_minutes_limit?: number; role?: string } | number,
  token?: string,
  adminUserId?: string
): Promise<boolean> {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const bodyObj: any = {
      user_id: userId,
      admin_user_id: adminUserId,
    };
    if (typeof updates === "number") {
      bodyObj.monthly_minutes_limit = updates;
    } else if (typeof updates === "object" && updates !== null) {
      if (updates.monthly_minutes_limit !== undefined) bodyObj.monthly_minutes_limit = updates.monthly_minutes_limit;
      if (updates.role !== undefined) bodyObj.role = updates.role;
    }

    const res = await fetch(`/api/admin/quota`, {
      method: "PATCH",
      headers,
      body: JSON.stringify(bodyObj),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function resetAdminUserQuota(
  userId: string,
  token?: string,
  adminUserId?: string
): Promise<boolean> {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`/api/admin/reset-quota`, {
      method: "POST",
      headers,
      body: JSON.stringify({ user_id: userId, admin_user_id: adminUserId }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function activateAdminUser(
  userId: string,
  token?: string,
  adminUserId?: string
): Promise<boolean> {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`/api/admin/activate`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ user_id: userId, admin_user_id: adminUserId, is_active: true }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export const updateUserQuota = updateAdminUserLimit;
export const resetUserMonthlyUsage = resetAdminUserQuota;
export const toggleUserActivation = activateAdminUser;


