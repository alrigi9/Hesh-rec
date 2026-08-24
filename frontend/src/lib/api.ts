import { MeetingSession } from "@/types/meeting";
import { UserProfile, AdminUserRecord, AdminDashboardStats } from "@/types/auth";

const rawApiBase =
  process.env.NEXT_PUBLIC_API_URL !== undefined
    ? process.env.NEXT_PUBLIC_API_URL
    : typeof window !== "undefined" && window.location.hostname !== "localhost"
    ? ""
    : "http://localhost:8000";
const API_BASE = rawApiBase.replace(/\/+$/, "");

async function safeReadResponse(res: Response): Promise<any> {
  const responseText = await res.text();
  let data: any = {};
  try {
    data = JSON.parse(responseText);
  } catch {
    data = { error: responseText || `HTTP ${res.status}: ${res.statusText}` };
  }

  if (!res.ok) {
    throw new Error(
      data.detail || data.error || data.message || `Request failed with status ${res.status}`
    );
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
  token?: string
): Promise<MeetingSession> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("template_type", templateType);
  if (customTitle) formData.append("custom_title", customTitle);
  if (userId) formData.append("user_id", userId);

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}/api/process-audio`, {
    method: "POST",
    headers,
    body: formData,
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
    if (Array.isArray(data)) return data;
    return data.sessions || [];
  } catch (err) {
    console.error("Error fetching sessions:", err);
    return [];
  }
}

export async function fetchSession(id: string): Promise<MeetingSession | null> {
  try {
    const res = await fetch(`${API_BASE}/api/sessions/${encodeURIComponent(id)}`);
    if (!res.ok) return null;
    return await safeReadResponse(res);
  } catch (err) {
    console.error("Error fetching session:", err);
    return null;
  }
}

export const fetchSessionById = fetchSession;

export async function toggleSessionPublic(
  id: string,
  isPublic: boolean
): Promise<boolean> {
  try {
    const res = await fetch(
      `${API_BASE}/api/sessions/${encodeURIComponent(id)}/public?is_public=${isPublic}`,
      { method: "PATCH" }
    );
    return res.ok;
  } catch {
    return false;
  }
}

export const togglePublicSession = toggleSessionPublic;

export async function queryAssistant(
  sessionData: any,
  query: string,
  history: Array<{ role: string; content: string }> = []
): Promise<string> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session: sessionData,
      session_data: sessionData,
      query: query,
      user_query: query,
      messages: history,
      chat_history: history,
    }),
  });

  const data = await safeReadResponse(response);
  return data.answer || "I could not generate an answer for that query.";
}

export const askMeetingAssistant = queryAssistant;

export async function fetchAdminUsers(
  token?: string,
  adminId?: string
): Promise<{ users: AdminUserRecord[]; stats: AdminDashboardStats }> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const url = adminId
    ? `${API_BASE}/api/admin/users?admin_id=${encodeURIComponent(adminId)}`
    : `${API_BASE}/api/admin/users`;

  const res = await fetch(url, { headers });
  return await safeReadResponse(res);
}

export async function updateAdminUserLimit(
  targetUserId: string,
  payload: { monthly_minutes_limit?: number; role?: string },
  token?: string,
  adminId?: string
): Promise<boolean> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // Try App Router endpoint first
  const res = await fetch(`${API_BASE}/api/admin/quota`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      target_user_id: targetUserId,
      monthly_minutes_limit: payload.monthly_minutes_limit,
      admin_id: adminId,
    }),
  });

  return res.ok;
}

export async function resetAdminUserQuota(
  targetUserId: string,
  token?: string,
  adminId?: string
): Promise<boolean> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/admin/reset-quota`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      target_user_id: targetUserId,
      admin_id: adminId,
    }),
  });

  return res.ok;
}

export async function activateAdminUser(
  targetUserId: string,
  token?: string,
  adminId?: string
): Promise<boolean> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/admin/activate`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      target_user_id: targetUserId,
      admin_id: adminId,
    }),
  });

  return res.ok;
}
