interface Props {
  byActivity: Record<string, number>;
  total: number;
}

// spec FR-023: shown before the traveler leaves — broken down by activity,
// not a single opaque number.
export function CostSummary({ byActivity, total }: Props) {
  return (
    <div className="cost-summary">
      <h3>What this trip cost</h3>
      <ul>
        {Object.entries(byActivity).map(([activity, cost]) => (
          <li key={activity}>
            {activity}: ${cost.toFixed(4)}
          </li>
        ))}
      </ul>
      <p>Total: ${total.toFixed(4)}</p>
    </div>
  );
}
