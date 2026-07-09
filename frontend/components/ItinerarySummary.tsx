interface Props {
  itinerary: { selections: Record<string, unknown>; total_cost: number; budget: number | null };
  onConfirm: () => void;
  confirming: boolean;
}

// No booking action fires from here directly — onConfirm is the ONLY path to
// POST /trips/{id}/confirm, and that endpoint is the FR-010 enforcement point.
export function ItinerarySummary({ itinerary, onConfirm, confirming }: Props) {
  return (
    <div className="itinerary-summary">
      <h2>Your itinerary</h2>
      <pre>{JSON.stringify(itinerary.selections, null, 2)}</pre>
      <p>
        Total: ${itinerary.total_cost}
        {itinerary.budget != null && ` / budget $${itinerary.budget}`}
      </p>
      <button onClick={onConfirm} disabled={confirming}>
        {confirming ? "Confirming..." : "Confirm and book"}
      </button>
    </div>
  );
}
