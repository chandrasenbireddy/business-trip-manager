import { useEffect, useState } from "react";

interface Policy {
  max_flight_budget: number | null;
  max_hotel_budget_per_night: number | null;
  approved_airlines: string[];
  approval_threshold: number | null;
  approver_email: string | null;
}

export default function AdminPolicy() {
  const [policy, setPolicy] = useState<Partial<Policy>>({});

  async function load() {
    const res = await fetch("/admin/policy", { credentials: "include" });
    if (res.ok) setPolicy((await res.json()).policy);
  }

  useEffect(() => {
    load();
  }, []);

  async function save() {
    const res = await fetch("/admin/policy", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(policy),
    });
    if (res.ok) setPolicy((await res.json()).policy);
  }

  return (
    <div>
      <h2>Organization travel policy</h2>
      <label>
        Max flight budget
        <input
          type="number"
          value={policy.max_flight_budget ?? ""}
          onChange={(e) => setPolicy((p) => ({ ...p, max_flight_budget: Number(e.target.value) }))}
        />
      </label>
      <label>
        Max nightly hotel budget
        <input
          type="number"
          value={policy.max_hotel_budget_per_night ?? ""}
          onChange={(e) => setPolicy((p) => ({ ...p, max_hotel_budget_per_night: Number(e.target.value) }))}
        />
      </label>
      <label>
        Approved airlines (comma-separated)
        <input
          value={(policy.approved_airlines ?? []).join(", ")}
          onChange={(e) =>
            setPolicy((p) => ({ ...p, approved_airlines: e.target.value.split(",").map((a) => a.trim()) }))
          }
        />
      </label>
      <label>
        Approval threshold
        <input
          type="number"
          value={policy.approval_threshold ?? ""}
          onChange={(e) => setPolicy((p) => ({ ...p, approval_threshold: Number(e.target.value) }))}
        />
      </label>
      <label>
        Designated approver email
        <input
          value={policy.approver_email ?? ""}
          onChange={(e) => setPolicy((p) => ({ ...p, approver_email: e.target.value }))}
        />
      </label>
      <button onClick={save}>Save policy</button>
    </div>
  );
}
