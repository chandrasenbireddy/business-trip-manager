import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

// spec FR-033: the invite email links here with ?token=...; this page's only
// job is handing that token to the BFF's /auth/login, which redirects to
// Google's single identity+calendar consent screen. The actual session gets
// established server-side in /auth/callback, not here.
export default function Activate() {
  const [params] = useSearchParams();
  const token = params.get("token");

  useEffect(() => {
    if (token) window.location.href = `/auth/login?token=${encodeURIComponent(token)}`;
  }, [token]);

  if (!token) return <div>This invite link is missing its token.</div>;
  return <div>Taking you to sign in...</div>;
}
