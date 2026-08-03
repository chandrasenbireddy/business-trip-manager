interface Option {
  option_id: string;
  attributes: Record<string, unknown>;
}

interface Props {
  category: string;
  bestOptions: Option[];
}

// Shown once the 3-attempt reject cap is hit (spec FR-008) — the best options
// found across all attempts, plus a link out to search manually.
export function ManualFallback({ category, bestOptions }: Props) {
  return (
    <div className="manual-fallback">
      <p>
        I couldn't find a {category} option that worked after 3 tries. Here's the best of what I found —
        or search yourself:
      </p>
      <ul>
        {bestOptions.map((o) => (
          <li key={o.option_id}>{JSON.stringify(o.attributes)}</li>
        ))}
      </ul>
      <a
        href={category === "flight" ? "https://www.google.com/travel/flights" : "https://www.airbnb.com/s/"}
        target="_blank"
        rel="noreferrer"
      >
        Search {category} manually
      </a>
    </div>
  );
}
