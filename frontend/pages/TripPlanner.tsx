import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { BookingProgress } from "../components/BookingProgress";
import { CategoryProgress } from "../components/CategoryProgress";
import { ItinerarySummary } from "../components/ItinerarySummary";
import { SwipeCard } from "../components/SwipeCard";
import { useSession } from "../hooks/useSession";
import { useTripStream } from "../hooks/useTripStream";

export default function TripPlanner() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [description, setDescription] = useState("");
  const [confirming, setConfirming] = useState(false);

  const { session, refresh } = useSession(sessionId);
  const events = useTripStream(sessionId);

  const calendarConflict = events.find((e) => e.type === "calendar_conflict");
  const bookingSteps = events.filter((e) => e.type === "booking_progress");

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

  async function confirm() {
    setConfirming(true);
    await fetch(`/trips/${sessionId}/confirm`, { method: "POST", credentials: "include" });
    setConfirming(false);
    refresh();
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

      <CategoryProgress
        categories={session.categories.map((c) => ({
          name: c.name,
          status: c.options.some((o: any) => o.decision === "selected")
            ? "selected"
            : c.options.length > 0 && c.options.every((o: any) => o.decision === "rejected")
              ? "all_rejected"
              : "selecting",
        }))}
      />

      {session.status === "in_progress" &&
        session.categories.map((c) => (
          <section key={c.name}>
            <h3>{c.name}</h3>
            {c.options
              .filter((o: any) => o.decision === "pending")
              .map((o: any) => (
                <SwipeCard key={o.option_id} option={o} onDecide={decide} />
              ))}
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
