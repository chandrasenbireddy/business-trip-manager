import { useEffect, useState } from "react";

interface Preference {
  type: string;
  value: Record<string, unknown>;
  version: number;
}

const PREFERENCE_TYPES = ["seat", "hotel_proximity", "dietary", "preferred_airline", "budget_pattern"];

export default function Preferences() {
  const [preferences, setPreferences] = useState<Preference[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  async function load() {
    const res = await fetch("/users/me/preferences", { credentials: "include" });
    if (res.ok) setPreferences((await res.json()).preferences);
  }

  useEffect(() => {
    load();
  }, []);

  async function save(type: string) {
    const raw = drafts[type];
    if (!raw) return;
    await fetch(`/users/me/preferences/${type}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ value: JSON.parse(raw) }),
    });
    load();
  }

  return (
    <div>
      <h2>Preferences</h2>
      {/* Editing here is what makes spec Story 3's "applied without restating" possible. */}
      {PREFERENCE_TYPES.map((type) => {
        const current = preferences.find((p) => p.type === type);
        return (
          <div key={type}>
            <label>{type.replace("_", " ")}</label>
            <input
              defaultValue={current ? JSON.stringify(current.value) : ""}
              placeholder='{"seat": "aisle"}'
              onChange={(e) => setDrafts((d) => ({ ...d, [type]: e.target.value }))}
            />
            <button onClick={() => save(type)}>Save</button>
            {current && <span> (v{current.version})</span>}
          </div>
        );
      })}
    </div>
  );
}
