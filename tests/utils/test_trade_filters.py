"""
Tests for trade_filters module - Anti-overtrading mechanisms.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
import pandas as pd

from src.utils.trade_filters import TradeFilter


@pytest.fixture
def tf():
    """Create a TradeFilter with no persistence side effects."""
    with patch.object(TradeFilter, '_load_state'), \
         patch.object(TradeFilter, '_save_state'):
        return TradeFilter(
            cooldown_minutes=15,
            max_daily_trades=5,
            min_probability=60.0,
            min_signal_quality=6,
            enable_all=True
        )


@pytest.fixture
def sample_bars_df():
    """DataFrame of 20 bars for quantitative filters."""
    data = []
    base = 100.0
    for i in range(20):
        o = base + i * 0.5
        h = o + 2.0
        l = o - 1.0
        c = o + 1.0
        data.append({"open": o, "high": h, "low": l, "close": c, "volume": 1000})
    return pd.DataFrame(data)


# ==================== Cooldown Filter ====================

class TestCooldownFilter:

    def test_pass_when_no_previous_trade(self, tf):
        passed, reason = tf.check_cooldown()
        assert passed is True
        assert reason == ""

    def test_fail_during_cooldown(self, tf):
        tf.last_trade_time = datetime.now() - timedelta(minutes=5)
        passed, reason = tf.check_cooldown()
        assert passed is False
        assert "Cooldown active" in reason

    def test_pass_after_cooldown_expires(self, tf):
        tf.last_trade_time = datetime.now() - timedelta(minutes=20)
        passed, reason = tf.check_cooldown()
        assert passed is True

    def test_disabled_always_passes(self, tf):
        tf.enable_all = False
        tf.last_trade_time = datetime.now()
        passed, reason = tf.check_cooldown()
        assert passed is True


# ==================== Daily Limit Filter ====================

class TestDailyLimitFilter:

    def test_pass_under_limit(self, tf):
        tf.trades_today = 3
        passed, reason = tf.check_daily_limit()
        assert passed is True

    def test_fail_at_limit(self, tf):
        tf.trades_today = 5
        passed, reason = tf.check_daily_limit()
        assert passed is False
        assert "Daily limit reached" in reason

    def test_fail_over_limit(self, tf):
        tf.trades_today = 10
        passed, reason = tf.check_daily_limit()
        assert passed is False

    def test_disabled_always_passes(self, tf):
        tf.enable_all = False
        tf.trades_today = 100
        passed, reason = tf.check_daily_limit()
        assert passed is True


# ==================== Probability Filter ====================

class TestProbabilityFilter:

    def test_pass_above_threshold(self, tf):
        decision = {"probability_score": 75.0}
        passed, reason = tf.check_probability_threshold(decision)
        assert passed is True

    def test_fail_below_threshold(self, tf):
        decision = {"probability_score": 40.0}
        passed, reason = tf.check_probability_threshold(decision)
        assert passed is False
        assert "Probability too low" in reason

    def test_exact_threshold_passes(self, tf):
        decision = {"probability_score": 60.0}
        passed, reason = tf.check_probability_threshold(decision)
        assert passed is True

    def test_missing_score_defaults_to_zero(self, tf):
        decision = {}
        passed, reason = tf.check_probability_threshold(decision)
        assert passed is False


# ==================== Signal Bar Quality Filter ====================

class TestSignalBarQualityFilter:

    def test_pass_good_quality(self, tf):
        analysis = {"signal_bar": {"quality_score": 8}}
        passed, reason = tf.check_signal_bar_quality(analysis)
        assert passed is True

    def test_fail_low_quality(self, tf):
        analysis = {"signal_bar": {"quality_score": 3}}
        passed, reason = tf.check_signal_bar_quality(analysis)
        assert passed is False
        assert "Signal bar quality too low" in reason

    def test_fail_no_analysis(self, tf):
        passed, reason = tf.check_signal_bar_quality(None)
        assert passed is False
        assert "No Brooks analysis" in reason

    def test_fail_missing_signal_bar(self, tf):
        passed, reason = tf.check_signal_bar_quality({"market_cycle": "bull"})
        assert passed is False


# ==================== TTR Condition Filter ====================

class TestTTRConditionFilter:

    def test_pass_in_trend(self, tf):
        analysis = {"market_cycle": "strong_bull_trend", "signal_bar": {"quality_score": 5}, "setup_quality": 5}
        passed, reason = tf.check_ttr_condition(analysis)
        assert passed is True

    def test_fail_in_ttr_with_low_signal(self, tf):
        analysis = {"market_cycle": "trading_range", "signal_bar": {"quality_score": 5}, "setup_quality": 8}
        passed, reason = tf.check_ttr_condition(analysis)
        assert passed is False
        assert "signal bar quality" in reason

    def test_fail_in_ttr_with_low_setup(self, tf):
        analysis = {"market_cycle": "trading_range", "signal_bar": {"quality_score": 9}, "setup_quality": 4}
        passed, reason = tf.check_ttr_condition(analysis)
        assert passed is False
        assert "setup quality" in reason

    def test_pass_in_ttr_with_high_quality(self, tf):
        analysis = {"market_cycle": "trading_range", "signal_bar": {"quality_score": 9}, "setup_quality": 8}
        passed, reason = tf.check_ttr_condition(analysis)
        assert passed is True

    def test_pass_when_no_analysis(self, tf):
        passed, reason = tf.check_ttr_condition(None)
        assert passed is True


# ==================== Validation Errors Filter ====================

class TestValidationErrorsFilter:

    def test_pass_valid(self, tf):
        analysis = {"_validation": {"valid": True, "errors": [], "warnings": []}}
        passed, reason = tf.check_validation_errors(analysis)
        assert passed is True

    def test_fail_invalid(self, tf):
        analysis = {"_validation": {"valid": False, "errors": ["Bar type mismatch"], "warnings": []}}
        passed, reason = tf.check_validation_errors(analysis)
        assert passed is False
        assert "VL model validation failed" in reason

    def test_fail_too_many_warnings(self, tf):
        analysis = {"_validation": {"valid": True, "errors": [], "warnings": ["w1", "w2", "w3"]}}
        passed, reason = tf.check_validation_errors(analysis)
        assert passed is False
        assert "Too many validation warnings" in reason

    def test_pass_no_validation_key(self, tf):
        analysis = {"market_cycle": "bull"}
        passed, reason = tf.check_validation_errors(analysis)
        assert passed is True


# ==================== Bar Close Filter ====================

class TestBarCloseFilter:

    def test_pass_near_close(self, tf):
        # 4 minutes 40 seconds into a 5-minute bar (20s remaining)
        t = datetime(2025, 1, 1, 12, 4, 40)
        passed, reason = tf.check_bar_close(current_time=t)
        assert passed is True

    def test_fail_mid_bar(self, tf):
        # 2 minutes into a 5-minute bar (180s remaining)
        t = datetime(2025, 1, 1, 12, 2, 0)
        passed, reason = tf.check_bar_close(current_time=t)
        assert passed is False
        assert "Not near bar close" in reason

    def test_pass_at_bar_start(self, tf):
        # First 10 seconds of a new bar (latency buffer)
        t = datetime(2025, 1, 1, 12, 0, 5)
        passed, reason = tf.check_bar_close(current_time=t)
        assert passed is True


# ==================== Barb Wire Filter ====================

class TestBarbWireFilter:

    def test_pass_trending_market(self, tf):
        """Trending market should pass even with some overlap."""
        data = []
        for i in range(10):
            o = 100 + i * 5
            data.append({"open": o, "high": o + 3, "low": o - 1, "close": o + 2, "volume": 100})
        df = pd.DataFrame(data)
        passed, reason = tf.check_barb_wire(df)
        assert passed is True

    def test_fail_choppy_market(self, tf):
        """Overlapping bars should trigger barb wire."""
        data = []
        for i in range(10):
            o = 100 + (i % 2) * 0.5
            data.append({"open": o, "high": 102, "low": 99, "close": o + 0.3, "volume": 100})
        df = pd.DataFrame(data)
        passed, reason = tf.check_barb_wire(df)
        assert passed is False
        assert "Barb Wire" in reason

    def test_pass_insufficient_data(self, tf):
        df = pd.DataFrame([{"open": 100, "high": 101, "low": 99, "close": 100, "volume": 100}])
        passed, reason = tf.check_barb_wire(df)
        assert passed is True


# ==================== ATR Stop Filter ====================

class TestATRStopFilter:

    def test_pass_reasonable_stop(self, tf, sample_bars_df):
        decision = {"entry_price": 110.0, "stop_loss": 105.0}
        passed, reason = tf.check_atr_stop(decision, sample_bars_df)
        assert passed is True

    def test_fail_tight_stop(self, tf, sample_bars_df):
        decision = {"entry_price": 110.0, "stop_loss": 109.99}
        passed, reason = tf.check_atr_stop(decision, sample_bars_df)
        assert passed is False
        assert "Stop Loss too tight" in reason

    def test_pass_missing_prices(self, tf, sample_bars_df):
        decision = {"entry_price": None, "stop_loss": None}
        passed, reason = tf.check_atr_stop(decision, sample_bars_df)
        assert passed is True


# ==================== Trading Range Logic Filter ====================

class TestTradingRangeLogicFilter:

    def test_pass_not_in_range(self, tf, sample_bars_df):
        decision = {"operation": "Buy"}
        analysis = {"market_cycle": "strong_bull_trend"}
        passed, reason = tf.check_trading_range_logic(decision, analysis, sample_bars_df)
        assert passed is True

    def test_fail_buying_at_top_of_range(self, tf):
        data = [{"open": 100, "high": 110, "low": 90, "close": 108, "volume": 100}] * 30
        # Price at 108 in 90-110 range = 0.9 (top third)
        df = pd.DataFrame(data)
        decision = {"operation": "Buy"}
        analysis = {"market_cycle": "trading_range"}
        passed, reason = tf.check_trading_range_logic(decision, analysis, df)
        assert passed is False
        assert "Buying at top of range" in reason

    def test_fail_selling_at_bottom_of_range(self, tf):
        data = [{"open": 100, "high": 110, "low": 90, "close": 92, "volume": 100}] * 30
        df = pd.DataFrame(data)
        decision = {"operation": "Sell"}
        analysis = {"market_cycle": "trading_range"}
        passed, reason = tf.check_trading_range_logic(decision, analysis, df)
        assert passed is False
        assert "Selling at bottom of range" in reason


# ==================== Apply All Filters ====================

class TestApplyAllFilters:

    def test_all_pass(self, tf):
        decision = {"probability_score": 80.0}
        analysis = {"signal_bar": {"quality_score": 8}, "market_cycle": "strong_bull_trend",
                     "setup_quality": 8, "_validation": {"valid": True, "errors": [], "warnings": []}}
        passed, reasons = tf.apply_all_filters(decision, analysis)
        assert passed is True
        assert reasons == []

    def test_multiple_failures(self, tf):
        tf.trades_today = 10
        decision = {"probability_score": 20.0}
        analysis = {"signal_bar": {"quality_score": 2}, "market_cycle": "strong_bull_trend",
                     "setup_quality": 8, "_validation": {"valid": True, "errors": [], "warnings": []}}
        passed, reasons = tf.apply_all_filters(decision, analysis)
        assert passed is False
        assert len(reasons) >= 2

    def test_disabled_passes_everything(self, tf):
        tf.enable_all = False
        decision = {"probability_score": 0}
        passed, reasons = tf.apply_all_filters(decision)
        assert passed is True
        assert reasons == []


# ==================== Record Trade ====================

class TestRecordTrade:

    def test_record_increments_counter(self, tf):
        assert tf.trades_today == 0
        tf.record_trade_execution()
        assert tf.trades_today == 1
        assert tf.last_trade_time is not None

    def test_record_multiple(self, tf):
        tf.record_trade_execution()
        tf.record_trade_execution()
        assert tf.trades_today == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
