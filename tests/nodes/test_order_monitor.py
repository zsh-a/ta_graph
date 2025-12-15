"""
Tests for order_monitor node
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.nodes.order_monitor import monitor_pending_order, confirm_order_fill


class TestMonitorPendingOrder:
    """Test order monitoring functionality"""
    
    @pytest.fixture
    def base_state(self):
        """Base state for testing"""
        return {
            "status": "order_pending",
            "symbol": "BTC/USDT:USDT",
            "exchange": "bitget",
            "pending_order_id": "order123",
            "order_placed_time": datetime.now() - timedelta(minutes=5),
            "current_bar": {
                "close_time": datetime.now(),
                "close": 90000
            },
            "timeframe": 60,
            "current_bar_index": 10
        }
    
    def test_skip_if_not_pending(self):
        """Should skip if status is not order_pending"""
        state = {"status": "looking_for_trade"}
        result = monitor_pending_order(state)
        assert result == state
    
    @patch('src.nodes.order_monitor.get_client')
    def test_cancel_order_if_timeout(self, mock_get_client, base_state):
        """Should cancel order if K-line closed and order not filled"""
        # Mock exchange client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Order still open after timeout
        mock_client.exchange.fetch_order.return_value = {"status": "open"}
        
        # Order was placed more than timeframe ago
        base_state["order_placed_time"] = datetime.now() - timedelta(minutes=65)
        
        result = monitor_pending_order(base_state)
        
        # Should cancel order
        mock_client.cancel_order.assert_called_once_with(
            "order123",
            "BTC/USDT:USDT"
        )
        
        # Should reset status
        assert result["status"] == "looking_for_trade"
        assert result["pending_order_id"] is None
        assert "cancel_reason" in result
    
    @patch('src.nodes.order_monitor.get_client')
    def test_switch_to_managing_if_filled(self, mock_get_client, base_state):
        """Should switch to managing_position if order filled"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Order filled
        mock_client.exchange.fetch_order.return_value = {"status": "filled"}
        
        # Mock position data
        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"
        mock_position.entry_price = 90000.0
        mock_position.size = 0.001
        mock_position.side = "long"
        mock_position.unrealized_pnl = 0.0
        mock_position.leverage = 20
        
        mock_client.get_positions.return_value = [mock_position]
        
        # Set timeout
        base_state["order_placed_time"] = datetime.now() - timedelta(minutes=65)
        
        result = monitor_pending_order(base_state)
        
        # Should switch to managing
        assert result["status"] == "managing_position"
        assert result["position"]["entry_price"] == 90000.0
        assert result["position"]["side"] == "long"
        assert result["pending_order_id"] is None
    
    @patch('src.nodes.order_monitor.get_client')
    def test_wait_if_within_timeframe(self, mock_get_client, base_state):
        """Should wait if order still within K-line timeframe"""
        # Order placed 30 minutes ago, timeframe is 60 minutes
        base_state["order_placed_time"] = datetime.now() - timedelta(minutes=30)
        
        result = monitor_pending_order(base_state)
        
        # Should not call exchange (still waiting)
        mock_get_client.assert_not_called()
        
        # State unchanged
        assert result["status"] == "order_pending"


class TestConfirmOrderFill:
    """Test immediate order fill confirmation"""
    
    @pytest.fixture
    def filled_state(self):
        return {
            "pending_order_id": "order456",
            "symbol": "BTC/USDT:USDT",
            "exchange": "bitget",
            "current_bar_index": 5
        }
    
    @patch('src.nodes.order_monitor.get_client')
    def test_confirm_filled_order(self, mock_get_client, filled_state):
        """Should confirm and update state when order is filled"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Order is filled
        mock_client.exchange.fetch_order.return_value = {
            "status": "filled",
            "average": 90500.0
        }
        
        # Mock position
        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"
        mock_position.entry_price = 90500.0
        mock_position.size = 0.002
        mock_position.side = "short"
        mock_position.unrealized_pnl = 50.0
        mock_position.leverage = 10
        
        mock_client.get_positions.return_value = [mock_position]
        
        result = confirm_order_fill(filled_state)
        
        assert result["status"] == "managing_position"
        assert result["position"]["entry_price"] == 90500.0
        assert result["position"]["side"] == "short"
        assert result["pending_order_id"] is None
    
    @patch('src.nodes.order_monitor.get_client')
    def test_handle_canceled_order(self, mock_get_client, filled_state):
        """Should handle externally canceled orders"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_client.exchange.fetch_order.return_value = {"status": "canceled"}
        
        result = confirm_order_fill(filled_state)
        
        assert result["status"] == "looking_for_trade"
        assert result["pending_order_id"] is None
        assert "cancel_reason" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
