"""
FORTERESS QUANT LAB — secure, read-only MetaTrader 5 bridge.
Runs on Windows beside the MT5 terminal. It never submits, modifies, or closes orders.
"""
from __future__ import annotations

import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import MetaTrader5 as mt5
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="FORTERESS MT5 Read-only Bridge", version="1.0.0")
BRIDGE_TOKEN = os.getenv("MT5_BRIDGE_TOKEN", "").strip()
MT5_PATH = os.getenv("MT5_TERMINAL_PATH", "").strip()
DEFAULT_SYMBOL = os.getenv("MT5_DEFAULT_SYMBOL", "XAUUSD").strip().upper()
TIMEFRAME = mt5.TIMEFRAME_M15


def require_token(authorization: str | None = Header(default=None)) -> None:
    if not BRIDGE_TOKEN or len(BRIDGE_TOKEN) < 32:
        raise HTTPException(status_code=503, detail="Bridge token not configured (minimum 32 characters)")
    expected = f"Bearer {BRIDGE_TOKEN}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def ensure_mt5() -> None:
    ok = mt5.initialize(path=MT5_PATH) if MT5_PATH else mt5.initialize()
    if not ok:
        err = mt5.last_error()
        raise HTTPException(status_code=503, detail=f"MetaTrader 5 unavailable: {err}")
    info = mt5.terminal_info()
    if info is None or not info.connected:
        mt5.shutdown()
        raise HTTPException(status_code=503, detail="MT5 terminal is not connected to the broker")


def number(value: Any) -> float | None:
    try:
        v = float(value)
        return v if v == v and abs(v) != float("inf") else None
    except (TypeError, ValueError):
        return None


def iso_time(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def symbol_or_error(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not symbol or len(symbol) > 32 or not all(c.isalnum() or c in "._-" for c in symbol):
        raise HTTPException(status_code=400, detail="Invalid symbol")
    info = mt5.symbol_info(symbol)
    if info is None:
        # Do not silently substitute a broker-specific symbol.
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found in this MT5 terminal")
    if not info.visible and not mt5.symbol_select(symbol, True):
        raise HTTPException(status_code=503, detail=f"Could not enable symbol {symbol}")
    return symbol


def run_read(fn):
    ensure_mt5()
    try:
        return fn()
    finally:
        mt5.shutdown()


@app.get("/health")
def health(_: None = Depends(require_token)):
    def read():
        account = mt5.account_info()
        terminal = mt5.terminal_info()
        if account is None:
            raise HTTPException(status_code=503, detail=f"MT5 account unavailable: {mt5.last_error()}")
        return {"ok": True, "service": "forteress-mt5-bridge", "version": "1.0.0",
                "connected": bool(terminal and terminal.connected),
                "account_login": int(account.login), "server": account.server,
                "observed_at": datetime.now(timezone.utc).isoformat(), "read_only": True}
    return run_read(read)


@app.get("/accounts")
def accounts(_: None = Depends(require_token)):
    def read():
        a = mt5.account_info()
        if a is None:
            raise HTTPException(status_code=503, detail=f"MT5 account unavailable: {mt5.last_error()}")
        return {"ok": True, "account": {
            "connected": True, "is_connected": True, "login": int(a.login),
            "server": str(a.server or ""), "company": str(a.company or ""),
            "currency": str(a.currency or "EUR"), "name": str(getattr(a, "name", "") or ""),
            "account_name": str(getattr(a, "name", "") or ""),
            "balance": number(a.balance), "equity": number(a.equity),
            "profit": number(a.profit), "floating_profit": number(a.profit),
            "margin": number(a.margin), "margin_free": number(a.margin_free),
            "free_margin": number(a.margin_free), "margin_level": number(a.margin_level)}}
    return run_read(read)


@app.get("/positions")
def positions(_: None = Depends(require_token)):
    def read():
        rows = mt5.positions_get()
        if rows is None:
            raise HTTPException(status_code=503, detail=f"MT5 positions unavailable: {mt5.last_error()}")
        data = []
        for p in rows:
            data.append({"ticket": int(p.ticket), "position_id": int(p.identifier),
                "symbol": p.symbol, "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                "side": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                "volume": number(p.volume), "price_open": number(p.price_open),
                "price_current": number(p.price_current), "profit": number(p.profit),
                "swap": number(p.swap), "sl": number(p.sl), "tp": number(p.tp),
                "time": iso_time(p.time)})
        return {"ok": True, "positions": data, "count": len(data),
                "observed_at": datetime.now(timezone.utc).isoformat(), "read_only": True}
    return run_read(read)


@app.get("/deals")
def deals(days: int = Query(default=30, ge=1, le=90),
          count: int = Query(default=100, ge=1, le=500),
          _: None = Depends(require_token)):
    def read():
        end = datetime.now()
        start = end - timedelta(days=days)
        rows = mt5.history_deals_get(start, end)
        if rows is None:
            raise HTTPException(status_code=503, detail=f"MT5 deal history unavailable: {mt5.last_error()}")
        rows = list(rows)[-count:][::-1]
        data = []
        for d in rows:
            info = mt5.symbol_info(d.symbol) if d.symbol else None
            data.append({"ticket": int(d.ticket), "deal": int(d.ticket),
                "order": int(d.order), "position_id": int(d.position_id),
                "symbol": d.symbol or "", "type": str(d.type), "entry": str(d.entry),
                "volume": number(d.volume), "price": number(d.price),
                "profit": number(d.profit), "commission": number(d.commission),
                "swap": number(d.swap), "fee": number(getattr(d, "fee", 0)),
                "time": iso_time(d.time), "time_msc": int(d.time_msc),
                "currency_digits": int(info.digits) if info else None})
        return {"ok": True, "deals": data, "count": len(data), "days": days,
                "observed_at": datetime.now(timezone.utc).isoformat(), "read_only": True}
    return run_read(read)


@app.get("/quote")
def quote(symbol: str = Query(default=DEFAULT_SYMBOL, min_length=3, max_length=20),
          _: None = Depends(require_token)):
    def read():
        sym = symbol_or_error(symbol)
        tick = mt5.symbol_info_tick(sym)
        if tick is None:
            raise HTTPException(status_code=503, detail=f"No tick available for {sym}: {mt5.last_error()}")
        bid, ask = number(tick.bid), number(tick.ask)
        return {"ok": True, "symbol": sym, "bid": bid, "ask": ask,
                "mid": ((bid + ask) / 2) if bid is not None and ask is not None else None,
                "last": number(tick.last), "spread": (ask - bid) if bid is not None and ask is not None else None,
                "time": iso_time(tick.time), "timestamp": int(tick.time),
                "time_msc": int(tick.time_msc),
                "observed_at": datetime.now(timezone.utc).isoformat(), "read_only": True}
    return run_read(read)


@app.get("/history/xauusd")
def history(count: int = Query(default=500, ge=100, le=500),
            _: None = Depends(require_token)):
    def read():
        sym = symbol_or_error(DEFAULT_SYMBOL)
        rates = mt5.copy_rates_from_pos(sym, TIMEFRAME, 0, count)
        if rates is None:
            raise HTTPException(status_code=503, detail=f"MT5 history unavailable: {mt5.last_error()}")
        bars = [{"time": iso_time(r["time"]), "timestamp": int(r["time"]),
                 "open": number(r["open"]), "high": number(r["high"]),
                 "low": number(r["low"]), "close": number(r["close"]),
                 "tick_volume": int(r["tick_volume"]), "spread": int(r["spread"]),
                 "real_volume": int(r["real_volume"])} for r in rates]
        return {"ok": True, "symbol": sym, "timeframe": "M15", "bars": bars,
                "count": len(bars), "observed_at": datetime.now(timezone.utc).isoformat(),
                "read_only": True}
    return run_read(read)


@app.get("/signals")
def signals(_: None = Depends(require_token)):
    # Descriptive SMA trend only. This endpoint does not place trades or promise outcomes.
    def read():
        sym = symbol_or_error(DEFAULT_SYMBOL)
        rates = mt5.copy_rates_from_pos(sym, TIMEFRAME, 0, 30)
        if rates is None or len(rates) < 21:
            raise HTTPException(status_code=503, detail="Not enough M15 history to calculate the SMA trend")
        closes = [float(r["close"]) for r in rates]
        sma8 = sum(closes[-8:]) / 8
        sma21 = sum(closes[-21:]) / 21
        direction = "BULLISH" if sma8 > sma21 else "BEARISH" if sma8 < sma21 else "NEUTRAL"
        return {"ok": True, "signal": {"direction": direction, "status": "SMA_TREND_ONLY",
            "reason": f"Trend descriptif M15 : SMA 8={sma8:.5f}, SMA 21={sma21:.5f}. Ce n'est pas un conseil ni une garantie.",
            "price": closes[-1], "reference_price": closes[-1],
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "sma8": sma8, "sma21": sma21}, "read_only": True}
    return run_read(read)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code,
                        content={"ok": False, "error": str(exc.detail), "read_only": True})
