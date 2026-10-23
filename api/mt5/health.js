
export default async function handler(req, res) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ error: "Method not allowed" });
  }

  const bridgeUrl = process.env.MT5_BRIDGE_URL;
  const token = process.env.MT5_BRIDGE_TOKEN;

  if (!bridgeUrl || !token) {
    return res.status(500).json({
      ok: false,
      error: "Configuration du pont MT5 manquante"
    });
  }

  try {
    const response = await fetch(
      `${bridgeUrl.replace(/\/+$/, "")}/health`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`
        },
        signal: AbortSignal.timeout(10000)
      }
    );

    const body = await response.text();
    let data;
    try { data = JSON.parse(body); } catch { data = { raw: body.slice(0, 1000) }; }
    return res.status(response.ok ? 200 : 502).json({ ok: response.ok, bridgeStatus: response.status, data });
  } catch {
    return res.status(502).json({
      ok: false,
      error: "Pont MT5 inaccessible. Vérifie le serveur et le tunnel."
    });
  }
}
