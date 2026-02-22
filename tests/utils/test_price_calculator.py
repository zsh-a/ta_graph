"""
Tests for price_calculator module - Entry, Stop Loss, Take Profit calculations.
"""

import pytest
from src.utils.price_calculator import (
    get_tick_size,
    calculate_entry_price,
    calculate_stop_loss_price,
    calculate_take_profit_price,
)


# OHLCV format: [timestamp, open, high, low, close, volume]
SAMPLE_OHLCV = [
    [1000, 100.0, 105.0, 95.0, 102.0, 500],   # bar -4
    [2000, 102.0, 108.0, 100.0, 106.0, 600],   # bar -3
    [3000, 106.0, 110.0, 103.0, 107.0, 700],   # bar -2
    [4000, 107.0, 112.0, 104.0, 110.0, 800],   # bar -1 (previous)
    [5000, 110.0, 115.0, 108.0, 113.0, 900],   # bar  0 (current)
]


# ==================== Tick Size ====================

class TestGetTickSize:

    def test_btc_tick(self):
        assert get_tick_size("BTC/USDT") == 0.1

    def test_eth_tick(self):
        assert get_tick_size("ETH/USDT") == 0.01

    def test_other_tick(self):
        assert get_tick_size("DOGE/USDT") == 0.0001

    def test_case_insensitive(self):
        assert get_tick_size("btc/usdt") == 0.1


# ==================== Entry Price ====================

class TestCalculateEntryPrice:

    def test_bar_high_current(self):
        """Entry at current bar's high + 1 tick."""
        rule = {"type": "bar_high", "barIndex": 0}
        price = calculate_entry_price(rule, SAMPLE_OHLCV, 113.0, "BTC/USDT")
        # bar 0 high = 115.0, offset defaults to 1 tick (0.1)
        assert price == pytest.approx(115.1, abs=0.01)

    def test_bar_low_current(self):
        """Entry at current bar's low - 1 tick."""
        rule = {"type": "bar_low", "barIndex": 0}
        price = calculate_entry_price(rule, SAMPLE_OHLCV, 113.0, "BTC/USDT")
        # bar 0 low = 108.0, offset defaults to 1 tick (0.1), subtracted for bar_low
        assert price == pytest.approx(107.9, abs=0.01)

    def test_bar_close_previous(self):
        """Entry at previous bar's close."""
        rule = {"type": "bar_close", "barIndex": -1, "offset": 0}
        price = calculate_entry_price(rule, SAMPLE_OHLCV, 113.0, "BTC/USDT")
        # bar -1 close = 110.0
        assert price == pytest.approx(110.0, abs=0.01)

    def test_current_price_type(self):
        """Entry at current market price."""
        rule = {"type": "current_price", "barIndex": 0, "offset": 0}
        price = calculate_entry_price(rule, SAMPLE_OHLCV, 113.0, "BTC/USDT")
        assert price == pytest.approx(113.0, abs=0.01)

    def test_explicit_offset(self):
        """Entry with explicit offset (2 ticks)."""
        rule = {"type": "bar_high", "barIndex": 0, "offset": 2}
        price = calculate_entry_price(rule, SAMPLE_OHLCV, 113.0, "BTC/USDT")
        # 115.0 + 2 * 0.1 = 115.2
        assert price == pytest.approx(115.2, abs=0.01)

    def test_invalid_bar_index_fallback(self):
        """Should fallback to current_price for invalid bar index."""
        rule = {"type": "bar_high", "barIndex": -10}
        price = calculate_entry_price(rule, SAMPLE_OHLCV, 113.0, "BTC/USDT")
        assert price == 113.0


# ==================== Stop Loss Price ====================

class TestCalculateStopLossPrice:

    def test_bar_low_buy_stop(self):
        """Buy: stop below bar low."""
        rule = {"type": "bar_low", "barIndex": -1, "offset": 1}
        price = calculate_stop_loss_price(rule, SAMPLE_OHLCV, 113.0, is_buy=True, symbol="BTC/USDT")
        # bar -1 low = 104.0, offset = 1 tick (0.1), buy subtracts
        assert price == pytest.approx(103.9, abs=0.01)

    def test_bar_high_sell_stop(self):
        """Sell: stop above bar high."""
        rule = {"type": "bar_high", "barIndex": -1, "offset": 1}
        price = calculate_stop_loss_price(rule, SAMPLE_OHLCV, 113.0, is_buy=False, symbol="BTC/USDT")
        # bar -1 high = 112.0, offset = 1 tick (0.1), sell adds
        assert price == pytest.approx(112.1, abs=0.01)

    def test_pattern_low(self):
        """Stop at pattern low (min of range)."""
        rule = {"type": "pattern_low", "patternStartBar": -3, "patternEndBar": -1}
        price = calculate_stop_loss_price(rule, SAMPLE_OHLCV, 113.0, is_buy=True, symbol="BTC/USDT")
        # bars -3 to -1: lows are 100.0, 103.0, 104.0 → min = 100.0
        assert price == pytest.approx(100.0, abs=0.01)

    def test_pattern_high(self):
        """Stop at pattern high (max of range)."""
        rule = {"type": "pattern_high", "patternStartBar": -3, "patternEndBar": -1}
        price = calculate_stop_loss_price(rule, SAMPLE_OHLCV, 113.0, is_buy=False, symbol="BTC/USDT")
        # bars -3 to -1: highs are 108.0, 110.0, 112.0 → max = 112.0
        assert price == pytest.approx(112.0, abs=0.01)

    def test_swing_low(self):
        """Stop at swing low."""
        rule = {"type": "swing_low", "swingStartBar": -4, "swingEndBar": -2}
        price = calculate_stop_loss_price(rule, SAMPLE_OHLCV, 113.0, is_buy=True, symbol="BTC/USDT")
        # bars -4 to -2: lows are 95.0, 100.0, 103.0 → min = 95.0
        assert price == pytest.approx(95.0, abs=0.01)

    def test_offset_percent(self):
        """Stop with percentage offset."""
        rule = {"type": "bar_low", "barIndex": -1, "offsetPercent": 1.0}
        price = calculate_stop_loss_price(rule, SAMPLE_OHLCV, 113.0, is_buy=True, symbol="BTC/USDT")
        # bar -1 low = 104.0, 1% of 104.0 = 1.04, buy subtracts
        assert price == pytest.approx(102.96, abs=0.01)

    def test_missing_bar_index_raises(self):
        """Should raise ValueError when barIndex is missing for bar_low."""
        rule = {"type": "bar_low"}
        with pytest.raises(ValueError, match="barIndex required"):
            calculate_stop_loss_price(rule, SAMPLE_OHLCV, 113.0, is_buy=True)

    def test_invalid_bar_index_raises(self):
        """Should raise ValueError for out-of-range bar index."""
        rule = {"type": "bar_low", "barIndex": -20}
        with pytest.raises(ValueError, match="Invalid bar index"):
            calculate_stop_loss_price(rule, SAMPLE_OHLCV, 113.0, is_buy=True)

    def test_missing_pattern_range_raises(self):
        """Should raise ValueError when pattern start/end missing."""
        rule = {"type": "pattern_low"}
        with pytest.raises(ValueError, match="pattern start/end required"):
            calculate_stop_loss_price(rule, SAMPLE_OHLCV, 113.0, is_buy=True)

    def test_missing_swing_range_raises(self):
        """Should raise ValueError when swing start/end missing."""
        rule = {"type": "swing_low"}
        with pytest.raises(ValueError, match="swing start/end required"):
            calculate_stop_loss_price(rule, SAMPLE_OHLCV, 113.0, is_buy=True)


# ==================== Take Profit Price ====================

class TestCalculateTakeProfitPrice:

    def test_risk_multiple_buy(self):
        """TP = entry + risk * multiple for buy."""
        rule = {"type": "risk_multiple", "riskMultiple": 2.0}
        tp = calculate_take_profit_price(rule, SAMPLE_OHLCV, entry_price=110.0, stop_loss_price=105.0)
        # risk = 5.0, TP = 110 + 5*2 = 120
        assert tp == pytest.approx(120.0, abs=0.01)

    def test_risk_multiple_sell(self):
        """TP = entry - risk * multiple for sell."""
        rule = {"type": "risk_multiple", "riskMultiple": 1.5}
        tp = calculate_take_profit_price(rule, SAMPLE_OHLCV, entry_price=100.0, stop_loss_price=105.0)
        # risk = 5.0, TP = 100 - 5*1.5 = 92.5
        assert tp == pytest.approx(92.5, abs=0.01)

    def test_risk_multiple_default(self):
        """Default risk multiple is 1.5."""
        rule = {"type": "risk_multiple"}
        tp = calculate_take_profit_price(rule, SAMPLE_OHLCV, entry_price=110.0, stop_loss_price=105.0)
        # risk = 5.0, TP = 110 + 5*1.5 = 117.5
        assert tp == pytest.approx(117.5, abs=0.01)

    def test_measured_move_buy(self):
        """TP from measured move (buy)."""
        rule = {"type": "measured_move", "measuredMoveBarStart": -4, "measuredMoveBarEnd": -2}
        tp = calculate_take_profit_price(rule, SAMPLE_OHLCV, entry_price=110.0, stop_loss_price=105.0)
        # bars -4 to -2: high = max(105,108,110)=110, low = min(95,100,103)=95, impulse = 15
        # buy: 110 + 15 = 125
        assert tp == pytest.approx(125.0, abs=0.01)

    def test_measured_move_sell(self):
        """TP from measured move (sell)."""
        rule = {"type": "measured_move", "measuredMoveBarStart": -4, "measuredMoveBarEnd": -2}
        tp = calculate_take_profit_price(rule, SAMPLE_OHLCV, entry_price=100.0, stop_loss_price=105.0)
        # sell: 100 - 15 = 85
        assert tp == pytest.approx(85.0, abs=0.01)

    def test_key_level(self):
        """TP at a specific key level."""
        rule = {"type": "key_level", "keyLevel": 120.0}
        tp = calculate_take_profit_price(rule, SAMPLE_OHLCV, entry_price=110.0, stop_loss_price=105.0)
        assert tp == pytest.approx(120.0, abs=0.01)

    def test_unknown_type_returns_entry(self):
        """Unknown rule type should return entry price."""
        rule = {"type": "unknown_type"}
        tp = calculate_take_profit_price(rule, SAMPLE_OHLCV, entry_price=110.0, stop_loss_price=105.0)
        assert tp == 110.0

    def test_measured_move_missing_range_raises(self):
        """Should raise ValueError when measured move range is missing."""
        rule = {"type": "measured_move"}
        with pytest.raises(ValueError, match="measured move start/end required"):
            calculate_take_profit_price(rule, SAMPLE_OHLCV, entry_price=110.0, stop_loss_price=105.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
