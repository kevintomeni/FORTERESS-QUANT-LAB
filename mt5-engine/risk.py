from dataclasses import dataclass

@dataclass
class RiskDecision:
    allowed: bool
    reasons: list[str]

def pre_trade_gate(*, spread_points: float, max_spread_points: float, atr_points: float, min_atr_points: float, max_atr_points: float, current_open_positions: int, max_open_positions: int, daily_loss_pct: float, max_daily_loss_pct: float, signal_direction: str) -> RiskDecision:
    reasons: list[str] = []
    if signal_direction not in {'BUY_BIAS', 'SELL_BIAS'}:
        reasons.append('No directional signal')
    if spread_points < 0 or spread_points > max_spread_points:
        reasons.append('Spread missing or above limit')
    if atr_points < min_atr_points or atr_points > max_atr_points:
        reasons.append('Volatility outside configured range')
    if current_open_positions >= max_open_positions:
        reasons.append('Maximum open positions reached')
    if daily_loss_pct >= max_daily_loss_pct:
        reasons.append('Daily loss limit reached')
    return RiskDecision(not reasons, reasons or ['Paper checks passed'])