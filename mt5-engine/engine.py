from datetime import datetime, timezone
import json
import sys

import MetaTrader5 as mt5
import pandas as pd

from config import CONFIG, validate_config
from strategy import evaluate_signal
from risk import pre_trade_gate

TIMEFRAMES = {"M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1}

# Conservative data-quality limits. If the feed is closed/stale, fail closed.
MAX_TICK_AGE_SECONDS = 120
MAX_FUTURE_SKEW_SECONDS = 60


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_tick_freshness(tick, now: datetime) -> datetime:
    if tick is None or not getattr(tick, "time", 0):
        raise RuntimeError("No valid MT5 tick; market may be closed or feed unavailable.")

    tick_time = datetime.fromtimestamp(tick.time, timezone.utc)
    age_seconds = (now - tick_time).total_seconds()

    if age_seconds < -MAX_FUTURE_SKEW_SECONDS:
        raise RuntimeError(
            f"MT5 tick timestamp is in the future by {-age_seconds:.0f}s; "
            "clock/feed mismatch suspected. Refusing to calculate a signal."
        )
    if age_seconds > MAX_TICK_AGE_SECONDS:
        raise RuntimeError(
            f"MT5 tick is stale ({age_seconds:.0f}s old); market may be closed "
            "or quotes unavailable. Refusing to calculate a signal."
        )
    return tick_time


def fetch_bars(symbol: str, timeframe: int, count: int, now: datetime) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) < 100:
        raise RuntimeError(f"Insufficient MT5 bars for {symbol}; error={mt5.last_error()}")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.sort_values("time").reset_index(drop=True)

    # Check all returned bars, not just the final row, for future timestamps.
    latest_bar_time = df["time"].iloc[-1].to_pydatetime()
    future_seconds = (latest_bar_time - now).total_seconds()
    if future_seconds > MAX_FUTURE_SKEW_SECONDS:
        raise RuntimeError(
            f"MT5 {timeframe} bar timestamp is in the future by "
            f"{future_seconds:.0f}s; refusing to calculate a signal."
        )

    if len(df) < 2:
        raise RuntimeError("Not enough bars to identify the last closed candle.")

    # -1 may be the currently forming candle. The closed candle is -2.
    last_closed_time = df["time"].iloc[-2].to_pydatetime()
    closed_age = (now - last_closed_time).total_seconds()
    timeframe_seconds = 15 * 60 if timeframe == mt5.TIMEFRAME_M15 else 60 * 60
    max_closed_age = max(3 * timeframe_seconds, 60 * 60)
    if closed_age < -MAX_FUTURE_SKEW_SECONDS:
        raise RuntimeError("Last closed candle is in the future; refusing to calculate a signal.")
    if closed_age > max_closed_age:
        raise RuntimeError(
            f"Last closed candle is stale ({closed_age:.0f}s old); "
            "market may be closed or history unavailable."
        )
    return df


def main() -> int:
    validate_config()
    if CONFIG.fast_timeframe not in TIMEFRAMES or CONFIG.slow_timeframe not in TIMEFRAMES:
        raise RuntimeError("Supported timeframes are M15 and H1.")

    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    try:
        terminal = mt5.terminal_info()
        account = mt5.account_info()
        if terminal is None or account is None:
            raise RuntimeError(f"MT5 terminal/account unavailable: {mt5.last_error()}")

        # Ensure the symbol is selected before querying its current info/tick.
        if not mt5.symbol_select(CONFIG.symbol, True):
            raise RuntimeError(f"Cannot select symbol {CONFIG.symbol}; error={mt5.last_error()}")

        info = mt5.symbol_info(CONFIG.symbol)
        tick = mt5.symbol_info_tick(CONFIG.symbol)
        if info is None or tick is None:
            raise RuntimeError(f"Symbol/tick unavailable: {CONFIG.symbol}")

        now = utc_now()
        tick_time = validate_tick_freshness(tick, now)

        fast = fetch_bars(CONFIG.symbol, TIMEFRAMES[CONFIG.fast_timeframe], CONFIG.bars_count, now)
        slow = fetch_bars(CONFIG.symbol, TIMEFRAMES[CONFIG.slow_timeframe], CONFIG.bars_count, now)

        point = float(info.point)
        if point <= 0:
            raise RuntimeError("Invalid MT5 point size")

        spread = (float(tick.ask) - float(tick.bid)) / point
        if spread < 0:
            raise RuntimeError("Invalid MT5 quote: ask is below bid.")

        signal = evaluate_signal(
            fast, slow, point, CONFIG.min_atr_points, CONFIG.max_atr_points
        )

        # Position reconciliation and persistent daily-equity tracking are not implemented.
        # Keep this gate closed unconditionally.
        gate = pre_trade_gate(
            spread_points=spread,
            max_spread_points=CONFIG.max_spread_points,
            atr_points=signal.atr / point,
            min_atr_points=CONFIG.min_atr_points,
            max_atr_points=CONFIG.max_atr_points,
            current_open_positions=CONFIG.max_open_positions,
            max_open_positions=CONFIG.max_open_positions,
            daily_loss_pct=CONFIG.max_daily_loss_pct,
            max_daily_loss_pct=CONFIG.max_daily_loss_pct,
            signal_direction=signal.direction,
        )

        output = {
            "timestamp_utc": now.isoformat(),
            "mode": "paper",
            "status": "DATA_OK_SIGNAL_OBSERVATION_ONLY",
            "symbol": CONFIG.symbol,
            "account_server": getattr(account, "server", None),
            "account_currency": getattr(account, "currency", None),
            "tick_time_utc": tick_time.isoformat(),
            "tick_age_seconds": round((now - tick_time).total_seconds(), 1),
            "bid": float(tick.bid),
            "ask": float(tick.ask),
            "spread_points": round(spread, 2),
            "last_closed_fast_bar_utc": fast.iloc[-2]["time"].isoformat(),
            "last_closed_slow_bar_utc": slow.iloc[-2]["time"].isoformat(),
            "signal": {
                "direction": signal.direction,
                "score": signal.score,
                "status": signal.status,
                "reasons": signal.reasons,
                "atr_price": signal.atr,
            },
            "risk_gate": {
                "allowed_for_future_paper_adapter_only": False,
                "reasons": gate.reasons + [
                    "Execution hard-disabled: reconciliation and persistent risk tracking not implemented"
                ],
            },
            "execution": "DISABLED — this scaffold never submits orders",
        }
        print(json.dumps(output, indent=2))
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({
            "mode": "paper",
            "status": "DATA_CHECK_FAILED",
            "message": str(exc),
            "signal": "NOT_COMPUTED",
            "execution": "DISABLED — this scaffold never submits orders",
        }, indent=2))
        sys.exit(1)
