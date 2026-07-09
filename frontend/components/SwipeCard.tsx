interface Option {
  option_id: string;
  attributes: Record<string, unknown>;
  badge?: "wishlisted" | "past_stay" | null;
}

interface Props {
  option: Option;
  onDecide: (optionId: string, decision: "selected" | "rejected") => void;
}

export function SwipeCard({ option, onDecide }: Props) {
  return (
    <div className="swipe-card">
      {option.badge && <span className="badge">{option.badge === "wishlisted" ? "⭐ Saved" : "✓ Stayed here"}</span>}
      <pre>{JSON.stringify(option.attributes, null, 2)}</pre>
      <button onClick={() => onDecide(option.option_id, "rejected")}>Skip</button>
      <button onClick={() => onDecide(option.option_id, "selected")}>Approve</button>
    </div>
  );
}
