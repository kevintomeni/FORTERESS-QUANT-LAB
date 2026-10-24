// Read-only public BTC-USD market data proxy. No order execution.
const BASE = "https://api.exchange.coinbase.com";
export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store, max-age=0");
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ ok: false, status: "unavailable", error: "Method not allowed" });
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const [tickerResponse, candlesResponse] = await Promise.all([
      fetch(BASE + "/products/BTC-USD/ticker", {
        headers: { Accept: "application/json", "User-Agent": "FORTERESS-QUANT-LAB/1.0" },
        signal: controller.signal,
        cache: "no-store"
      }),
      fetch(BASE + "/products/BTC-USD/candles?granularity=900", {
        headers: { Accept: "application/json", "User-Agent": "FORTERESS-QUANT-LAB/1.0" },
        signal: controller.signal,
        cache: "no-store"
      })
    ]);
    if (!tickerResponse.ok || !candlesResponse.ok) {
      return res.status(502).json({
        ok: false, status: "unavailable",
        error: "Coinbase public API returned a non-success status",
        upstream: { ticker: tickerResponse.status, candles: candlesResponse.status },
        source: "Coinbase Exchange BTC-USD"
      });
    }
    const [ticker, rawCandles] = await Promise.all([tickerResponse.json(), candlesResponse.json()]);
    const price = Number(ticker.price);
    const bid = Number(ticker.bid);
    const ask = Number(ticker.ask);
    if (![price, bid, ask].every(Number.isFinite) || price <= 0 || bid <= 0 || ask <= 0 ||
        !Array.isArray(rawCandles) || rawCandles.length < 30) {
      return res.status(502).json({ ok: false, status: "invalid", error: "Invalid market payload", source: "Coinbase Exchange BTC-USD" });
    }
    const bars = rawCandles
      .map(row => ({ time: Number(row[0]), low: Number(row[1]), high: Number(row[2]), open: Number(row[3]), close: Number(row[4]), volume: Number(row[5]) }))
      .sort((a, b) => a.time - b.time);
    for (let i = 0; i < bars.length; i++) {
      const b = bars[i];
      if (![b.time, b.low, b.high, b.open, b.close, b.volume].every(Number.isFinite) ||
          b.time <= 0 || Math.min(b.low, b.high, b.open, b.close) <= 0 ||
          b.high < Math.max(b.open, b.close, b.low) || b.low > Math.min(b.open, b.close, b.high) ||
          (i > 0 && b.time <= bars[i - 1].time)) {
        return res.status(502).json({ ok: false, status: "invalid", error: "OHLC validation failed", source: "Coinbase Exchange BTC-USD" });
      }
    }
    const now = Date.now() / 1000;
    const lastBar = bars[bars.length - 1];
    const quoteTime = Number(ticker.time ? Date.parse(ticker.time) / 1000 : now);
    const quoteAgeSeconds = now - quoteTime;
    const candleAgeSeconds = now - (lastBar.time + 900);
    if (!Number.isFinite(quoteAgeSeconds) || quoteAgeSeconds < -30 || quoteAgeSeconds > 120 ||
        candleAgeSeconds < -900 || candleAgeSeconds > 3600) {
      return res.status(503).json({
        ok: false, status: "stale", error: "Market data is stale; no synthetic fallback is used",
        source: "Coinbase Exchange BTC-USD", quoteAgeSeconds: Math.round(quoteAgeSeconds),
        candleAgeSeconds: Math.round(candleAgeSeconds)
      });
    }
    return res.status(200).json({
      ok: true, status: "live", source: "Coinbase Exchange public API",
      product: "BTC-USD", quoteTime: ticker.time || new Date().toISOString(),
      quoteAgeSeconds: Math.max(0, Math.round(quoteAgeSeconds)),
      price, bid, ask, spread: ask - bid,
      candles: { intervalSeconds: 900, count: bars.length, latestTime: lastBar.time, ageSeconds: Math.max(0, Math.round(candleAgeSeconds)), data: bars }
    });
  } catch (error) {
    const timeoutError = error && error.name === "AbortError";
    return res.status(502).json({
      ok: false, status: "unavailable",
      error: timeoutError ? "Market provider timed out" : "Could not fetch public market data",
      source: "Coinbase Exchange BTC-USD"
    });
  } finally {
    clearTimeout(timeout);
  }
}
