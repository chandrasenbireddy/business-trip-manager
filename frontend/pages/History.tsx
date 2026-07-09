import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

interface HistoryEntry {
  session_id: string;
  destination: string | null;
  status: string;
  created_at: string;
}

export default function History() {
  const [sessions, setSessions] = useState<HistoryEntry[]>([]);

  useEffect(() => {
    fetch("/trips", { credentials: "include" })
      .then((r) => r.json())
      .then((body) => setSessions(body.sessions));
  }, []);

  return (
    <div>
      <h2>Trip history</h2>
      <ul>
        {sessions.map((s) => (
          <li key={s.session_id}>
            <Link to={`/trips/${s.session_id}`}>
              {s.destination ?? "Untitled trip"} — {s.status} ({new Date(s.created_at).toLocaleDateString()})
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
