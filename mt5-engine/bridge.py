"""Authenticated read-only status bridge for the currently logged-in MT5 terminal."""
import json
import os
import time
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen

import MetaTrader5 as mt5

HOST = os.getenv("MT5_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.getenv("MT5_BRIDGE_PORT", "8765"))
TOKEN = os.getenv("MT5_BRIDGE_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SIGNAL_TIMEFRAME = mt5.TIMEFRAME_M15
_last_signal_key = None
_signal_lock = threading.Lock()


def account_status():
    terminal = mt5.terminal_info()
    account = mt5.account_info()
    if terminal is None or account is None:
        return {"connected": False, "error": "MT5 non initialisé ou aucun compte connecté",
                "mt5_error": str(mt5.last_error())}
    return {
        "connected": bool(terminal.connected),
        "company": getattr(account, "company", None),
        "server": getattr(account, "server", None),
        "login": int(account.login),
        "name": getattr(account, "name", None),
        "currency": getattr(account, "currency", None),
        "leverage": int(account.leverage),
        "balance": float(account.balance),
        "equity": float(account.equity),
        "profit": float(account.profit),
        "margin": float(account.margin),
        "margin_free": float(account.margin_free),
        "read_only": True,
        "observed_at": datetime.now(timezone.utc).isoformat()
    }



def calculate_signal():
    """Read-only SMA crossover on closed MT5 M15 bars; never places orders."""
    symbol = os.getenv("MT5_SIGNAL_SYMBOL", "XAUUSD").upper()
    info = mt5.symbol_info(symbol)
    if info is None:
        return {"ok": False, "status": "symbol_unavailable", "error": "Symbole MT5 introuvable", "symbol": symbol}
    if not info.visible and not mt5.symbol_select(symbol, True):
        return {"ok": False, "status": "symbol_unavailable", "error": "Impossible d'activer le symbole", "symbol": symbol}
    rates = mt5.copy_rates_from_pos(symbol, SIGNAL_TIMEFRAME, 1, 60)
    if rates is None or len(rates) < 22:
        return {"ok": False, "status": "history_unavailable", "error": "Historique M15 insuffisant", "mt5_error": str(mt5.last_error())}
    closes = [float(r["close"]) for r in rates]
    def sma(values, n):
        return sum(values[-n:]) / n
    # Compare the two most recent closed candles without using the forming candle.
    fast_prev, slow_prev = sma(closes[:-1], 8), sma(closes[:-1], 21)
    fast_now, slow_now = sma(closes, 8), sma(closes, 21)
    side = "BUY" if fast_prev <= slow_prev and fast_now > slow_now else "SELL" if fast_prev >= slow_prev and fast_now < slow_now else "NONE"
    candle_time = int(rates[-1]["time"])
    tick = mt5.symbol_info_tick(symbol)
    tick_time = int(tick.time) if tick else 0
    quote_age = max(0, int(time.time()) - tick_time) if tick_time else None
    fresh = quote_age is not None and quote_age <= 1800 and tick is not None and tick.bid > 0 and tick.ask > 0
    return {
        "ok": True, "symbol": symbol, "timeframe": "M15", "strategy": "SMA 8/21 crossover",
        "signal": side if fresh else "NONE",
        "reason": "Croisement confirmé sur bougie clôturée" if side != "NONE" and fresh else ("Cotations MT5 trop anciennes : aucun signal envoyé" if not fresh else "Aucun nouveau croisement"),
        "fast_sma": round(fast_now, int(info.digits)), "slow_sma": round(slow_now, int(info.digits)),
        "last_closed_candle_time": datetime.fromtimestamp(candle_time, timezone.utc).isoformat(),
        "bid": float(tick.bid) if tick else None, "ask": float(tick.ask) if tick else None,
        "quote_time": datetime.fromtimestamp(tick_time, timezone.utc).isoformat() if tick_time else None,
        "quote_age_seconds": quote_age, "fresh": fresh, "read_only": True,
        "observed_at": datetime.now(timezone.utc).isoformat()
    }


def send_telegram_signal(signal):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    message = (
        f"FORTERESS QUANT LAB — SIGNAL {signal['signal']}\n"
        f"{signal['symbol']} · {signal['timeframe']}\n"
        f"Stratégie : {signal['strategy']}\n"
        f"Bid/Ask : {signal['bid']} / {signal['ask']}\n"
        f"Bougie clôturée UTC : {signal['last_closed_candle_time']}\n"
        "Flux frais : oui\nMode : signal uniquement — aucun ordre envoyé"
    )
    payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode("utf-8")
    request = Request("https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage",
                      data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=8) as response:
            return 200 <= response.status < 300
    except Exception as exc:
        print(f"Telegram notification failed: {exc}")
        return False


def signal_watcher():
    global _last_signal_key
    while True:
        try:
            if mt5.initialize():
                result = calculate_signal()
                if result.get("ok") and result.get("fresh") and result.get("signal") in ("BUY", "SELL"):
                    key = f"{result['symbol']}:{result['timeframe']}:{result['last_closed_candle_time']}:{result['signal']}"
                    with _signal_lock:
                        if key != _last_signal_key and send_telegram_signal(result):
                            _last_signal_key = key
                            print(f"Telegram signal sent: {key}")
        except Exception as exc:
            print(f"Signal watcher error: {exc}")
        time.sleep(15)

class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not TOKEN or self.headers.get("Authorization") != "Bearer " + TOKEN:
            return self.send_json(401, {"ok": False, "error": "Unauthorized"})
        path = urlparse(self.path).path
        if path == "/signals":
            if not mt5.initialize():
                return self.send_json(503, {"ok": False, "error": "MT5 initialize failed", "mt5_error": str(mt5.last_error())})
            result = calculate_signal()
            return self.send_json(200 if result.get("ok") else 503, result)
        if path in ("/health", "/accounts"):
            if not mt5.initialize():
                return self.send_json(503, {"ok": False, "error": "MT5 initialize failed",
                                            "mt5_error": str(mt5.last_error())})
            account = account_status()
            return self.send_json(200 if account.get("connected") else 503,
                                  {"ok": bool(account.get("connected")), "account": account})
        if not mt5.initialize():
            return self.send_json(503, {"ok": False, "error": "MT5 initialize failed",
                                        "mt5_error": str(mt5.last_error())})
        if path == "/quote":
            query = parse_qs(urlparse(self.path).query)
            symbol = (query.get("symbol", ["XAUUSD"])[0] or "XAUUSD").upper()
            info = mt5.symbol_info(symbol)
            if info is None:
                return self.send_json(404, {"ok": False, "error": "Symbole MT5 introuvable", "symbol": symbol})
            if not info.visible and not mt5.symbol_select(symbol, True):
                return self.send_json(503, {"ok": False, "error": "Impossible d'activer le symbole", "symbol": symbol})
            tick = mt5.symbol_info_tick(symbol)
            if tick is None or not tick.bid or not tick.ask:
                return self.send_json(503, {"ok": False, "error": "Cotation Bid/Ask indisponible", "symbol": symbol,
                                            "mt5_error": str(mt5.last_error())})
            return self.send_json(200, {"ok": True, "symbol": symbol, "bid": float(tick.bid),
                "ask": float(tick.ask), "last": float(getattr(tick, "last", 0) or 0),
                "time": int(tick.time), "time_utc": datetime.fromtimestamp(tick.time, timezone.utc).isoformat(),
                "digits": int(info.digits), "spread_points": int(info.spread), "read_only": True})
        if path == "/positions":
            items = mt5.positions_get()
            if items is None:
                return self.send_json(503, {"ok": False, "error": "Positions indisponibles",
                                            "mt5_error": str(mt5.last_error())})
            rows = []
            account = mt5.account_info()
            for p in items:
                rows.append({"ticket": int(p.ticket), "time": int(p.time), "symbol": p.symbol,
                    "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                    "volume": float(p.volume), "price_open": float(p.price_open), "price_current": float(p.price_current),
                    "sl": float(p.sl), "tp": float(p.tp), "profit": float(p.profit), "swap": float(p.swap),
                    "commission": float(getattr(p, "commission", 0) or 0), "magic": int(p.magic),
                    "comment": str(p.comment), "currency": getattr(account, "currency", None)})
            return self.send_json(200, {"ok": True, "count": len(rows), "positions": rows,
                                        "observed_at": datetime.now(timezone.utc).isoformat(), "read_only": True})
        if path == "/deals":
            query = parse_qs(urlparse(self.path).query)
            try:
                days = max(1, min(90, int(query.get("days", ["30"])[0])))
                count = max(1, min(500, int(query.get("count", ["100"])[0])))
            except ValueError:
                days, count = 30, 100
            end = datetime.now(timezone.utc)
            from datetime import timedelta
            start = end - timedelta(days=days)
            items = mt5.history_deals_get(start, end)
            if items is None:
                return self.send_json(503, {"ok": False, "error": "Historique des transactions indisponible",
                                            "mt5_error": str(mt5.last_error())})
            rows = []
            for d in sorted(items, key=lambda x: x.time, reverse=True)[:count]:
                rows.append({"ticket": int(d.ticket), "order": int(d.order), "time": int(d.time),
                    "symbol": str(d.symbol), "type": str(d.type), "entry": str(d.entry),
                    "volume": float(d.volume), "price": float(d.price), "profit": float(d.profit),
                    "commission": float(d.commission), "swap": float(d.swap), "fee": float(getattr(d, "fee", 0) or 0),
                    "comment": str(d.comment), "magic": int(d.magic)})
            return self.send_json(200, {"ok": True, "count": len(rows), "days": days, "deals": rows,
                                        "observed_at": datetime.now(timezone.utc).isoformat(), "read_only": True})
        if path == "/history/xauusd":
            query = parse_qs(urlparse(self.path).query)
            try:
                count = max(10, min(500, int(query.get("count", ["100"])[0])))
            except ValueError:
                count = 100
            rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M15, 0, count)
            if rates is None:
                return self.send_json(503, {"ok": False, "error": "Historique XAUUSD indisponible",
                                            "mt5_error": str(mt5.last_error())})
            bars = [{"time": int(r["time"]), "open": float(r["open"]),
                     "high": float(r["high"]), "low": float(r["low"]),
                     "close": float(r["close"]), "tick_volume": int(r["tick_volume"])}
                    for r in rates]
            return self.send_json(200, {"ok": True, "symbol": "XAUUSD", "timeframe": "M15", "bars": bars})
        if path in ("/health", "/accounts"):
            account = account_status()
            return self.send_json(200 if account.get("connected") else 503,
                                  {"ok": bool(account.get("connected")), "account": account})
        return self.send_json(404, {"ok": False, "error": "Not found"})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Définis MT5_BRIDGE_TOKEN avant de démarrer le pont.")
    print(f"Pont MT5 lecture seule actif sur {HOST}:{PORT}")
    print("Le pont ne contient aucune fonction d'envoi d'ordre.")
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        if not mt5.initialize():
            print(f"MT5 initialization failed: {mt5.last_error()}")
        threading.Thread(target=signal_watcher, daemon=True).start()
        print("Surveillance des signaux M15 active ; alertes Telegram activées.")
    else:
        print("Alertes Telegram non configurées ; définir TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID pour les activer.")
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    finally:
        mt5.shutdown()
