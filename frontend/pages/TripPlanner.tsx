import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { AirbnbReconnectNudge } from "../components/AirbnbBadges";
import { BookingProgress } from "../components/BookingProgress";
import { CategoryProgress } from "../components/CategoryProgress";
import { CostSummary } from "../components/CostSummary";
import { ItineraryReport } from "../components/ItineraryReport";
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
  const [clarifyAnswer, setClarifyAnswer] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [airbnbStatus, setAirbnbStatus] = useState<{ connected: boolean; cookie_status: string } | null>(null);
  const [costSummary, setCostSummary] = useState<{ by_activity: Record<string, number>; total: number } | null>(null);
  const [report, setReport] = useState<{ download_url: string; share_url: string | null; share_expires_at: string | null } | null>(null);

  const { session, refresh } = useSession(sessionId);
  const events = useTripStream(sessionId);

  const calendarConflict = events.find((e) => e.type === "calendar_conflict");
  const airbnbConflict = events.find((e) => e.type === "airbnb_conflict");
  const bookingSteps = events.filter((e) => e.type === "booking_progress");
  const bookingComplete = events.find((e) => e.type === "booking_complete");
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

  useEffect(() => {
    // spec FR-023/024: presented once the session is done — booking_complete
    // is the signal, same as when the confirmation itself finishes.
    if (!bookingComplete || !sessionId) return;
    fetch(`/trips/${sessionId}/cost-summary`, { credentials: "include" })
      .then((r) => r.json())
      .then(setCostSummary);
    fetch(`/trips/${sessionId}/report`, { credentials: "include" })
      .then((r) => r.json())
      .then(setReport);
  }, [bookingComplete, sessionId]);

  async function startTrip() {
    const res = await fetch("/trips", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ description }),
    });
    const body = await res.json();
    // A clarifying question with a session_id (e.g. missing origin) still
    // navigates — the session page shows the question inline. One with no
    // session_id (destination/dates missing) never got far enough to have
    // one, so there's nowhere to navigate to yet.
    if (body.clarifying_question && !body.session_id) setDescription(body.clarifying_question);
    else if (body.session_id) navigate(`/trips/${body.session_id}`);
  }

  async function submitClarification() {
    await fetch(`/trips/${sessionId}/clarify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ answer: clarifyAnswer }),
    });
    setClarifyAnswer("");
    refresh();
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

      {session.status === "awaiting_clarification" && (
        <div className="clarifying-question">
          <p>{session.clarifying_question}</p>
          <input
            value={clarifyAnswer}
            onChange={(e) => setClarifyAnswer(e.target.value)}
            placeholder="e.g. Austin, TX"
          />
          <button onClick={submitClarification} disabled={!clarifyAnswer.trim()}>
            Send
          </button>
        </div>
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

      {costSummary && <CostSummary byActivity={costSummary.by_activity} total={costSummary.total} />}
      {report && (
        <ItineraryReport
          downloadUrl={report.download_url}
          shareUrl={report.share_url}
          shareExpiresAt={report.share_expires_at}
        />
      )}
    </div>
  );
}
