interface Props {
  downloadUrl: string;
  shareUrl: string | null;
  shareExpiresAt: string | null;
}

// spec FR-024/025: download always works; the share link is best-effort and
// simply absent (not an error) if the hosted-link upload failed.
export function ItineraryReport({ downloadUrl, shareUrl, shareExpiresAt }: Props) {
  return (
    <div className="itinerary-report">
      <h3>Your trip, to keep</h3>
      <a href={downloadUrl} download>
        Download itinerary
      </a>
      {shareUrl ? (
        <p>
          Share link (expires {shareExpiresAt ? new Date(shareExpiresAt).toLocaleDateString() : ""}):{" "}
          <a href={shareUrl}>{shareUrl}</a>
        </p>
      ) : (
        <p>No share link available right now — the download above always works.</p>
      )}
    </div>
  );
}
