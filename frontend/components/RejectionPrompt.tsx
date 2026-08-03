import { useState } from "react";

interface Props {
  category: string;
  onSubmit: (category: string, reason: string) => void;
}

// Shown when a category's current batch is all_rejected (spec FR-007) —
// the reason is passed straight through to the re-search, never discarded.
export function RejectionPrompt({ category, onSubmit }: Props) {
  const [reason, setReason] = useState("");

  return (
    <div className="rejection-prompt">
      <p>None of the {category} options worked — tell me why and I'll look again.</p>
      <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
      <button onClick={() => onSubmit(category, reason)} disabled={!reason.trim()}>
        Search again
      </button>
    </div>
  );
}
