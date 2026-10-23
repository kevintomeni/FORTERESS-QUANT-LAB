# FORTERESS QUANT LAB — MT5 Engine (paper-only)

This is a development scaffold for a persistent Windows VPS process. It reads market data and computes an illustrative multi-criteria signal, but never sends, modifies, or closes orders.

## Safety
- TRADING_MODE=paper is the only supported mode.
- No mt5.order_send call is implemented.
- Never commit .env or broker passwords/tokens.
- Keep live trading disabled until backtests, demo forward tests, order reconciliation and risk controls are reviewed.

## Windows VPS setup
1. Install the broker's MT5 desktop terminal and sign in to a DEMO account.
2. Install Python 3.11 64-bit and run: py -3.11 -m venv .venv
3. Activate the environment and install: pip install -r requirements.txt
4. Copy .env.example to .env. Do not commit .env.
5. Run python engine.py.

## Scope of this first step
Reads XAUUSD M15 and H1 bars, computes a transparent baseline using EMA trend, a simple 20-bar breakout proxy and ATR, then prints a JSON observation. It does not execute orders. Position reconciliation and daily equity tracking are not implemented, so the risk gate is intentionally hard-locked against execution.

## Next milestones
1. Verify broker-specific symbol name, tick size/value, contract size and timestamps.
2. Add deterministic backtests including spread, commissions, swap and slippage, then out-of-sample validation.
3. Add persistent database/audit log and duplicate-signal protection.
4. Implement demo-only execution with reconciliation against actual MT5 orders.
5. Test disconnects, restart recovery, stale data, order rejection and emergency stop.

The baseline is for engineering tests, not a validated profitable strategy or investment advice.
