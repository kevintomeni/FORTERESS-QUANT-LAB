import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default

def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default

@dataclass(frozen=True)
class Config:
    trading_mode: str = os.getenv('TRADING_MODE', 'paper').strip().lower()
    symbol: str = os.getenv('MT5_SYMBOL', 'XAUUSD').strip()
    fast_timeframe: str = os.getenv('FAST_TIMEFRAME', 'M15').strip().upper()
    slow_timeframe: str = os.getenv('SLOW_TIMEFRAME', 'H1').strip().upper()
    bars_count: int = _int('BARS_COUNT', 250)
    risk_per_trade_pct: float = _float('RISK_PER_TRADE_PCT', 0.25)
    max_daily_loss_pct: float = _float('MAX_DAILY_LOSS_PCT', 1.0)
    max_open_positions: int = _int('MAX_OPEN_POSITIONS', 1)
    max_spread_points: float = _float('MAX_SPREAD_POINTS', 80.0)
    min_atr_points: float = _float('MIN_ATR_POINTS', 0.0)
    max_atr_points: float = _float('MAX_ATR_POINTS', 5000.0)

CONFIG = Config()

def validate_config() -> None:
    if CONFIG.trading_mode != 'paper':
        raise RuntimeError('Safety lock: this scaffold supports TRADING_MODE=paper only.')
    if not CONFIG.symbol:
        raise RuntimeError('MT5_SYMBOL must not be empty.')
    if not 100 <= CONFIG.bars_count <= 5000:
        raise RuntimeError('BARS_COUNT must be between 100 and 5000.')
    if not 0 < CONFIG.risk_per_trade_pct <= 0.25:
        raise RuntimeError('Risk must be >0 and <=0.25% during validation.')
    if not 0 < CONFIG.max_daily_loss_pct <= 1.0:
        raise RuntimeError('Daily loss limit must be >0 and <=1%.')
    if CONFIG.max_open_positions != 1:
        raise RuntimeError('Initial validation permits one position at most.')