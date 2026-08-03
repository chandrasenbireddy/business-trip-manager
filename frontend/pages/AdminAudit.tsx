import { useEffect, useState } from "react";

interface ApprovalEvent {
  event_id: string;
  session_id: string;
  option_id: string | null;
  decision: string;
  shown_snapshot: Record<string, unknown>;
  created_at: string;
}

// Read-only (spec FR-020) — no edit/delete action exists anywhere on this page,
// by design (constitution Principle X).
export default function AdminAudit() {
  const [events, setEvents] = useState<ApprovalEvent[]>([]);

  useEffect(() => {
    fetch("/admin/approval-events", { credentials: "include" })
      .then((r) => r.json())
      .then((body) => setEvents(body.events));
  }, []);

  return (
    <div>
      <h2>Approval audit trail</h2>
      <table>
        <thead>
          <tr>
            <th>When</th>
            <th>Session</th>
            <th>Decision</th>
            <th>Shown</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e) => (
            <tr key={e.event_id}>
              <td>{new Date(e.created_at).toLocaleString()}</td>
              <td>{e.session_id}</td>
              <td>{e.decision}</td>
              <td>{JSON.stringify(e.shown_snapshot)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
