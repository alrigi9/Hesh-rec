import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Polishes raw auto-generated filenames / titles (e.g. Upload 20260824 134349 or upload_20260824_134349_soc2)
 * into editorial titles (e.g. "08-24 Meeting: SOC 2 Policy Updates" or "08-24 Meeting Summary").
 */
export function formatMeetingTitle(rawTitle?: string, meetingDate?: string): string {
  if (!rawTitle) return "Meeting Summary";

  let t = rawTitle.trim();

  // Strip file extensions
  t = t.replace(/\.(mp3|wav|m4a|mp4|aac|ogg|flac|json)$/i, "");

  // Match timestamps like Upload 20260824 134349 or upload_20260824_134349_topic
  const tsPattern = /^(?:upload|session)?[ _-]?(\d{4})[-_]?(\d{2})[-_]?(\d{2})[ _-]?(\d{6})?[ _-]*(.*)$/i;
  const match = t.match(tsPattern);

  if (match) {
    const [, , month, day, , restTopic] = match;
    const datePrefix = `${month}-${day} Meeting`;
    const cleanTopic = (restTopic || "").replace(/[_-]+/g, " ").trim();

    if (
      cleanTopic &&
      !["summary", "meeting", "recording", "audio", "notes"].includes(cleanTopic.toLowerCase())
    ) {
      // Capitalize acronyms & words
      const polished = cleanTopic
        .split(" ")
        .map((w) => {
          const upper = w.toUpperCase();
          if (["SOC", "2", "SOC2", "IAM", "MFA", "API", "AWS", "LLM", "PRD", "Q1", "Q2", "Q3", "Q4", "AI", "CI/CD", "SSO"].includes(upper)) {
            if (upper === "SOC2") return "SOC 2";
            return upper;
          }
          return w.charAt(0).toUpperCase() + w.slice(1);
        })
        .join(" ");

      return `${datePrefix}: ${polished}`;
    }

    return `${datePrefix} Summary`;
  }

  // Handle "Upload filename" without timestamp
  if (t.toLowerCase().startsWith("upload ")) {
    t = t.slice(7).replace(/[_-]+/g, " ").trim();
  }

  return t;
}
