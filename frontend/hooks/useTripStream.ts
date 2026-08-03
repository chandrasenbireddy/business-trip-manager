import { useEffect, useRef, useState } from "react";

// Event names per contracts/bff-api.md's SSE event table — kept as a union so
// a consumer's switch/case is exhaustively checked by TypeScript.
export type TripStreamEvent =
  | { type: "calendar_conflict"; conflicts: { event_title: string; start: string; end: string }[] }
  | { type: "airbnb_conflict"; reservations: { listing: unknown; dates: unknown; address: unknown; confirmation_code: string }[] }
  | { type: "research_started"; categories: string[] }
  | { type: "card_ready"; category: string; option: unknown }
  | { type: "category_complete"; category: string; outcome: "selected" | "all_rejected" }
  | { type: "researching_again"; category: string; attempt_number: number }
  | { type: "manual_fallback"; category: string; best_options: unknown[] }
  | { type: "itinerary_ready"; itinerary: unknown; total_cost: number; budget: number }
  | { type: "pending_approval"; approver: string }
  | { type: "booking_progress"; step: "flight" | "accommodation" | "calendar" | "email"; status: string }
  | { type: "booking_complete"; itinerary: unknown; report_url: string }
  | { type: "degraded"; category: string; source: string }
  | { type: "error"; message: string };

export function useTripStream(sessionId: string | undefined) {
  const [events, setEvents] = useState<TripStreamEvent[]>([]);
  const sourceRef = useRef<EventSource>();

  useEffect(() => {
    if (!sessionId) return;

    const source = new EventSource(`/trips/${sessionId}/stream`, { withCredentials: true });
    sourceRef.current = source;

    const eventNames: TripStreamEvent["type"][] = [
      "calendar_conflict",
      "airbnb_conflict",
      "research_started",
      "card_ready",
      "category_complete",
      "researching_again",
      "manual_fallback",
      "itinerary_ready",
      "pending_approval",
      "booking_progress",
      "booking_complete",
      "degraded",
      "error",
    ];
    for (const type of eventNames) {
      source.addEventListener(type, (e: MessageEvent) => {
        setEvents((prev) => [...prev, { type, ...JSON.parse(e.data) }]);
      });
    }

    return () => source.close();
  }, [sessionId]);

  return events;
}
