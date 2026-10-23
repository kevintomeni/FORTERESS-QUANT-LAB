from dataclasses import dataclass
import pandas as pd

@dataclass
class Signal:
    direction: str
    score: int
    reasons: list[str]
    atr: float
    status: str

def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev = df['close'].shift(1)
    tr = pd.concat([df['high'] - df['low'], (df['high'] - prev).abs(), (df['low'] - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def evaluate_signal(fast: pd.DataFrame, slow: pd.DataFrame, point: float, min_atr_points: float, max_atr_points: float) -> Signal:
    if len(fast) < 60 or len(slow) < 60 or point <= 0:
        return Signal('NONE', 0, ['Insufficient bars or invalid point size'], 0.0, 'BLOCKED')
    # Exclude the currently forming candle to avoid repainting signals.
    f = fast.iloc[:-1].copy()
    s = slow.iloc[:-1].copy()
    if len(f) < 60 or len(s) < 60:
        return Signal('NONE', 0, ['Insufficient closed candles'], 0.0, 'BLOCKED')
    f['ema20'] = f['close'].ewm(span=20, adjust=False).mean()
    f['ema50'] = f['close'].ewm(span=50, adjust=False).mean()
    s['ema20'] = s['close'].ewm(span=20, adjust=False).mean()
    s['ema50'] = s['close'].ewm(span=50, adjust=False).mean()
    f['atr'] = _atr(f, 14)
    last, slow_last = f.iloc[-1], s.iloc[-1]
    atr = float(last['atr']) if pd.notna(last['atr']) else 0.0
    atr_points = atr / point
    bull = bear = 0
    reasons: list[str] = []
    if last['ema20'] > last['ema50']:
        bull += 1; reasons.append('M15 EMA20 > EMA50')
    elif last['ema20'] < last['ema50']:
        bear += 1; reasons.append('M15 EMA20 < EMA50')
    if slow_last['ema20'] > slow_last['ema50']:
        bull += 1; reasons.append('H1 EMA20 > EMA50')
    elif slow_last['ema20'] < slow_last['ema50']:
        bear += 1; reasons.append('H1 EMA20 < EMA50')
    prior = f.iloc[-21:-1]
    if float(last['close']) > float(prior['high'].max()):
        bull += 1; reasons.append('M15 close breaks prior 20-bar high')
    elif float(last['close']) < float(prior['low'].min()):
        bear += 1; reasons.append('M15 close breaks prior 20-bar low')
    else:
        reasons.append('No 20-bar breakout')
    if not min_atr_points <= atr_points <= max_atr_points:
        return Signal('NONE', max(bull, bear), reasons + [f'ATR blocked: {atr_points:.1f} points'], atr, 'BLOCKED')
    reasons.append(f'ATR within configured range ({atr_points:.1f} points)')
    if bull >= 2 and bull > bear:
        return Signal('BUY_BIAS', bull, reasons, atr, 'PAPER_SIGNAL_ONLY')
    if bear >= 2 and bear > bull:
        return Signal('SELL_BIAS', bear, reasons, atr, 'PAPER_SIGNAL_ONLY')
    return Signal('NONE', max(bull, bear), reasons + ['Criteria not aligned; no trade'], atr, 'NO_TRADE')