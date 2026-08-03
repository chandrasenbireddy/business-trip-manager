import { useEffect, useState } from "react";

interface CostUsage {
  by_user: Record<string, number>;
  by_agent_type: Record<string, number>;
  total: number;
}

export default function AdminCostUsage() {
  const [usage, setUsage] = useState<CostUsage | null>(null);

  useEffect(() => {
    fetch("/admin/cost-usage", { credentials: "include" })
      .then((r) => r.json())
      .then(setUsage);
  }, []);

  if (!usage) return <div>Loading...</div>;

  return (
    <div>
      <h2>Tenant cost usage</h2>
      <p>Total: ${usage.total.toFixed(4)}</p>

      <h3>By traveler</h3>
      <ul>
        {Object.entries(usage.by_user).map(([userId, cost]) => (
          <li key={userId}>
            {userId}: ${cost.toFixed(4)}
          </li>
        ))}
      </ul>

      <h3>By agent type</h3>
      <ul>
        {Object.entries(usage.by_agent_type).map(([agentType, cost]) => (
          <li key={agentType}>
            {agentType}: ${cost.toFixed(4)}
          </li>
        ))}
      </ul>
    </div>
  );
}
