import { MeetingSession } from "@/types/meeting";
import { UserProfile, AdminUserRecord, AdminDashboardStats } from "@/types/auth";

const rawApiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_BASE = rawApiBase.replace(/\/+$/, "");

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
        email: "guest@heshrec.com",
        role: "user",
        monthly_minutes_limit: 300.0,
        minutes_used_this_month: 0.0,
        minutes_remaining: 300.0,
        percent_used: 0.0,
        can_upload: true,
      };
    }
    return await res.json();
  } catch {
    return {
      id: userId || "guest",
      email: "guest@heshrec.com",
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

  if (!response.ok) {
    let errMessage = response.statusText;
    try {
      const errJson = await response.json();
      errMessage = errJson.detail || errMessage;
    } catch {
      const errText = await response.text();
      errMessage = errText || errMessage;
    }
    throw new Error(errMessage);
  }

  return response.json();
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
  if (!res.ok) {
    throw new Error("Failed to fetch admin users directory.");
  }
  return await res.json();
}

export async function updateAdminUserLimit(
  targetUserId: string,
  payload: { monthly_minutes_limit?: number; role?: string },
  token?: string
): Promise<boolean> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/admin/users/${encodeURIComponent(targetUserId)}/limit`, {
    method: "PATCH",
    headers,
    body: JSON.stringify(payload),
  });

  return res.ok;
}

export async function resetAdminUserQuota(
  targetUserId: string,
  token?: string
): Promise<boolean> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/admin/users/${encodeURIComponent(targetUserId)}/reset-quota`, {
    method: "PATCH",
    headers,
  });

  return res.ok;
}
