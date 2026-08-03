import { useState } from "react";

// spec FR-031: access requires an explicit request — no self-serve signup.
export default function Landing() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "submitted">("idle");

  async function requestAccess() {
    const res = await fetch("/waitlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    if (res.ok) setStatus("submitted");
  }

  return (
    <div>
      <h1>Business Travel Manager</h1>
      <p>Plan, approve, and book a business trip in one conversation.</p>

      {status === "submitted" ? (
        <p>Thanks — we'll email you an invite once your request is approved.</p>
      ) : (
        <div>
          <input type="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
          <button onClick={requestAccess}>Request Access</button>
        </div>
      )}
    </div>
  );
}
