interface Step {
  step: "flight" | "accommodation" | "calendar" | "email";
  status: string;
}

// Each step renders independently — a failed calendar write must not hide a
// successful flight booking (spec Edge Cases).
export function BookingProgress({ steps }: { steps: Step[] }) {
  return (
    <ul className="booking-progress">
      {steps.map((s) => (
        <li key={s.step} data-status={s.status}>
          {s.step}: {s.status}
        </li>
      ))}
    </ul>
  );
}
