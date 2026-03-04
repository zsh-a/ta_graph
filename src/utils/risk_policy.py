from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class RiskPolicy:
    """Centralized distance constraints for initial SL/TP."""

    min_stop_atr_multiplier: float = 1.5
    min_stop_pct: float = 0.005
    min_rr: float = 2.0
    atr_period: int = 14

    @classmethod
    def from_env(cls) -> "RiskPolicy":
        return cls(
            min_stop_atr_multiplier=float(os.getenv("MIN_STOP_ATR_MULTIPLIER", "1.5")),
            min_stop_pct=float(os.getenv("MIN_STOP_PCT", "0.005")),
            min_rr=float(os.getenv("MIN_RR", "2.0")),
            atr_period=int(os.getenv("ATR_PERIOD", "14")),
        )


def calculate_atr_from_ohlcv(ohlcv: list[list[float]], period: int = 14) -> float:
    """
    Calculate ATR using a simple rolling mean of True Range.
    OHLCV format: [timestamp, open, high, low, close, volume]
    """
    if len(ohlcv) < 2:
        return 0.0

    trs: list[float] = []
    for i in range(1, len(ohlcv)):
        high = float(ohlcv[i][2])
        low = float(ohlcv[i][3])
        prev_close = float(ohlcv[i - 1][4])

        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    if not trs:
        return 0.0

    lookback = min(period, len(trs))
    sample = trs[-lookback:]
    return sum(sample) / len(sample)


def enforce_min_stop_distance(
    *,
    entry_price: float,
    stop_loss: float,
    is_buy: bool,
    atr: float,
    policy: RiskPolicy,
) -> tuple[float, bool, str]:
    """
    Ensure initial stop is not too tight. Returns (stop, adjusted, reason).
    """
    if entry_price <= 0:
        return stop_loss, False, ""

    distance = abs(entry_price - stop_loss)
    min_distance_atr = policy.min_stop_atr_multiplier * atr if atr > 0 else 0.0
    min_distance_pct = entry_price * policy.min_stop_pct
    min_distance = max(min_distance_atr, min_distance_pct)

    if distance >= min_distance or min_distance <= 0:
        return stop_loss, False, ""

    new_stop = entry_price - min_distance if is_buy else entry_price + min_distance
    reason = (
        f"SL distance adjusted {distance:.4f} -> {min_distance:.4f} "
        f"(ATR={atr:.4f}, min_atr_mult={policy.min_stop_atr_multiplier}, "
        f"min_stop_pct={policy.min_stop_pct})"
    )
    return new_stop, True, reason


def enforce_min_rr(
    *,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    is_buy: bool,
    policy: RiskPolicy,
) -> tuple[float, bool, str]:
    """
    Ensure TP is far enough to satisfy minimum reward/risk.
    Returns (tp, adjusted, reason).
    """
    risk = abs(entry_price - stop_loss)
    if risk <= 0:
        return take_profit, False, ""

    reward = abs(take_profit - entry_price)
    rr = reward / risk if risk > 0 else 0.0
    if rr >= policy.min_rr:
        return take_profit, False, ""

    new_tp = entry_price + (risk * policy.min_rr) if is_buy else entry_price - (risk * policy.min_rr)
    reason = (
        f"TP RR adjusted {rr:.2f}R -> {policy.min_rr:.2f}R "
        f"(risk={risk:.4f}, reward={reward:.4f})"
    )
    return new_tp, True, reason
