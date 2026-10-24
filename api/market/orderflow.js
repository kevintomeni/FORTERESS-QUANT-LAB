/**
 * Public BTC-USD trade tape -> read-only Order Flow aggregates.
 * No authentication, account data, order endpoints, or execution logic.
 *
 * Coinbase Exchange GET /products/BTC-USD/trades reports side as MAKER side.
 * Aggressor side is the opposite side: maker sell => buyer aggressed; maker buy => seller aggressed.
 * This endpoint exposes only recent public trades and labels the limited lookback honestly.
 */
const BASE = "https://api.exchange.coinbase.com";
const PRODUCT = "BTC-USD";
const MAX_TRADES = 1000;
const WINDOW_SECONDS = 60;

function json(res, status, body) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store, max-age=0");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.end(JSON.stringify(body));
}
module.exports = async function handler(req, res) {
  if (req.method === "OPTIONS") return json(res, 204, {});
  if (req.method !== "GET") return json(res, 405, { error: "method_not_allowed", message: "GET only" });
  try {
    const u = new URL(req.url, "http://localhost");
    const limit = Math.max(100, Math.min(MAX_TRADES, Number(u.searchParams.get("limit")) || MAX_TRADES));
    const response = await fetch(`${BASE}/products/${PRODUCT}/trades?limit=${limit}`, {
      headers: { Accept: "application/json", "User-Agent": "FORTERESS-QUANT-LAB-readonly/1.0" }
    });
    if (!response.ok) {
      const retry = response.headers.get("Retry-After");
      return json(res, response.status === 429 ? 429 : 502, {
        error: "upstream_market_data_error",
        upstream_status: response.status,
        retry_after: retry,
        source: "Coinbase Exchange public REST",
        message: "Order Flow is unavailable until the upstream trade tape responds successfully."
      });
    }
    const payload = await response.json();
    if (!Array.isArray(payload) || payload.length < 20) {
      return json(res, 502, { error: "invalid_trade_tape", message: "Too few public trades to compute a reliable short-window aggregate." });
    }
    const trades = payload.map(t => {
      const price = Number(t.price), size = Number(t.size), time = Date.parse(t.time) / 1000;
      const makerSide = String(t.side || "").toLowerCase();
      if (!Number.isFinite(price) || price <= 0 || !Number.isFinite(size) || size <= 0 ||
          !Number.isFinite(time) || !["buy", "sell"].includes(makerSide)) {
        throw new Error("Invalid trade fields in upstream payload");
      }
      // Coinbase's side is the resting/maker side, not the aggressor side.
      const aggressor = makerSide === "sell" ? "buy" : "sell";
      return { id: String(t.trade_id), time, price, size, notional: price * size, makerSide, aggressor };
    }).sort((a, b) => a.time - b.time || Number(a.id) - Number(b.id));
    const ids = new Set();
    for (const t of trades) {
      if (ids.has(t.id)) throw new Error("Duplicate trade IDs in upstream payload");
      ids.add(t.id);
    }
    const now = Date.now() / 1000;
    const latest = trades[trades.length - 1];
    const ageSeconds = now - latest.time;
    if (ageSeconds > 180 || ageSeconds < -30) {
      return json(res, 200, {
        ok: false, status: "stale",
        source: "Coinbase Exchange public REST", product: PRODUCT,
        message: "The newest trade is stale or has an invalid future timestamp. No Order Flow signal emitted.",
        latest_trade_time: new Date(latest.time * 1000).toISOString(),
        age_seconds: Math.round(ageSeconds), trade_count: trades.length
      });
    }
    const cutoff = now - WINDOW_SECONDS;
    const recent = trades.filter(t => t.time >= cutoff);
    const summarize = list => {
      const buy = list.filter(t => t.aggressor === "buy");
      const sell = list.filter(t => t.aggressor === "sell");
      const buyVolume = buy.reduce((s, t) => s + t.size, 0);
      const sellVolume = sell.reduce((s, t) => s + t.size, 0);
      const buyNotional = buy.reduce((s, t) => s + t.notional, 0);
      const sellNotional = sell.reduce((s, t) => s + t.notional, 0);
      return {
        trades: list.length, buyAggressorTrades: buy.length, sellAggressorTrades: sell.length,
        buyVolumeBTC: buyVolume, sellVolumeBTC: sellVolume,
        deltaBTC: buyVolume - sellVolume,
        deltaNotionalUSD: buyNotional - sellNotional,
        buyNotionalUSD: buyNotional, sellNotionalUSD: sellNotional,
        buyShare: buyVolume + sellVolume ? buyVolume / (buyVolume + sellVolume) : null
      };
    };
    const buckets = new Map();
    for (const t of trades) {
      const key = Math.floor(t.time / 60) * 60;
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(t);
    }
    const minuteBuckets = [...buckets.entries()].map(([start, list]) => ({
      start: new Date(start * 1000).toISOString(),
      ...summarize(list)
    })).slice(-20);
    return json(res, 200, {
      ok: true, status: "live_recent_tape",
      source: "Coinbase Exchange public REST", product: PRODUCT,
      instrumentType: "spot", interval: "recent trades; one-minute buckets",
      timestamp: new Date().toISOString(),
      latestTradeTime: new Date(latest.time * 1000).toISOString(),
      ageSeconds: Math.round(ageSeconds), receivedTradeCount: trades.length,
      windowSeconds: WINDOW_SECONDS, window: summarize(recent),
      minuteBuckets,
      semantics: {
        upstreamSide: "maker side",
        aggressorSide: "derived as the opposite of maker side",
        delta: "aggressor buy volume minus aggressor sell volume, in BTC",
        caveat: "Exchange-specific tape only; not global BTC market flow, not Weltrade/MT5 CFD flow, and not a complete historical footprint."
      }
    });
  } catch (error) {
    return json(res, 502, {
      ok: false, status: "unavailable",
      source: "Coinbase Exchange public REST",
      error: "order_flow_unavailable",
      message: String(error && error.message || error),
      action: "Do not substitute OHLCV or synthetic values for trade-level Order Flow."
    });
  }
};
