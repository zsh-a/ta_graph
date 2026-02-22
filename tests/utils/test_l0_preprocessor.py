"""
Tests for l0_preprocessor module - Pure Python bar feature extraction.
"""

import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from src.utils.l0_preprocessor import (
    classify_bar_type,
    classify_close_position,
    classify_ema_relation,
    detect_bar_patterns,
    BarFeatures,
    MarketContext,
    L0Preprocessor,
)


# ==================== classify_bar_type ====================

class TestClassifyBarType:

    def test_bull_trend_bar(self):
        """Big bull body (>50% of range) → bull_trend."""
        bar_type, body_pct = classify_bar_type(100.0, 110.0, 98.0, 109.0)
        assert bar_type == "bull_trend"
        assert body_pct > 50

    def test_bear_trend_bar(self):
        """Big bear body → bear_trend."""
        bar_type, body_pct = classify_bar_type(109.0, 110.0, 98.0, 100.0)
        assert bar_type == "bear_trend"
        assert body_pct > 50

    def test_bull_doji(self):
        """Small bull body (<=50%) → bull_doji."""
        bar_type, body_pct = classify_bar_type(100.0, 110.0, 90.0, 101.0)
        assert bar_type == "bull_doji"
        assert body_pct <= 50

    def test_bear_doji(self):
        """Small bear body → bear_doji."""
        bar_type, body_pct = classify_bar_type(101.0, 110.0, 90.0, 100.0)
        assert bar_type == "bear_doji"
        assert body_pct <= 50

    def test_zero_range(self):
        """All OHLC equal → body_pct = 0, bull_doji (close >= open)."""
        bar_type, body_pct = classify_bar_type(100.0, 100.0, 100.0, 100.0)
        assert body_pct == 0
        assert bar_type == "bull_doji"  # close >= open

    def test_exact_50_percent_is_doji(self):
        """Body exactly 50% of range → doji (not trend)."""
        # open=100, high=110, low=90, close=110 → body=10, range=20 → 50%
        bar_type, body_pct = classify_bar_type(100.0, 110.0, 90.0, 110.0)
        assert body_pct == 50
        assert bar_type == "bull_doji"  # 50% is NOT > 50, so it's doji


# ==================== classify_close_position ====================

class TestClassifyClosePosition:

    def test_close_high(self):
        pos = classify_close_position(100.0, 110.0, 90.0, 108.0)
        assert pos == "high"

    def test_close_mid(self):
        pos = classify_close_position(100.0, 110.0, 90.0, 100.0)
        assert pos == "mid"

    def test_close_low(self):
        pos = classify_close_position(100.0, 110.0, 90.0, 92.0)
        assert pos == "low"

    def test_close_at_boundary_high(self):
        """67% position should be 'high'."""
        # low=0, high=100, close=67 → (67-0)/100 = 0.67 ≥ 0.67
        pos = classify_close_position(50.0, 100.0, 0.0, 67.0)
        assert pos == "high"

    def test_close_at_boundary_low(self):
        """33% position should be 'low'."""
        pos = classify_close_position(50.0, 100.0, 0.0, 33.0)
        assert pos == "low"

    def test_zero_range(self):
        pos = classify_close_position(100.0, 100.0, 100.0, 100.0)
        assert pos == "mid"


# ==================== classify_ema_relation ====================

class TestClassifyEmaRelation:

    def test_above_ema(self):
        rel, dist = classify_ema_relation(close=110.0, ema=100.0, atr=10.0)
        assert rel == "above"
        assert dist > 50  # 100%

    def test_below_ema(self):
        rel, dist = classify_ema_relation(close=90.0, ema=100.0, atr=10.0)
        assert rel == "below"
        assert dist < -50

    def test_at_ema(self):
        """Within 0.5 ATR → 'at'."""
        rel, dist = classify_ema_relation(close=103.0, ema=100.0, atr=10.0)
        assert rel == "at"
        assert abs(dist) <= 50

    def test_zero_atr(self):
        rel, dist = classify_ema_relation(close=110.0, ema=100.0, atr=0.0)
        assert rel == "at"
        assert dist == 0.0


# ==================== detect_bar_patterns ====================

class TestDetectBarPatterns:

    def test_inside_bar(self):
        """Current bar completely inside previous bar."""
        is_inside, is_outside, is_reversal = detect_bar_patterns(
            curr_open=102.0, curr_high=105.0, curr_low=98.0, curr_close=103.0,
            prev_high=110.0, prev_low=95.0
        )
        assert is_inside is True
        assert is_outside is False

    def test_outside_bar(self):
        """Current bar engulfs previous bar."""
        is_inside, is_outside, is_reversal = detect_bar_patterns(
            curr_open=102.0, curr_high=115.0, curr_low=90.0, curr_close=103.0,
            prev_high=110.0, prev_low=95.0
        )
        assert is_inside is False
        assert is_outside is True

    def test_reversal_bar(self):
        """Bar with long tail (>40% tail ratio)."""
        # range = 20, body = 2 → tail_pct = 90% → reversal
        is_inside, is_outside, is_reversal = detect_bar_patterns(
            curr_open=100.0, curr_high=110.0, curr_low=90.0, curr_close=101.0,
            prev_high=105.0, prev_low=95.0
        )
        assert is_reversal is True

    def test_normal_bar(self):
        """Normal bar — not inside, not outside, not reversal."""
        # range = 10, body = 8 → tail_pct = 20% → not reversal
        is_inside, is_outside, is_reversal = detect_bar_patterns(
            curr_open=100.0, curr_high=109.0, curr_low=99.0, curr_close=108.0,
            prev_high=105.0, prev_low=95.0
        )
        assert is_inside is False
        assert is_outside is False
        assert is_reversal is False

    def test_zero_range_no_reversal(self):
        is_inside, is_outside, is_reversal = detect_bar_patterns(
            curr_open=100.0, curr_high=100.0, curr_low=100.0, curr_close=100.0,
            prev_high=105.0, prev_low=95.0
        )
        assert is_reversal is False
        assert is_inside is True


# ==================== L0Preprocessor ====================

class TestL0Preprocessor:

    @pytest.fixture
    def preprocessor(self):
        return L0Preprocessor(dead_market_threshold=0.3)

    def test_extract_bar_features_basic(self, preprocessor):
        bar = {"open": 100.0, "high": 110.0, "low": 95.0, "close": 108.0}
        prev = {"open": 98.0, "high": 105.0, "low": 94.0, "close": 102.0}

        feature = preprocessor.extract_bar_features(bar, prev, ema20=100.0, atr=5.0, bar_index=0)

        assert isinstance(feature, BarFeatures)
        assert feature.bar_index == 0
        assert feature.bar_type == "bull_trend"  # body > 50%
        assert feature.close_position == "high"   # close near high
        assert feature.ema_relation == "above"     # 108 > 100 + 0.5*5

    def test_extract_bar_features_no_prev(self, preprocessor):
        bar = {"open": 100.0, "high": 110.0, "low": 95.0, "close": 108.0}

        feature = preprocessor.extract_bar_features(bar, None, ema20=100.0, atr=5.0)

        assert feature.is_inside_bar is False
        assert feature.is_outside_bar is False
        assert feature.is_reversal_bar is False

    def test_h_counter_increments(self, preprocessor):
        """H counter should increment on higher highs."""
        bars = [
            {"open": 100, "high": 105, "low": 95, "close": 103},
            {"open": 103, "high": 108, "low": 100, "close": 106},  # higher high
            {"open": 106, "high": 112, "low": 103, "close": 110},  # higher high
        ]

        features = []
        for i, bar in enumerate(bars):
            prev = bars[i-1] if i > 0 else None
            f = preprocessor.extract_bar_features(bar, prev, ema20=100.0, atr=5.0, bar_index=i)
            features.append(f)

        assert features[-1].h_count == 2

    def test_l_counter_resets_on_strong_bull(self, preprocessor):
        """L counter should reset on a strong bull trend bar."""
        bar_with_low = {"open": 100, "high": 105, "low": 90, "close": 92}
        strong_bull = {"open": 92, "high": 110, "low": 91, "close": 109}  # body > 60%

        preprocessor.extract_bar_features(bar_with_low, None, 100.0, 5.0)
        prev = bar_with_low

        # This bar makes a lower low, incrementing l_count
        preprocessor._l_counter = 1

        f = preprocessor.extract_bar_features(strong_bull, prev, 100.0, 5.0)
        # Strong bull bar body_pct > 60 and "bull" in bar_type → resets l_counter
        assert f.l_count == 0

    def test_encode_to_brooks_notation(self, preprocessor):
        feature = BarFeatures(
            bar_index=0,
            bar_type="bull_trend",
            body_pct=75,
            close_position="high",
            ema_relation="above",
            ema_distance_pct=120.0,
            h_count=2,
            l_count=0,
            is_inside_bar=False,
            is_outside_bar=False,
            is_reversal_bar=False
        )

        notation = preprocessor.encode_to_brooks_notation(feature)

        assert "Bull Trend" in notation
        assert "Cl High" in notation
        assert "EMA+" in notation
        assert "H2" in notation

    def test_encode_reversal_bar_notation(self, preprocessor):
        feature = BarFeatures(
            bar_index=-1,
            bar_type="bear_doji",
            body_pct=20,
            close_position="low",
            ema_relation="below",
            ema_distance_pct=-80.0,
            h_count=0,
            l_count=1,
            is_inside_bar=True,
            is_outside_bar=False,
            is_reversal_bar=True
        )

        notation = preprocessor.encode_to_brooks_notation(feature)

        assert "Bear Doji" in notation
        assert "IB" in notation
        assert "Rev" in notation
        assert "L1" in notation

    def test_encode_recent_bars(self, preprocessor):
        features = [
            BarFeatures(bar_index=-2, bar_type="bull_trend", body_pct=70,
                       close_position="high", ema_relation="above", ema_distance_pct=100.0,
                       h_count=1, l_count=0, is_inside_bar=False, is_outside_bar=False, is_reversal_bar=False),
            BarFeatures(bar_index=-1, bar_type="bear_doji", body_pct=30,
                       close_position="mid", ema_relation="at", ema_distance_pct=10.0,
                       h_count=0, l_count=0, is_inside_bar=False, is_outside_bar=False, is_reversal_bar=False),
            BarFeatures(bar_index=0, bar_type="bull_trend", body_pct=80,
                       close_position="high", ema_relation="above", ema_distance_pct=150.0,
                       h_count=2, l_count=0, is_inside_bar=False, is_outside_bar=False, is_reversal_bar=False),
        ]

        text = preprocessor.encode_recent_bars(features, count=2)
        lines = text.strip().split("\n")
        assert len(lines) == 2
        assert "Bar -1" in lines[0]
        assert "Bar 0" in lines[1]

    def test_bar_features_to_dict(self):
        feature = BarFeatures(
            bar_index=0, bar_type="bull_trend", body_pct=70,
            close_position="high", ema_relation="above", ema_distance_pct=100.0,
            h_count=1, l_count=0, is_inside_bar=False, is_outside_bar=False, is_reversal_bar=False
        )
        d = feature.to_dict()
        assert isinstance(d, dict)
        assert d["bar_type"] == "bull_trend"
        assert d["body_pct"] == 70


# ==================== MarketContext ====================

class TestMarketContext:

    def test_get_market_context_empty_bars(self):
        preprocessor = L0Preprocessor()
        ctx = preprocessor.get_market_context([])
        assert ctx.is_dead_market is True
        assert ctx.atr_14 == 0.0

    @patch("src.utils.l0_preprocessor.calculate_atr")
    def test_dead_market_detection(self, mock_atr):
        """Low ATR relative to price → dead market."""
        mock_atr.return_value = 0.2  # ATR = 0.2
        bars = [{"open": 100, "high": 100.5, "low": 99.5, "close": 100}] * 20

        preprocessor = L0Preprocessor(dead_market_threshold=0.3)
        ctx = preprocessor.get_market_context(bars)

        # ATR% = 0.2/100 * 100 = 0.2% < 0.3% threshold
        assert ctx.is_dead_market is True

    @patch("src.utils.l0_preprocessor.calculate_atr")
    def test_active_market(self, mock_atr):
        """Normal ATR → not dead market."""
        mock_atr.return_value = 5.0
        bars = [{"open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 103 + i} for i in range(20)]

        preprocessor = L0Preprocessor(dead_market_threshold=0.3)
        ctx = preprocessor.get_market_context(bars)

        # ATR% = 5/122 * 100 ≈ 4.1% > 0.3%
        assert ctx.is_dead_market is False
        assert ctx.atr_14 == 5.0

    @patch("src.utils.l0_preprocessor.calculate_atr")
    def test_price_position_in_range(self, mock_atr):
        """Price position should be between 0 and 1."""
        mock_atr.return_value = 5.0
        bars = [{"open": 100, "high": 110, "low": 90, "close": 100}] * 20

        preprocessor = L0Preprocessor()
        ctx = preprocessor.get_market_context(bars)

        # close=100, range 90-110, position = (100-90)/20 = 0.5
        assert ctx.price_position_in_range == pytest.approx(0.5, abs=0.01)
        assert ctx.recent_high == 110.0
        assert ctx.recent_low == 90.0

    def test_market_context_to_dict(self):
        ctx = MarketContext(
            atr_14=5.0, atr_pct=2.5, is_dead_market=False,
            ema20=100.0, recent_high=110.0, recent_low=90.0, price_position_in_range=0.5
        )
        d = ctx.to_dict()
        assert isinstance(d, dict)
        assert d["atr_14"] == 5.0


# ==================== Volatility Gate ====================

class TestVolatilityGate:

    @patch("src.utils.l0_preprocessor.calculate_atr")
    def test_dead_market_gates(self, mock_atr):
        mock_atr.return_value = 0.1
        bars = [{"open": 100, "high": 100.2, "low": 99.8, "close": 100}] * 20

        preprocessor = L0Preprocessor(dead_market_threshold=0.3)
        result = preprocessor.check_volatility_gate(bars)
        assert result is True  # Dead market, should skip

    @patch("src.utils.l0_preprocessor.calculate_atr")
    def test_active_market_passes(self, mock_atr):
        mock_atr.return_value = 5.0
        bars = [{"open": 100, "high": 105, "low": 95, "close": 103}] * 20

        preprocessor = L0Preprocessor(dead_market_threshold=0.3)
        result = preprocessor.check_volatility_gate(bars)
        assert result is False  # Active market, don't skip


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
