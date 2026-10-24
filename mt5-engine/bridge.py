"""Authenticated read-only status bridge for the currently logged-in MT5 terminal."""
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import MetaTrader5 as mt5

HOST = os.getenv("MT5_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.getenv("MT5_BRIDGE_PORT", "8765"))
TOKEN = os.getenv("MT5_BRIDGE_TOKEN", "")


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
        if path in ("/history", "/history/xauusd"):
            query = parse_qs(urlparse(self.path).query)
            symbol = (query.get("symbol", ["XAUUSD"])[0] or "XAUUSD").upper()
            timeframe_name = (query.get("timeframe", ["M15"])[0] or "M15").upper()
            allowed_symbols = {"BTCUSD", "XAUUSD", "EURUSD", "GBPUSD", "USDJPY"}
            timeframes = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
                          "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
                          "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
                          "D1": mt5.TIMEFRAME_D1}
            if symbol not in allowed_symbols:
                return self.send_json(400, {"ok": False, "error": "Symbole non autorisé", "read_only": True})
            if timeframe_name not in timeframes:
                return self.send_json(400, {"ok": False, "error": "Timeframe non autorisé", "allowed": list(timeframes), "read_only": True})
            try:
                count = max(50, min(500, int(query.get("count", ["200"])[0])))
            except ValueError:
                count = 200
            info = mt5.symbol_info(symbol)
            if info is None:
                return self.send_json(404, {"ok": False, "error": "Symbole MT5 introuvable", "symbol": symbol})
            if not info.visible and not mt5.symbol_select(symbol, True):
                return self.send_json(503, {"ok": False, "error": "Impossible d'activer le symbole", "symbol": symbol})
            rates = mt5.copy_rates_from_pos(symbol, timeframes[timeframe_name], 0, count)
            if rates is None or len(rates) == 0:
                return self.send_json(503, {"ok": False, "error": "Historique MT5 indisponible", "symbol": symbol,
                                            "mt5_error": str(mt5.last_error()), "read_only": True})
            bars = [{"time": int(r["time"]), "open": float(r["open"]),
                     "high": float(r["high"]), "low": float(r["low"]),
                     "close": float(r["close"]), "tick_volume": int(r["tick_volume"])}
                    for r in rates]
            return self.send_json(200, {"ok": True, "symbol": symbol, "timeframe": timeframe_name,
                                        "bars": bars, "read_only": True})
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
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    finally:
        mt5.shutdown()
