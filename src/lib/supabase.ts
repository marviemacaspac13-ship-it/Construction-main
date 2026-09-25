import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

if (!supabaseUrl || !supabaseAnonKey) {
  console.error(
    "Missing Supabase env vars. Add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to your .env.local file."
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

/**
 * The signed-in session's token, for calls to the FastAPI backend.
 *
 * The backend refuses every /api route without one (backend/app/auth.py),
 * so every fetch there goes through this. Empty when signed out - the
 * backend then answers 401, which is the honest result.
 */
export async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}
