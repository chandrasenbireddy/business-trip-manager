import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { AirbnbReconnectNudge } from "../components/AirbnbBadges";
import { BookingProgress } from "../components/BookingProgress";
import { CategoryProgress } from "../components/CategoryProgress";
import { ItinerarySummary } from "../components/ItinerarySummary";
import { ManualFallback } from "../components/ManualFallback";
import { RejectionPrompt } from "../components/RejectionPrompt";
import { SwipeCard } from "../components/SwipeCard";
import { useSession } from "../hooks/useSession";
import { useTripStream } from "../hooks/useTripStream";

export default function TripPlanner() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [description, setDescription] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [airbnbStatus, setAirbnbStatus] = useState<{ connected: boolean; cookie_status: string } | null>(null);

  const { session, refresh } = useSession(sessionId);
  const events = useTripStream(sessionId);

  const calendarConflict = events.find((e) => e.type === "calendar_conflict");
  const airbnbConflict = events.find((e) => e.type === "airbnb_conflict");
  const bookingSteps = events.filter((e) => e.type === "booking_progress");
  // Most recent manual_fallback per category — a later re-search recovering
  // from a fallback (shouldn't normally happen, but) supersedes the earlier one.
  const fallbackByCategory = Object.fromEntries(
    events.filter((e) => e.type === "manual_fallback").map((e: any) => [e.category, e.best_options])
  );

  useEffect(() => {
    fetch("/users/me/airbnb-status", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then(setAirbnbStatus);
  }, []);

  async function startTrip() {
    const res = await fetch("/trips", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ description }),
    });
    const body = await res.json();
    if (body.session_id) navigate(`/trips/${body.session_id}`);
    else if (body.clarifying_question) setDescription(body.clarifying_question);
  }

  async function decide(optionId: string, decision: "selected" | "rejected") {
    await fetch(`/trips/${sessionId}/options/${optionId}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ decision }),
    });
    refresh();
  }

  async function submitRejection(category: string, reason: string) {
    await fetch(`/trips/${sessionId}/categories/${category}/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ reason }),
    });
    refresh();
  }

  async function confirm() {
    setConfirming(true);
    await fetch(`/trips/${sessionId}/confirm`, { method: "POST", credentials: "include" });
    setConfirming(false);
    refresh();
  }

  async function reconnectAirbnb() {
    await fetch("/users/me/airbnb-reconnect", { method: "POST", credentials: "include" });
  }

  if (!sessionId) {
    return (
      <div>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
        <button onClick={startTrip}>Plan my trip</button>
      </div>
    );
  }

  if (!session) return <div>Loading...</div>;

  return (
    <div>
      {calendarConflict && (
        <div className="calendar-conflict-banner">
          Heads up — you already have something on your calendar during these dates.
        </div>
      )}
      {airbnbConflict && (
        <div className="airbnb-conflict-banner">
          Heads up — you have an existing Airbnb reservation overlapping these dates.
        </div>
      )}
      {airbnbStatus?.connected && airbnbStatus.cookie_status === "expired" && (
        <AirbnbReconnectNudge onReconnect={reconnectAirbnb} />
      )}

      <CategoryProgress categories={session.categories.map((c: any) => ({ name: c.name, status: c.status }))} />

      {session.status === "in_progress" &&
        session.categories.map((c: any) => (
          <section key={c.name}>
            <h3>{c.name}</h3>
            {fallbackByCategory[c.name] ? (
              <ManualFallback category={c.name} bestOptions={fallbackByCategory[c.name]} />
            ) : c.status === "all_rejected" ? (
              <RejectionPrompt category={c.name} onSubmit={submitRejection} />
            ) : (
              c.options
                .filter((o: any) => o.decision === "pending")
                .map((o: any) => <SwipeCard key={o.option_id} option={o} onDecide={decide} />)
            )}
          </section>
        ))}

      {session.status === "awaiting_approval" && !!session.itinerary && (
        <ItinerarySummary itinerary={session.itinerary as any} onConfirm={confirm} confirming={confirming} />
      )}

      {bookingSteps.length > 0 && (
        <BookingProgress steps={bookingSteps.map((e: any) => ({ step: e.step, status: e.status }))} />
      )}
    </div>
  );
}
