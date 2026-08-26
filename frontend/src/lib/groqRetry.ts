/**
 * Utility to execute async API calls (such as Groq Whisper, Groq LLaMA, or Gemini)
 * with exponential backoff retry logic specifically handling rate limits (429) and transient errors (500, 502, 503, 504).
 */
export async function callWithRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 3,
  baseDelayMs = 2000
): Promise<T> {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err: any) {
      const status = Number(err?.status || err?.statusCode || 0);
      const msg = String(err?.message || "").toLowerCase();
      const errText = String(err?.detail || err?.error || "").toLowerCase();

      const isRateLimit =
        status === 429 ||
        msg.includes("429") ||
        msg.includes("rate limit") ||
        msg.includes("too many requests") ||
        errText.includes("rate_limit_exceeded") ||
        errText.includes("429");

      const isTransient =
        status === 500 ||
        status === 502 ||
        status === 503 ||
        status === 504 ||
        msg.includes("503") ||
        msg.includes("fetch failed") ||
        msg.includes("econnreset") ||
        msg.includes("network error") ||
        msg.includes("socket hang up");

      if ((!isRateLimit && !isTransient) || attempt === maxRetries) {
        console.error(`[callWithRetry] Giving up after attempt ${attempt + 1}/${maxRetries + 1}:`, err);
        throw err;
      }

      // Exponential backoff: 2s, 4s, 8s (+ jitter)
      const delay = Math.round(baseDelayMs * Math.pow(2, attempt) + Math.random() * 500);
      console.warn(
        `[callWithRetry] Rate limit or transient error detected (status: ${status || "unknown"}). Retrying attempt ${
          attempt + 1
        }/${maxRetries} after ${delay}ms...`
      );
      await new Promise((res) => setTimeout(res, delay));
    }
  }
  throw new Error("callWithRetry unreachable");
}
