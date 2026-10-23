export default async function handler(req, res) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ error: "Method not allowed" });
  }

  const bridgeUrl = process.env.MT5_BRIDGE_URL;
  const token = process.env.MT5_BRIDGE_TOKEN;
  if (!bridgeUrl || !token) {
    return res.status(500).json({ ok: false, error: "Configuration du pont MT5 manquante" });
  }

  const parsed = Number.parseInt(req.query.count || "500", 10);
  const count = Number.isFinite(parsed) ? Math.min(Math.max(parsed, 1), 500) : 500;

  try {
    const response = await fetch(
      `${bridgeUrl.replace(/\/+$/, "")}/history/xauusd?count=${count}`,
      {
        headers: { Authorization: `Bearer ${token}` },
        signal: AbortSignal.timeout(15000)
      }
    );
    const body = await response.text();
    let data;
    try { data = JSON.parse(body); } catch { data = { details: body.slice(0, 1000) }; }

    if (!response.ok) {
      return res.status(502).json({ ok: false, error: "Le pont MT5 a refusé la demande", bridgeStatus: response.status });
    }
    return res.status(200).json({ ok: true, data });
  } catch {
    return res.status(502).json({ ok: false, error: "Pont MT5 inaccessible. Vérifie que le serveur et le tunnel sont actifs." });
  }
}
