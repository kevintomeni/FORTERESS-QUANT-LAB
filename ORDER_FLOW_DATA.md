# FORTERESS BTC/USD — Order Flow data contract

## Real trade-tape alternative
`GET /api/market/orderflow` reads the public Coinbase Exchange BTC-USD recent-trades endpoint. It computes short-window aggressor buy/sell volume, volume delta in BTC and USD notional, and minute buckets. It is a **recent rolling window**, not a full historical footprint archive.

Coinbase's REST trade `side` is the maker/resting-order side. The implementation explicitly derives aggressor side as the opposite side (maker sell -> aggressive buyer; maker buy -> aggressive seller). This semantic distinction must not be removed.

## Quality gates
- Upstream HTTP status must be successful.
- At least 20 trades; valid positive price/size and parseable timestamp; side must be buy or sell.
- Duplicate trade IDs rejected.
- Latest trade must be no more than 180 seconds old and no more than 30 seconds in the future.
- Upstream failures/stale data return a clear unavailable/stale status; no synthetic fallback.
- No user authentication, account access, private credentials, or order placement.

## Limits
This is Coinbase BTC-USD spot only. It does not represent global crypto flow, any Weltrade CFD/synthetic index, or the MT5 broker tape. Public recent trades do not constitute a deep historical trade archive; historical Order Flow tests require a licensed tick/trade dataset or locally persisted stream with coverage/retention controls. Level 2 order-book data is a different signal and should be implemented separately, not conflated with executed trade delta.

## Signal usage
Do not create a high-confidence setup when this endpoint is stale/unavailable. A full production ICT/OPR strategy still requires documented definitions, unit tests, walk-forward evaluation, out-of-sample data, and independent result checks. The endpoint is data plumbing for that engine, not evidence that strategy performance has been validated.
