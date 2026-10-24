import requireSupabaseUser from "../_lib/require-supabase-user.js";

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store, max-age=0");
  if (!(await requireSupabaseUser(req, res))) return;
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ ok: false, error: "Method not allowed" });
  }
  const bridgeUrl = process.env.MT5_BRIDGE_URL;
  const token = process.env.MT5_BRIDGE_TOKEN;
  if (!bridgeUrl || !token) {
    return res.status(500).json({ ok: false, error: "Configuration du pont MT5 manquante" });
  }
  try {
    const response = await fetch(`${bridgeUrl.replace(/\/+$/, "")}/accounts`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10000),
      cache: "no-store"
    });
    const body = await response.text();
    let data;
    try { data = JSON.parse(body); } catch { data = { error: body.slice(0, 500) }; }
    return res.status(response.ok ? 200 : 502).json(data);
  } catch {
    return res.status(502).json({ ok: false, error: "Pont MT5 inaccessible. Vérifie le serveur et le tunnel privé." });
  }
}
