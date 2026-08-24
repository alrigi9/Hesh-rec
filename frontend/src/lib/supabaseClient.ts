import { createClient } from "@supabase/supabase-js";

function getValidSupabaseConfig() {
  const fallbackUrl = "https://bdgjsmwtxfacgqqhwtzw.supabase.co";
  const fallbackKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJkZ2pzbXd0eGZhY2dxcWh3dHp3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzU1MjI0NSwiZXhwIjoyMTAzMTI4MjQ1fQ.X4zJ5iLD8gyjrcoX8uy0GJwE1eCvPQLMxvNRM1kvHG4";

  let url = (typeof process !== "undefined" && process.env && process.env.NEXT_PUBLIC_SUPABASE_URL) ? process.env.NEXT_PUBLIC_SUPABASE_URL.trim() : "";
  let key = (typeof process !== "undefined" && process.env && (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_KEY)) ? (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_KEY)!.trim() : "";

  if (!url || !url.startsWith("http")) {
    url = fallbackUrl;
  }
  if (!key || key.length < 10) {
    key = fallbackKey;
  }

  return { url, key };
}

const { url: supabaseUrl, key: supabaseAnonKey } = getValidSupabaseConfig();

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: typeof window !== "undefined",
    autoRefreshToken: typeof window !== "undefined",
    detectSessionInUrl: typeof window !== "undefined",
  },
});
