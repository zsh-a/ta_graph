from src.utils.risk_policy import (
    RiskPolicy,
    calculate_atr_from_ohlcv,
    enforce_min_rr,
    enforce_min_stop_distance,
)


SAMPLE_OHLCV = [
    [1, 100, 102, 99, 101, 1000],
    [2, 101, 104, 100, 103, 1000],
    [3, 103, 106, 102, 105, 1000],
    [4, 105, 107, 103, 104, 1000],
    [5, 104, 108, 103, 107, 1000],
]


def test_calculate_atr_from_ohlcv_positive():
    atr = calculate_atr_from_ohlcv(SAMPLE_OHLCV, period=3)
    assert atr > 0


def test_enforce_min_stop_distance_adjusts_tight_long_stop():
    policy = RiskPolicy(min_stop_atr_multiplier=1.0, min_stop_pct=0.001, min_rr=2.0, atr_period=14)
    new_stop, adjusted, reason = enforce_min_stop_distance(
        entry_price=100.0,
        stop_loss=99.9,
        is_buy=True,
        atr=2.0,
        policy=policy,
    )

    assert adjusted is True
    assert new_stop == 98.0
    assert "SL distance adjusted" in reason


def test_enforce_min_rr_adjusts_take_profit():
    policy = RiskPolicy(min_stop_atr_multiplier=1.0, min_stop_pct=0.001, min_rr=2.0, atr_period=14)
    new_tp, adjusted, reason = enforce_min_rr(
        entry_price=100.0,
        stop_loss=98.0,
        take_profit=101.0,
        is_buy=True,
        policy=policy,
    )

    assert adjusted is True
    assert new_tp == 104.0
    assert "TP RR adjusted" in reason
