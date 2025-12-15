"""
Integration tests for complete position management workflow
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.position_management_workflow import (
    create_position_management_workflow,
    PositionManagementState
)
from src.safety import ConvictionTracker


class TestPositionManagementWorkflow:
    """Test complete workflow integration"""
    
    @pytest.fixture
    def workflow_app(self):
        """Create compiled workflow"""
        workflow = create_position_management_workflow()
        return workflow.compile()
    
    @pytest.fixture
    def initial_managing_state(self):
        """State with active position"""
        return {
            "symbol": "BTC/USDT:USDT",
            "exchange": "bitget",
            "status": "managing_position",
            "position": {
                "side": "long",
                "entry_price": 90000.0,
                "size": 0.001,
                "leverage": 20,
                "unrealized_pnl": 100.0
            },
            "entry_bar_index": 100,
            "current_bar_index": 102,
            "stop_loss": 89000.0,
            "take_profit": 95000.0,
            "breakeven_locked": False,
            "followthrough_checked": False,
            "should_exit": False,
            "conviction_tracker": ConvictionTracker(),
            "account_balance": 10000.0,
            "timeframe": 60,
            "bars": [
                {"open":89500,"high":90000,"low":89000,"close":89800,"close_time":datetime.now()-timedelta(hours=3)},
                {"open":89800,"high":90500,"low":89700,"close":90000,"close_time":datetime.now()-timedelta(hours=2)},
                {"open":90000,"high":91500,"low":89900,"close":91200,"close_time":datetime.now()-timedelta(hours=1)},
                {"open":91200,"high":92000,"low":91000,"close":91800,"close_time":datetime.now()},
            ],
            "current_bar": {"open":91200,"high":92000,"low":91000,"close":91800,"close_time":datetime.now()}
        }
    
    @patch('src.nodes.position_sync.get_client')
    @patch('src.nodes.risk_manager.update_stop_loss_order')
    def test_complete_managing_cycle(self, mock_update_stop, mock_get_client, workflow_app, initial_managing_state):
        """Test complete managing position cycle"""
        # Mock exchange client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock position sync
        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"
        mock_position.entry_price = 90000.0
        mock_position.size = 0.001
        mock_position.side = "long"
        mock_position.unrealized_pnl = 500.0
        mock_position.leverage = 20
        
        mock_client.get_positions.return_value = [mock_position]
        
        # Mock account info
        mock_balance = Mock()
        mock_balance.total = 10000.0
        mock_balance.used = 500.0
        mock_client.get_account_info.return_value = mock_balance
        
        # Mock stop loss update
        mock_update_stop.return_value = True
        
        # Run workflow
        result = workflow_app.invoke(initial_managing_state)
        
        # Assertions
        assert "last_followthrough_analysis" in result
        assert result["followthrough_checked"] is True
        
        # Should have analyzed follow-through
        analysis = result["last_followthrough_analysis"]
        assert analysis["follow_through_quality"] in ["strong", "weak", "disappointing"]
    
    @patch('src.nodes.order_monitor.get_client')
    def test_order_pending_to_filled(self, mock_get_client, workflow_app):
        """Test order pending -> filled -> managing transition"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Order is filled
        mock_client.exchange.fetch_order.return_value = {"status": "filled"}
        
        # Mock position
        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"
        mock_position.entry_price = 90500.0
        mock_position.size = 0.001
        mock_position.side = "long"
        mock_position.unrealized_pnl = 0.0
        mock_position.leverage = 20
        
        mock_client.get_positions.return_value = [mock_position]
        
        # Initial state: order pending
        state = {
            "status": "order_pending",
            "symbol": "BTC/USDT:USDT",
            "exchange": "bitget",
            "pending_order_id": "order123",
            "order_placed_time": datetime.now() - timedelta(minutes=65),
            "current_bar": {"close_time": datetime.now()},
            "current_bar_index": 5,
            "timeframe": 60,
            "conviction_tracker": ConvictionTracker(),
            "account_balance": 10000.0,
            "bars": [],
            "breakeven_locked": False,
            "followthrough_checked": False,
            "should_exit": False
        }
        
        result = workflow_app.invoke(state)
        
        # Should transition to managing
        assert result["status"] == "managing_position"
        assert result["position"]["entry_price"] == 90500.0
    
    @patch('src.nodes.risk_manager.close_position_market')
    @patch('src.nodes.risk_manager.notify_trade_event')
    @patch('src.nodes.position_sync.get_client')
    def test_stop_loss_hit_exit(self, mock_get_client, mock_notify, mock_close, workflow_app):
        """Test automatic exit when stop loss is hit"""
        # Mock client for sync
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"
        mock_position.entry_price = 90000.0
        mock_position.size = 0.001
        mock_position.side = "long"
        mock_position.unrealized_pnl = -900.0
        mock_position.leverage = 20
        
        mock_client.get_positions.return_value = [mock_position]
        
        mock_balance = Mock()
        mock_balance.total = 10000.0
        mock_balance.used = 500.0
        mock_client.get_account_info.return_value = mock_balance
        
        # State with stop loss about to be hit
        state = {
            "status": "managing_position",
            "symbol": "BTC/USDT:USDT",
            "exchange": "bitget",
            "position": {
                "side": "long",
                "entry_price": 90000.0,
                "size": 0.001,
                "leverage": 20
            },
            "entry_bar_index": 10,
            "current_bar_index": 12,
            "stop_loss": 89100.0,
            "current_bar": {
                "low": 88900.0,  # Hit stop loss!
                "high": 90500.0,
                "close": 89000.0,
                "close_time": datetime.now()
            },
            "breakeven_locked": False,
            "followthrough_checked": False,
            "should_exit": False,
            "conviction_tracker": ConvictionTracker(),
            "account_balance": 10000.0,
            "timeframe": 60,
            "bars": []
        }
        
        result = workflow_app.invoke(state)
        
        # Should close position
        mock_close.assert_called_once()
        
        # Should reset to hunting mode
        assert result["status"] == "looking_for_trade"
        assert result["position"] is None


class TestEndToEndScenarios:
    """Test complete realistic trading scenarios"""
    
    @patch('src.nodes.position_sync.get_client')
    @patch('src.nodes.risk_manager.update_stop_loss_order')
    def test_profitable_trade_with_breakeven(self, mock_update_stop, mock_get_client):
        """Test a profitable trade that moves to breakeven"""
        workflow = create_position_management_workflow()
        app = workflow.compile()
        
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_update_stop.return_value = True
        
        # Entry at 90000, currently at 91000 (profit >= risk)
        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"
        mock_position.entry_price = 90000.0
        mock_position.size = 0.001
        mock_position.side = "long"
        mock_position.unrealized_pnl = 1000.0
        mock_position.leverage = 20
        
        mock_client.get_positions.return_value = [mock_position]
        
        mock_balance = Mock()
        mock_balance.total = 10000.0
        mock_balance.used = 500.0
        mock_client.get_account_info.return_value = mock_balance
        
        state = {
            "status": "managing_position",
            "symbol": "BTC/USDT:USDT",
            "exchange": "bitget",
            "position": {
                "side": "long",
                "entry_price": 90000.0,
                "size": 0.001
            },
            "entry_bar_index": 10,
            "current_bar_index": 11,
            "stop_loss": 89000.0,  # Risk = 1000
            "current_bar": {"close": 91000.0},  # Profit = 1000
            "breakeven_locked": False,
            "followthrough_checked": False,
            "should_exit": False,
            "conviction_tracker": ConvictionTracker(),
            "account_balance": 10000.0,
            "timeframe": 60,
            "bars": [
                {"open": 90000, "high": 91500, "low": 89900, "close": 91000}
            ]
        }
        
        result = app.invoke(state)
        
        # Stop should be moved to breakeven
        assert result["breakeven_locked"] is True
        assert result["stop_loss"] == 90000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
