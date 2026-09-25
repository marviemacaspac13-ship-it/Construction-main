import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../../lib/supabase";

/**
 * Renders its children only for a signed-in user; everyone else goes to
 * /sign-in.
 *
 * Until Sep 2026 no route checked (audit finding AUTH-03): a signed-out
 * visitor reached every screen, and since Supabase's row policies return
 * nothing to them, the screens rendered empty instead of saying why.
 *
 * `undefined` means "not known yet" - the stored session is read
 * asynchronously, and redirecting before it arrives would bounce a
 * signed-in user to /sign-in on every refresh.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => sub.subscription.unsubscribe();
  }, []);

  if (session === undefined) return null;
  if (!session) return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}
