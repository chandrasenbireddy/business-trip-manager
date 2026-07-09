import { useCallback, useEffect, useState } from "react";

interface AuthUser {
  userId: string;
  tenantId: string;
  isAdmin: boolean;
}

// Session lives in an httpOnly cookie (btm_session) — never read/stored in JS.
// This hook only asks the BFF "who am I" and reacts to 401s.
export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const res = await fetch("/users/me", { credentials: "include" });
    if (!res.ok) {
      setUser(null);
    } else {
      const body = await res.json();
      setUser({ userId: body.user_id, tenantId: body.tenant_id, isAdmin: body.is_admin });
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { user, loading, refresh };
}
