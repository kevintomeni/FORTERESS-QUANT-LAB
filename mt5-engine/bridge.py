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
        if path == "/history/xauusd":
            query = parse_qs(urlparse(self.path).query)
            try:
                count = max(10, min(500, int(query.get("count", ["100"])[0])))
            except ValueError:
                count = 100
            if not mt5.initialize():
                return self.send_json(503, {"ok": False, "error": "MT5 initialize failed"})
            rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M15, 0, count)
            if rates is None:
                return self.send_json(503, {"ok": False, "error": "Historique XAUUSD indisponible",
                                            "mt5_error": str(mt5.last_error())})
            bars = [{"time": int(r["time"]), "open": float(r["open"]),
                     "high": float(r["high"]), "low": float(r["low"]),
                     "close": float(r["close"]), "tick_volume": int(r["tick_volume"])}
                    for r in rates]
            return self.send_json(200, {"ok": True, "symbol": "XAUUSD", "timeframe": "M15", "bars": bars})
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
