export default async function handler(req, res) {
  if (req.method !== "GET") { res.setHeader("Allow", "GET"); return res.status(405).json({ ok: false, error: "Method not allowed" }); }
  const bridgeUrl = process.env.MT5_BRIDGE_URL, token = process.env.MT5_BRIDGE_TOKEN;
  if (!bridgeUrl || !token) return res.status(500).json({ ok: false, error: "Configuration du pont MT5 manquante" });
  const symbol = String(req.query.symbol || "XAUUSD").toUpperCase();
  const timeframe = String(req.query.timeframe || "M15").toUpperCase();
  const allowedSymbols = new Set(["BTCUSD", "XAUUSD", "EURUSD", "GBPUSD", "USDJPY"]);
  const allowedTimeframes = new Set(["M1", "M5", "M15", "M30", "H1", "H4", "D1"]);
  if (!allowedSymbols.has(symbol)) return res.status(400).json({ ok: false, error: "Symbole non autorisé" });
  if (!allowedTimeframes.has(timeframe)) return res.status(400).json({ ok: false, error: "Timeframe non autorisé" });
  const parsed = Number.parseInt(req.query.count || "200", 10);
  const count = Number.isFinite(parsed) ? Math.min(Math.max(parsed, 50), 500) : 200;
  try {
    const base = bridgeUrl.replace(/\/+$/, "");
    const response = await fetch(base + "/history?symbol=" + encodeURIComponent(symbol) + "&timeframe=" + encodeURIComponent(timeframe) + "&count=" + count, {
      headers: { Authorization: "Bearer " + token }, signal: AbortSignal.timeout(15000), cache: "no-store"
    });
    const body = await response.text(); let data;
    try { data = JSON.parse(body); } catch { data = { details: body.slice(0, 1000) }; }
    if (!response.ok) return res.status(502).json({ ok: false, error: "Historique MT5 indisponible", bridgeStatus: response.status, bridgeDetails: data });
    return res.status(200).json({ ok: true, data });
  } catch { return res.status(502).json({ ok: false, error: "Pont MT5 inaccessible. Vérifie le serveur et le tunnel." }); }
}