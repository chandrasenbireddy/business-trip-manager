import { useCallback, useEffect, useState } from "react";

interface SessionState {
  status: string;
  categories: { name: string; status: string; options: unknown[] }[];
  itinerary?: unknown;
  clarifying_question?: string | null;
}

// Snapshot fetch of a trip session — complements useTripStream's live events
// with the current state on first load / after a refresh.
export function useSession(sessionId: string | undefined) {
  const [session, setSession] = useState<SessionState | null>(null);

  const refresh = useCallback(async () => {
    if (!sessionId) return;
    const res = await fetch(`/trips/${sessionId}`, { credentials: "include" });
    setSession(res.ok ? await res.json() : null);
  }, [sessionId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { session, refresh };
}
