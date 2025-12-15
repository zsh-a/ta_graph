"""
Tests for followthrough_analyzer node
"""

import pytest
from src.nodes.followthrough_analyzer import (
    analyze_followthrough,
    analyze_followthrough_simple,
    calculate_tighter_stop
)


class TestAnalyzeFollowthrough:
    """Test follow-through analysis"""
    
    @pytest.fixture
    def long_position_state(self):
        """State with long position just entered"""
        return {
            "status": "managing_position",
            "position": {
                "side": "long",
                "entry_price": 90000.0,
                "size": 0.001
            },
            "entry_bar_index": 10,
            "current_bar_index": 11,  # One bar after entry
            "bars": [
                {"open": 89000, "high": 89500, "low": 88800, "close": 89200},
                {"open": 89200, "high": 90500, "low": 89100, "close": 90000},  # Entry bar
                {"open": 90000, "high": 91500, "low": 89900, "close": 91200},  # Follow-through bar
            ],
            "current_bar": {"open": 90000, "high": 91500, "low": 89900, "close": 91200}
        }
    
    def test_skip_if_not_managing(self):
        """Should skip if not managing position"""
        state = {"status": "looking_for_trade"}
        result = analyze_followthrough(state)
        assert result == state
    
    def test_skip_if_too_many_bars(self, long_position_state):
        """Should skip if more than 2 bars after entry"""
        long_position_state["current_bar_index"] = 13  # 3 bars after
        
        result = analyze_followthrough(long_position_state)
        
        # Should skip analysis
        assert result == long_position_state
    
    def test_strong_followthrough_long(self, long_position_state):
        """Should detect strong follow-through for long position"""
        result = analyze_followthrough(long_position_state)
        
        analysis = result.get("last_followthrough_analysis")
        assert analysis is not None
        assert analysis["follow_through_quality"] == "strong"
        assert analysis["recommendation"] == "hold"
        assert result.get("followthrough_checked") is True
    
    def test_disappointing_followthrough_long(self):
        """Should detect disappointing follow-through"""
        state = {
            "status": "managing_position",
            "position": {"side": "long", "entry_price": 90000.0},
            "entry_bar_index": 10,
            "current_bar_index": 11,
            "bars": [
                {"open": 89000, "high": 89500, "low": 88800, "close": 89200},
                {"open": 89200, "high": 90500, "low": 89100, "close": 90000},
                {"open": 90000, "high": 90200, "low": 89000, "close": 89100},  # Bearish bar!
            ],
            "current_bar": {"open": 90000, "high": 90200, "low": 89000, "close": 89100}
        }
        
        result = analyze_followthrough(state)
        
        analysis = result["last_followthrough_analysis"]
        assert analysis["follow_through_quality"] == "disappointing"
        assert analysis["recommendation"] == "exit_market"
        assert result.get("should_exit") is True


class TestAnalyzeFollowthroughSimple:
    """Test simple bar-based analysis"""
    
    def test_strong_bullish_bar(self):
        """Should identify strong bullish bar"""
        state = {
            "position": {"side": "long"},
            "entry_bar_index": 0,
            "bars": [
                {"open": 90000, "high": 91500, "low": 89900, "close": 91200}
            ]
        }
        
        result = analyze_followthrough_simple(state)
        
        assert result["follow_through_quality"] == "strong"
        assert result["recommendation"] == "hold"
        assert result["confidence"] >= 0.8
    
    def test_doji_pattern(self):
        """Should detect doji (indecision)"""
        state = {
            "position": {"side": "long"},
            "entry_bar_index": 0,
            "bars": [
                {"open": 90000, "high": 90000, "low": 90000, "close": 90000}
            ]
        }
        
        result = analyze_followthrough_simple(state)
        
        assert result["follow_through_quality"] == "weak"
        assert "Doji" in result["reasoning"]
    
    def test_bearish_after_long_entry(self):
        """Should flag bearish bar after long entry"""
        state = {
            "position": {"side": "long"},
            "entry_bar_index": 0,
            "bars": [
                {"open": 90000, "high": 90500, "low": 89000, "close": 89200}
            ]
        }
        
        result = analyze_followthrough_simple(state)
        
        assert result["follow_through_quality"] == "disappointing"
        assert result["recommendation"] == "exit_market"


class TestCalculateTighterStop:
    """Test tighter stop loss calculation"""
    
    def test_tighten_long_stop(self):
        """Should tighten long stop to current bar low"""
        state = {
            "position": {"side": "long", "entry_price": 90000},
            "stop_loss": 88000,
            "current_bar": {"low": 89500, "high": 91000}
        }
        
        new_stop = calculate_tighter_stop(state)
        
        assert new_stop == 89500
        assert new_stop > state["stop_loss"]
    
    def test_tighten_short_stop(self):
        """Should tighten short stop to current bar high"""
        state = {
            "position": {"side": "short", "entry_price": 90000},
            "stop_loss": 92000,
            "current_bar": {"low": 89000, "high": 90500}
        }
        
        new_stop = calculate_tighter_stop(state)
        
        assert new_stop == 90500
        assert new_stop < state["stop_loss"]
    
    def test_no_tighten_if_worse(self):
        """Should not tighten if new stop is worse"""
        state = {
            "position": {"side": "long", "entry_price": 90000},
            "stop_loss": 89500,
            "current_bar": {"low": 89000, "high": 91000}  # Low is below current stop
        }
        
        new_stop = calculate_tighter_stop(state)
        
        assert new_stop is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
