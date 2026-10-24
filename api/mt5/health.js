export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store, max-age=0");
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ ok: false, error: "Method not allowed" });
  }
  const base = process.env.MT5_BRIDGE_URL;
  const token = process.env.MT5_BRIDGE_TOKEN;
  if (!base || !token) {
    return res.status(500).json({
      ok: false,
      status: "configuration_missing",
      checks: { urlConfigured: Boolean(base), tokenConfigured: Boolean(token) }
    });
  }
  try {
    const response = await fetch(base.replace(/\\/+$/, "") + "/health", {
      headers: { Authorization: "Bearer " + token, Accept: "application/json" },
      signal: AbortSignal.timeout(8000),
      cache: "no-store"
    });
    const text = await response.text();
    let body;
    try { body = JSON.parse(text); } catch { body = { error: text.slice(0, 250) }; }
    return res.status(response.ok ? 200 : 502).json({
      ok: response.ok && body.ok === true,
      status: response.ok && body.ok === true ? "connected" : "bridge_error",
      upstreamStatus: response.status,
      bridge: body
    });
  } catch (error) {
    return res.status(502).json({
      ok: false,
      status: "bridge_unreachable",
      error: error && (error.name === "TimeoutError" || error.name === "AbortError")
        ? "Bridge timeout"
        : "Bridge unreachable"
    });
  }
}
