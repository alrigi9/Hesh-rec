import { MeetingSession } from "@/types/meeting";
import { UserProfile, AdminUserRecord, AdminDashboardStats } from "@/types/auth";
import { supabase } from "@/lib/supabaseClient";

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

  // Normalize mobile filenames (especially iOS voice memos / blobs)
  let safeFilename = file.name || "recording.m4a";
  if (!safeFilename.includes(".")) {
    if (file.type.includes("m4a") || file.type.includes("mp4") || file.type.includes("aac")) {
      safeFilename += ".m4a";
    } else if (file.type.includes("wav")) {
      safeFilename += ".wav";
    } else if (file.type.includes("webm")) {
      safeFilename += ".webm";
    } else {
      safeFilename += ".mp3";
    }
  }

  // 1. Step 1: Direct Client-Side Speech Transcription via Groq Whisper LPU (Fastest, 0 Serverless Hops)
  const groqKey =
    process.env.NEXT_PUBLIC_GROQ_API_KEY ||
    "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";

  let transcriptText = "";
  let durationSeconds = 0;
  let formattedSegments: any[] = [];

  try {
    const groqFormData = new FormData();
    groqFormData.append("file", file, safeFilename);
    groqFormData.append("model", "whisper-large-v3");
    groqFormData.append("response_format", "verbose_json");
    groqFormData.append("temperature", "0");
    if (language === "ar") groqFormData.append("language", "ar");
    if (language === "en") groqFormData.append("language", "en");

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 45000); // 45s client timeout

    const groqRes = await fetch("https://api.groq.com/openai/v1/audio/transcriptions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${groqKey}`,
      },
      body: groqFormData,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (groqRes.ok) {
      const groqData = await groqRes.json();
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
  } catch (groqErr: any) {
    console.warn("Direct Groq client transcription failed or timed out, trying serverless fallback:", groqErr?.message || groqErr);
  }

  // 2. Fallback: Serverless direct transcription or Supabase storage upload for larger files
  if (!transcriptText) {
    try {
      const isUnderVercelLimit = file.size <= 4.2 * 1024 * 1024;

      if (isUnderVercelLimit) {
        // Post directly to /api/transcribe-direct
        const transcribeFormData = new FormData();
        transcribeFormData.append("file", file, safeFilename);
        transcribeFormData.append("language", language);

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 45000);

        const transcribeRes = await fetch("/api/transcribe-direct", {
          method: "POST",
          body: transcribeFormData,
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

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
      } else {
        // Upload to Supabase Storage first, then send URL to /api/transcribe-direct
        const storagePath = `${userId || "guest"}/${Date.now()}_${safeFilename}`;
        const { data: uploadData, error: uploadErr } = await supabase.storage
          .from("recordings")
          .upload(storagePath, file, { contentType: file.type || "audio/mp4", upsert: true });

        if (!uploadErr && uploadData) {
          const { data: urlData } = supabase.storage.from("recordings").getPublicUrl(storagePath);
          const publicUrl = urlData?.publicUrl;

          if (publicUrl) {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 45000);

            const transcribeRes = await fetch("/api/transcribe-direct", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ file_url: publicUrl, filename: safeFilename, language }),
              signal: controller.signal,
            });
            clearTimeout(timeoutId);

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
          }
        }
      }
    } catch (fallbackErr: any) {
      console.warn("Serverless fallback transcription error:", fallbackErr?.message || fallbackErr);
    }
  }

  if (!transcriptText) {
    throw new Error("No audible speech could be extracted. The file may be in an unsupported format, silent, or upload timed out.");
  }

  // 3. Step 3: Send lightweight JSON payload to /api/process-audio for intelligence synthesis
  const synthesisPayload = {
    transcript: transcriptText,
    transcript_text: transcriptText,
    transcript_segments: formattedSegments,
    duration_seconds: durationSeconds,
    filename: safeFilename,
    template: templateType,
    template_type: templateType,
    language,
    custom_title: customTitle,
    user_id: userId,
  };

  const synthController = new AbortController();
  const synthTimeout = setTimeout(() => synthController.abort(), 45000);

  try {
    const response = await fetch("/api/process-audio", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: JSON.stringify(synthesisPayload),
      signal: synthController.signal,
    });
    clearTimeout(synthTimeout);

    return await safeReadResponse(response);
  } catch (err: any) {
    clearTimeout(synthTimeout);
    if (err.name === "AbortError") {
      throw new Error("Analysis timed out after 45 seconds. Please try again with a shorter recording.");
    }
    throw err;
  }
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


