/**
 * Server-side Supabase Auth guard for Vercel API routes.
 * Requires SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in Vercel environment variables.
 * The user's access token is verified by Supabase Auth; never trust decoded JWT claims alone.
 */
export default async function requireSupabaseUser(req, res) {
  res.setHeader("Cache-Control", "no-store, max-age=0");

  const projectUrl = process.env.SUPABASE_URL;
  const publishableKey = process.env.SUPABASE_PUBLISHABLE_KEY;
  if (!projectUrl || !publishableKey) {
    res.status(503).json({ ok: false, error: "Authentification non configurée côté serveur" });
    return false;
  }

  const authorization = req.headers?.authorization || "";
  const match = /^Bearer\s+(.+)$/i.exec(authorization);
  if (!match || match[1].length > 8192) {
    res.status(401).json({ ok: false, error: "Authentification requise" });
    return false;
  }

  let authUrl;
  try {
    authUrl = new URL("/auth/v1/user", projectUrl);
    if (authUrl.protocol !== "https:") throw new Error("HTTPS required");
  } catch {
    res.status(503).json({ ok: false, error: "Configuration Supabase invalide" });
    return false;
  }

  try {
    const response = await fetch(authUrl, {
      method: "GET",
      headers: {
        apikey: publishableKey,
        Authorization: `Bearer ${match[1]}`,
        Accept: "application/json"
      },
      cache: "no-store",
      signal: AbortSignal.timeout(8000)
    });
    if (!response.ok) {
      res.status(401).json({ ok: false, error: "Session invalide ou expirée" });
      return false;
    }
    const user = await response.json();
    if (!user || typeof user.id !== "string" || !user.id) {
      res.status(401).json({ ok: false, error: "Session invalide" });
      return false;
    }
    req.supabaseUser = { id: user.id, email: user.email || null };
    return true;
  } catch {
    res.status(503).json({ ok: false, error: "Vérification de session indisponible" });
    return false;
  }
}
