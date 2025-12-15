"""
Tests for risk_manager node
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.nodes.risk_manager import (
    manage_risk,
    update_stop_loss_order,
    calculate_measured_move_target,
    check_stop_hit,
    calculate_pnl
)


class TestManageRisk:
    """Test dynamic risk management"""
    
    @pytest.fixture
    def profitable_long_state(self):
        """State with profitable long position"""
        return {
            "status": "managing_position",
            "symbol": "BTC/USDT:USDT",
            "exchange": "bitget",
            "position": {
                "side": "long",
                "entry_price": 90000.0,
                "size": 0.001
            },
            "stop_loss": 89000.0,
            "current_bar": {"close": 91000.0},  # $1000 profit
            "breakeven_locked": False
        }
    
    def test_skip_if_not_managing(self):
        """Should skip if not managing position"""
        state = {"status": "looking_for_trade"}
        result = manage_risk(state)
        assert result == state
    
    @patch('src.nodes.risk_manager.update_stop_loss_order')
    @patch('src.nodes.risk_manager.notify_trade_event')
    def test_move_to_breakeven(self, mock_notify, mock_update, profitable_long_state):
        """Should move stop to breakeven when profit >= risk"""
        mock_update.return_value = True
        
        result = manage_risk(profitable_long_state)
        
        # Should update stop to entry price
        mock_update.assert_called_once()
        assert result["stop_loss"] == 90000.0  # Entry price
        assert result["breakeven_locked"] is True
        
        # Should notify
        mock_notify.assert_called_once()
        assert "breakeven" in mock_notify.call_args[1]["reason"].lower()
    
    @patch('src.nodes.risk_manager.update_stop_loss_order')
    def test_trailing_stop_long(self, mock_update):
        """Should trail stop for long position"""
        mock_update.return_value = True
        
        state = {
            "status": "managing_position",
            "position": {"side": "long", "entry_price": 90000, "size": 0.001},
            "stop_loss": 90000,  # Already at breakeven
            "breakeven_locked": True,
            "bars": [
                {"low": 89500, "high": 91000},  # Previous bar
                {"low": 90500, "high": 92000}   # Current bar
            ],
            "current_bar": {"close": 91500},
            "symbol": "BTC/USDT:USDT",
            "exchange": "bitget"
        }
        
        result = manage_risk(state)
        
        # Should trail to previous bar low
        assert result["stop_loss"] == 89500
    
    @patch('src.nodes.risk_manager.update_stop_loss_order')
    def test_trailing_stop_short(self, mock_update):
        """Should trail stop for short position"""
        mock_update.return_value = True
        
        state = {
            "status": "managing_position",
            "position": {"side": "short", "entry_price": 90000, "size": 0.001},
            "stop_loss": 90000,
            "breakeven_locked": True,
            "bars": [
                {"low": 89000, "high": 90500},
                {"low": 88000, "high": 89500}
            ],
            "current_bar": {"close": 88500},
            "symbol": "BTC/USDT:USDT",
            "exchange": "bitget"
        }
        
        result = manage_risk(state)
        
        # Should trail to previous bar high
        assert result["stop_loss"] == 90500


class TestCheckStopHit:
    """Test stop loss hit detection"""
    
    @patch('src.nodes.risk_manager.close_position_market')
    @patch('src.nodes.risk_manager.notify_trade_event')
    def test_long_stop_hit(self, mock_notify, mock_close):
        """Should close position when long stop is hit"""
        state = {
            "status": "managing_position",
            "position": {"side": "long", "entry_price": 90000, "size": 0.001},
            "stop_loss": 89000,
            "current_bar": {"low": 88800, "high": 90500, "close": 89000},
            "current_bar_index": 15,
            "entry_bar_index": 10
        }
        
        result = check_stop_hit(state)
        
        # Should close position
        mock_close.assert_called_once()
        
        # Should notify
        mock_notify.assert_called_once()
        assert mock_notify.call_args[0][0] == "exit"
        
        # Should reset state
        assert result["status"] == "looking_for_trade"
        assert result["position"] is None
        assert result["exit_reason"] == "stop_loss_hit"
    
    @patch('src.nodes.risk_manager.close_position_market')
    def test_short_stop_hit(self, mock_close):
        """Should close position when short stop is hit"""
        state = {
            "status": "managing_position",
            "position": {"side": "short", "entry_price": 90000, "size": 0.001},
            "stop_loss": 91000,
            "current_bar": {"low": 89500, "high": 91200, "close": 90800},
            "current_bar_index": 12,
            "entry_bar_index": 10
        }
        
        result = check_stop_hit(state)
        
        mock_close.assert_called_once()
        assert result["status"] == "looking_for_trade"
    
    def test_no_stop_hit(self):
        """Should not close if stop not hit"""
        state = {
            "status": "managing_position",
            "position": {"side": "long", "entry_price": 90000, "size": 0.001},
            "stop_loss": 89000,
            "current_bar": {"low": 89500, "high": 91000, "close": 90500}
        }
        
        result = check_stop_hit(state)
        
        # State unchanged
        assert result["status"] == "managing_position"


class TestCalculateMeasuredMove:
    """Test measured move target calculation"""
    
    def test_long_measured_move(self):
        """Should calculate measured move for long"""
        bars = [
            {"low": 88000, "high": 89000},
            {"low": 88500, "high": 90000},
            {"low": 89000, "high": 91000},
            {"low": 89500, "high": 92000},
            {"low": 90000, "high": 93000},
        ] * 4  # 20 bars
        
        target = calculate_measured_move_target(bars, "long")
        
        assert target is not None
        assert target > 93000  # Should be above recent high
    
    def test_insufficient_bars(self):
        """Should return None if insufficient data"""
        bars = [{"low": 90000, "high": 91000}] * 10
        
        target = calculate_measured_move_target(bars, "long")
        
        assert target is None


class TestCalculatePnL:
    """Test PnL calculation"""
    
    def test_long_profit(self):
        """Should calculate long profit correctly"""
        state = {
            "position": {
                "side": "long",
                "entry_price": 90000.0,
                "size": 0.01
            },
            "current_bar": {"close": 91000.0}
        }
        
        pnl = calculate_pnl(state)
        
        assert pnl == 10.0  # (91000 - 90000) * 0.01
    
    def test_short_profit(self):
        """Should calculate short profit correctly"""
        state = {
            "position": {
                "side": "short",
                "entry_price": 90000.0,
                "size": 0.01
            },
            "current_bar": {"close": 89000.0}
        }
        
        pnl = calculate_pnl(state)
        
        assert pnl == 10.0  # (90000 - 89000) * 0.01
    
    def test_long_loss(self):
        """Should calculate long loss correctly"""
        state = {
            "position": {
                "side": "long",
                "entry_price": 90000.0,
                "size": 0.01
            },
            "current_bar": {"close": 89000.0}
        }
        
        pnl = calculate_pnl(state)
        
        assert pnl == -10.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
