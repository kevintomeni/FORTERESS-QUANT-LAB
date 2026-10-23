from datetime import datetime, timezone
import json
import sys
import MetaTrader5 as mt5
import pandas as pd
from config import CONFIG, validate_config
from strategy import evaluate_signal
from risk import pre_trade_gate

TIMEFRAMES = {'M15': mt5.TIMEFRAME_M15, 'H1': mt5.TIMEFRAME_H1}

def fetch_bars(symbol: str, timeframe: int, count: int) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) < 100:
        raise RuntimeError(f'Insufficient MT5 bars for {symbol}; error={mt5.last_error()}')
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time').reset_index(drop=True)
    age = (datetime.now(timezone.utc) - df['time'].iloc[-1].to_pydatetime()).total_seconds()
    if age > 2 * 60 * 60:
        raise RuntimeError('Latest candle timestamp is stale; refusing to compute signal.')
    return df

def main() -> int:
    validate_config()
    if CONFIG.fast_timeframe not in TIMEFRAMES or CONFIG.slow_timeframe not in TIMEFRAMES:
        raise RuntimeError('Supported timeframes are M15 and H1.')
    if not mt5.initialize():
        raise RuntimeError(f'MT5 initialize failed: {mt5.last_error()}')
    try:
        terminal = mt5.terminal_info()
        account = mt5.account_info()
        if terminal is None or account is None:
            raise RuntimeError(f'MT5 terminal/account unavailable: {mt5.last_error()}')
        info = mt5.symbol_info(CONFIG.symbol)
        tick = mt5.symbol_info_tick(CONFIG.symbol)
        if info is None or tick is None:
            raise RuntimeError(f'Symbol/tick unavailable: {CONFIG.symbol}')
        if not info.visible and not mt5.symbol_select(CONFIG.symbol, True):
            raise RuntimeError(f'Cannot select symbol {CONFIG.symbol}')
        fast = fetch_bars(CONFIG.symbol, TIMEFRAMES[CONFIG.fast_timeframe], CONFIG.bars_count)
        slow = fetch_bars(CONFIG.symbol, TIMEFRAMES[CONFIG.slow_timeframe], CONFIG.bars_count)
        point = float(info.point)
        if point <= 0:
            raise RuntimeError('Invalid MT5 point size')
        spread = (float(tick.ask) - float(tick.bid)) / point
        signal = evaluate_signal(fast, slow, point, CONFIG.min_atr_points, CONFIG.max_atr_points)
        # Position reconciliation and daily equity tracking are not implemented.
        # Force the gate closed regardless of any provisional signal.
        gate = pre_trade_gate(spread_points=spread, max_spread_points=CONFIG.max_spread_points, atr_points=signal.atr / point, min_atr_points=CONFIG.min_atr_points, max_atr_points=CONFIG.max_atr_points, current_open_positions=CONFIG.max_open_positions, max_open_positions=CONFIG.max_open_positions, daily_loss_pct=CONFIG.max_daily_loss_pct, max_daily_loss_pct=CONFIG.max_daily_loss_pct, signal_direction=signal.direction)
        output = {
            'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'mode': 'paper',
            'symbol': CONFIG.symbol,
            'account_server': getattr(account, 'server', None),
            'account_currency': getattr(account, 'currency', None),
            'bid': float(tick.bid), 'ask': float(tick.ask), 'spread_points': round(spread, 2),
            'last_closed_fast_bar_utc': fast.iloc[-2]['time'].isoformat(),
            'last_closed_slow_bar_utc': slow.iloc[-2]['time'].isoformat(),
            'signal': {'direction': signal.direction, 'score': signal.score, 'status': signal.status, 'reasons': signal.reasons, 'atr_price': signal.atr},
            'risk_gate': {'allowed_for_future_paper_adapter_only': False, 'reasons': gate.reasons + ['Execution hard-disabled: reconciliation and persistent risk tracking not implemented']},
            'execution': 'DISABLED — this scaffold never submits orders'
        }
        print(json.dumps(output, indent=2))
        return 0
    finally:
        mt5.shutdown()

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({'mode': 'paper', 'status': 'ERROR', 'message': str(exc), 'execution': 'DISABLED'}, indent=2))
        sys.exit(1)