"""
Tests for position_sync node
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.nodes.position_sync import sync_position_state, check_position_health


class TestSyncPositionState:
    """Test position synchronization with exchange"""
    
    @pytest.fixture
    def managing_state(self):
        """State with active position"""
        return {
            "status": "managing_position",
            "symbol": "BTC/USDT:USDT",
            "exchange": "bitget",
            "position": {
                "entry_price": 90000.0,
                "size": 0.001,
                "side": "long"
            }
        }
    
    @patch('src.nodes.position_sync.send_alert')
    @patch('src.nodes.position_sync.get_client')
    def test_system_has_position_exchange_missing(self, mock_get_client, mock_alert, managing_state):
        """Should alert and reset if system thinks it has position but exchange doesn't"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Exchange has no positions
        mock_client.get_positions.return_value = []
        
        result = sync_position_state(managing_state)
        
        # Should send critical alert
        mock_alert.assert_called_once()
        assert mock_alert.call_args[1]["severity"] == "critical"
        
        # Should reset state
        assert result["status"] == "looking_for_trade"
        assert result["position"] is None
        assert "sync_error" in result
    
    @patch('src.nodes.position_sync.send_alert')
    @patch('src.nodes.position_sync.get_client')
    def test_exchange_has_position_system_missing(self, mock_get_client, mock_alert):
        """Should import position if exchange has it but system doesn't"""
        state = {
            "status": "looking_for_trade",
            "symbol": "BTC/USDT:USDT",
            "exchange": "bitget",
            "current_bar_index": 10
        }
        
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Exchange has position
        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"
        mock_position.entry_price = 91000.0
        mock_position.size = 0.002
        mock_position.side = "short"
        mock_position.unrealized_pnl = -100.0
        mock_position.leverage = 15
        
        mock_client.get_positions.return_value = [mock_position]
        
        result = sync_position_state(state)
        
        # Should import position
        assert result["status"] == "managing_position"
        assert result["position"]["entry_price"] == 91000.0
        assert result["position"]["side"] == "short"
        assert result.get("sync_imported") is True
        
        # Should send warning
        mock_alert.assert_called_once()
        assert mock_alert.call_args[1]["severity"] == "warning"
    
    @patch('src.nodes.position_sync.get_client')
    def test_size_mismatch_sync(self, mock_get_client, managing_state):
        """Should sync size if mismatch detected"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Exchange position with different size
        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"
        mock_position.entry_price = 90000.0
        mock_position.size = 0.0005  # Half the system size
        mock_position.side = "long"
        mock_position.unrealized_pnl = 25.0
        mock_position.leverage = 20
        
        mock_client.get_positions.return_value = [mock_position]
        
        result = sync_position_state(managing_state)
        
        # Should update to exchange size
        assert result["position"]["size"] == 0.0005
        assert result["position"]["unrealized_pnl"] == 25.0


class TestCheckPositionHealth:
    """Test position health checks"""
    
    @patch('src.nodes.position_sync.send_alert')
    @patch('src.nodes.position_sync.get_client')
    def test_high_margin_warning(self, mock_get_client, mock_alert):
        """Should warn if margin usage is high"""
        state = {
            "status": "managing_position",
            "exchange": "bitget",
            "position": {"size": 0.1}
        }
        
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # High margin usage
        mock_balance = Mock()
        mock_balance.total = 1000.0
        mock_balance.used = 850.0  # 85% usage
        
        mock_client.get_account_info.return_value = mock_balance
        
        result = check_position_health(state)
        
        # Should send warning
        mock_alert.assert_called_once()
        assert "High Margin" in mock_alert.call_args[0][0]
    
    def test_skip_if_not_managing(self):
        """Should skip health check if not managing position"""
        state = {"status": "looking_for_trade"}
        
        result = check_position_health(state)
        
        assert result == state


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
