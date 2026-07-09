// spec FR-028: visual badges for wishlisted / previously-stayed listings.
export function AirbnbBadge({ badge }: { badge: "wishlisted" | "past_stay" | null | undefined }) {
  if (!badge) return null;
  return <span className="airbnb-badge">{badge === "wishlisted" ? "⭐ Saved" : "✓ Stayed here"}</span>;
}

// spec FR-029: shown when the connected Airbnb account's session has expired —
// never blocks the trip request, just nudges toward reconnecting.
export function AirbnbReconnectNudge({ onReconnect }: { onReconnect: () => void }) {
  return (
    <div className="airbnb-reconnect-nudge">
      <span>Your Airbnb account session expired — showing anonymous results.</span>
      <button onClick={onReconnect}>Reconnect</button>
    </div>
  );
}
