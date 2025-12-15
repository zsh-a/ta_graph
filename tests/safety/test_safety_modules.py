"""
Tests for safety modules
"""

import pytest
from datetime import datetime, date, timedelta

from src.safety.equity_protector import EquityProtector
from src.safety.conviction_tracker import (
    ConvictionTracker,
    check_hallucination_guard,
    is_tight_trading_range
)


class TestEquityProtector:
    """Test equity protection mechanisms"""
    
    def test_daily_loss_limit(self):
        """Should disable trading when daily loss limit hit"""
        protector = EquityProtector(max_daily_loss_pct=2.0)
        account_balance = 10000.0
        
        # First loss
        protector.update_trade_result(-100, account_balance)
        assert protector.can_trade() is True
        
        # Second loss pushes over 2%
        protector.update_trade_result(-110, account_balance)
        assert protector.can_trade() is False
        assert protector.daily_pnl == -210
    
    def test_consecutive_losses(self):
        """Should enter cooldown after consecutive losses"""
        protector = EquityProtector(max_consecutive_losses=3, cooldown_hours=2)
        
        # Three consecutive losses
        protector.update_trade_result(-50, 10000)
        protector.update_trade_result(-50, 10000)
        protector.update_trade_result(-50, 10000)
        
        assert protector.can_trade() is False
        assert protector.consecutive_losses == 3
        assert protector.cooldown_until is not None
    
    def test_reset_on_win(self):
        """Should reset consecutive losses on win"""
        protector = EquityProtector()
        
        protector.update_trade_result(-50, 10000)
        protector.update_trade_result(-50, 10000)
        assert protector.consecutive_losses == 2
        
        # Win resets counter
        protector.update_trade_result(100, 10000)
        assert protector.consecutive_losses == 0
    
    def test_daily_reset(self):
        """Should reset daily PnL on new day"""
        protector = EquityProtector()
        protector.daily_pnl = -200
        protector.trading_enabled = False
        protector.last_reset_date = date.today() - timedelta(days=1)
        
        # Check on new day
        can_trade = protector.can_trade()
        
        assert can_trade is True
        assert protector.daily_pnl == 0.0
    
    def test_get_status(self):
        """Should return current status"""
        protector = EquityProtector()
        protector.update_trade_result(-50, 10000)
        
        status = protector.get_status()
        
        assert status["trading_enabled"] is True
        assert status["daily_pnl"] == -50
        assert status["consecutive_losses"] == 1


class TestConvictionTracker:
    """Test conviction tracking"""
    
    def test_insufficient_signals(self):
        """Should require minimum consecutive signals"""
        tracker = ConvictionTracker(min_consecutive=2)
        
        tracker.add_signal("buy", 0.9, "Strong setup")
        
        # Only one signal
        assert tracker.evaluate_conviction() is False
    
    def test_consistent_signals(self):
        """Should approve consistent high-confidence signals"""
        tracker = ConvictionTracker(min_consecutive=2)
        
        tracker.add_signal("buy", 0.85, "Setup 1")
        tracker.add_signal("buy", 0.90, "Setup 2")
        
        assert tracker.evaluate_conviction() is True
    
    def test_inconsistent_signals(self):
        """Should reject inconsistent signals"""
        tracker = ConvictionTracker(min_consecutive=2)
        
        tracker.add_signal("buy", 0.85, "Setup 1")
        tracker.add_signal("sell", 0.80, "Setup 2")  # Different action
        
        assert tracker.evaluate_conviction() is False
    
    def test_low_confidence(self):
        """Should reject low confidence signals"""
        tracker = ConvictionTracker(min_consecutive=2)
        
        tracker.add_signal("buy", 0.85, "Setup 1")
        tracker.add_signal("buy", 0.60, "Setup 2")  # Low confidence
        
        assert tracker.evaluate_conviction() is False
    
    def test_specific_action_check(self):
        """Should check for specific required action"""
        tracker = ConvictionTracker(min_consecutive=2)
        
        tracker.add_signal("sell", 0.85)
        tracker.add_signal("sell", 0.90)
        
        # Looking for "buy" but got "sell"
        assert tracker.evaluate_conviction("buy") is False
        
        # Looking for "sell"
        assert tracker.evaluate_conviction("sell") is True


class TestHallucinationGuard:
    """Test hallucination protection"""
    
    def test_block_trading_in_ttr(self):
        """Should block trading in tight trading range"""
        state = {
            "bars": [{"high": 90100, "low": 89900, "open": 90000, "close": 90000}] * 20
        }
        decision = {"action": "buy"}
        
        # TTR detected
        assert is_tight_trading_range(state) is True
        
        # Should block
        assert check_hallucination_guard(state, decision) is False
    
    def test_block_weak_reversal(self):
        """Should block weak reversal signals"""
        state = {
            "status": "managing_position",
            "position": {"side": "long"},
            "bars": []
        }
        decision = {
            "action": "reverse",
            "reversal_strength": "weak"  # Not strong enough
        }
        
        assert check_hallucination_guard(state, decision) is False
    
    def test_allow_strong_reversal(self):
        """Should allow very strong reversal"""
        state = {
            "status": "managing_position",
            "position": {"side": "long"},
            "bars": []
        }
        decision = {
            "action": "reverse",
            "reversal_strength": "very_strong"
        }
        
        assert check_hallucination_guard(state, decision) is True
    
    def test_require_conviction(self):
        """Should use conviction tracker"""
        tracker = ConvictionTracker(min_consecutive=2)
        tracker.add_signal("buy", 0.60)  # Low confidence
        
        state = {
            "conviction_tracker": tracker,
            "bars": []
        }
        decision = {"action": "buy"}
        
        # Not enough conviction
        assert check_hallucination_guard(state, decision) is False


class TestIsTightTradingRange:
    """Test TTR detection"""
    
    def test_detect_ttr(self):
        """Should detect tight trading range"""
        # 20 bars with small bodies and overlapping ranges
        bars = [
            {"high": 90100, "low": 89900, "open": 90000, "close": 90050}
            for _ in range(20)
        ]
        
        state = {"bars": bars}
        
        assert is_tight_trading_range(state) is True
    
    def test_not_ttr_trending(self):
        """Should not flag trending market as TTR"""
        bars = [
            {"high": 90000 + i*100, "low": 89000 + i*100, "open": 89500 + i*100, "close": 89800 + i*100}
            for i in range(20)
        ]
        
        state = {"bars": bars}
        
        assert is_tight_trading_range(state) is False
    
    def test_insufficient_bars(self):
        """Should return False if less than 20 bars"""
        state = {"bars": [{"high": 90000, "low": 89000}] * 10}
        
        assert is_tight_trading_range(state) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
