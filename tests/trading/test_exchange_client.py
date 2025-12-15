"""
Unit tests for exchange_client module

Tests cover:
- Data class creation and validation
- ExchangeClient interface
- CCXTExchangeClient implementation (with mocking)
- get_client factory function
- Error handling
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
import os

from src.trading.exchange_client import (
    Balance,
    Position,
    OrderResult,
    ExchangeClient,
    CCXTExchangeClient,
    get_client,
    _clients
)


# ============================================================================
# Data Class Tests
# ============================================================================

class TestDataClasses:
    """Test data classes for type safety and structure"""
    
    def test_balance_creation(self):
        """Test Balance dataclass instantiation"""
        balance = Balance(
            total=10000.0,
            free=8000.0,
            used=2000.0,
            upnl=500.0
        )
        
        assert balance.total == 10000.0
        assert balance.free == 8000.0
        assert balance.used == 2000.0
        assert balance.upnl == 500.0
    
    def test_position_creation(self):
        """Test Position dataclass instantiation"""
        position = Position(
            symbol="BTC/USDT:USDT",
            side="long",
            size=0.5,
            entry_price=90000.0,
            mark_price=91000.0,
            unrealized_pnl=500.0,
            leverage=20.0,
            margin_type="isolated"
        )
        
        assert position.symbol == "BTC/USDT:USDT"
        assert position.side == "long"
        assert position.size == 0.5
        assert position.leverage == 20.0
    
    def test_order_result_creation(self):
        """Test OrderResult dataclass instantiation"""
        order = OrderResult(
            id="12345",
            symbol="BTC/USDT:USDT",
            side="buy",
            price=90000.0,
            amount=0.1,
            status="filled",
            filled=0.1,
            remaining=0.0
        )
        
        assert order.id == "12345"
        assert order.side == "buy"
        assert order.filled == 0.1
        assert order.remaining == 0.0


# ============================================================================
# CCXTExchangeClient Tests
# ============================================================================

class TestCCXTExchangeClient:
    """Test CCXTExchangeClient implementation with mocked CCXT"""
    
    @pytest.fixture
    def mock_ccxt(self):
        """Mock CCXT exchange"""
        with patch('src.trading.exchange_client.ccxt') as mock:
            # Mock exchange class
            mock_exchange_class = MagicMock()
            mock.bitget = mock_exchange_class
            
            # Mock exchange instance
            mock_exchange_instance = MagicMock()
            mock_exchange_class.return_value = mock_exchange_instance
            
            yield mock, mock_exchange_instance
    
    def test_client_initialization(self, mock_ccxt):
        """Test client initialization with credentials"""
        mock_module, mock_instance = mock_ccxt
        
        client = CCXTExchangeClient(
            exchange_id="bitget",
            api_key="test_key",
            api_secret="test_secret",
            password="test_pass",
            sandbox=True
        )
        
        assert client.exchange_id == "bitget"
        assert client.exchange == mock_instance
        
        # Verify exchange was initialized with correct config
        mock_module.bitget.assert_called_once()
        call_args = mock_module.bitget.call_args[0][0]
        assert call_args['apiKey'] == "test_key"
        assert call_args['secret'] == "test_secret"
        assert call_args['password'] == "test_pass"
        assert call_args['sandbox'] is True
    
    def test_get_account_info(self, mock_ccxt):
        """Test fetching account balance"""
        _, mock_instance = mock_ccxt
        
        # Setup mock response
        mock_instance.fetch_balance.return_value = {
            'USDT': {
                'total': 10000.0,
                'free': 8000.0,
                'used': 2000.0
            }
        }
        
        client = CCXTExchangeClient("bitget", "key", "secret", "pass")
        balance = client.get_account_info()
        
        assert isinstance(balance, Balance)
        assert balance.total == 10000.0
        assert balance.free == 8000.0
        assert balance.used == 2000.0
        mock_instance.fetch_balance.assert_called_once()
    
    def test_get_positions(self, mock_ccxt):
        """Test fetching active positions"""
        _, mock_instance = mock_ccxt
        
        # Setup mock response
        mock_instance.fetch_positions.return_value = [
            {
                'symbol': 'BTC/USDT:USDT',
                'side': 'long',
                'contracts': 0.5,
                'entryPrice': 90000.0,
                'markPrice': 91000.0,
                'unrealizedPnl': 500.0,
                'leverage': 20.0,
                'marginMode': 'isolated'
            },
            {
                'symbol': 'ETH/USDT:USDT',
                'side': 'short',
                'contracts': 0,  # This should be filtered out
                'entryPrice': 3000.0,
                'markPrice': 2950.0,
                'unrealizedPnl': 0.0,
                'leverage': 10.0,
                'marginMode': 'cross'
            }
        ]
        
        client = CCXTExchangeClient("bitget", "key", "secret", "pass")
        positions = client.get_positions()
        
        assert len(positions) == 1  # Only active position
        assert positions[0].symbol == 'BTC/USDT:USDT'
        assert positions[0].side == 'long'
        assert positions[0].size == 0.5
        mock_instance.fetch_positions.assert_called_once()
    
    def test_place_order_market(self, mock_ccxt):
        """Test placing market order"""
        _, mock_instance = mock_ccxt
        
        # Setup mock response
        mock_instance.create_order.return_value = {
            'id': 'order123',
            'symbol': 'BTC/USDT:USDT',
            'side': 'buy',
            'amount': 0.1,
            'price': None,
            'average': 90000.0,
            'status': 'filled',
            'filled': 0.1,
            'remaining': 0.0
        }
        
        client = CCXTExchangeClient("bitget", "key", "secret", "pass")
        order = client.place_order(
            symbol="BTC/USDT:USDT",
            side="buy",
            order_type="market",
            amount=0.1,
            leverage=20
        )
        
        assert isinstance(order, OrderResult)
        assert order.id == 'order123'
        assert order.price == 90000.0
        assert order.filled == 0.1
        mock_instance.create_order.assert_called_once()
    
    def test_place_order_with_sltp(self, mock_ccxt):
        """Test placing order with stop loss and take profit"""
        _, mock_instance = mock_ccxt
        
        mock_instance.create_order.return_value = {
            'id': 'order456',
            'symbol': 'BTC/USDT:USDT',
            'side': 'buy',
            'amount': 0.1,
            'price': 89000.0,
            'status': 'open',
            'filled': 0.0,
            'remaining': 0.1
        }
        
        client = CCXTExchangeClient("bitget", "key", "secret", "pass")
        order = client.place_order(
            symbol="BTC/USDT:USDT",
            side="buy",
            order_type="limit",
            amount=0.1,
            price=89000.0,
            stop_loss_price=85000.0,
            take_profit_price=95000.0,
            leverage=20
        )
        
        assert order.id == 'order456'
        
        # Verify SL/TP params were passed
        call_args = mock_instance.create_order.call_args
        params = call_args[1]['params']
        assert 'stopLoss' in params
        assert params['stopLoss']['triggerPrice'] == 85000.0
        assert 'takeProfit' in params
        assert params['takeProfit']['triggerPrice'] == 95000.0
    
    def test_cancel_order(self, mock_ccxt):
        """Test order cancellation"""
        _, mock_instance = mock_ccxt
        
        client = CCXTExchangeClient("bitget", "key", "secret", "pass")
        client.cancel_order("order123", "BTC/USDT:USDT")
        
        mock_instance.cancel_order.assert_called_once_with(
            "order123",
            "BTC/USDT:USDT"
        )
    
    def test_set_leverage(self, mock_ccxt):
        """Test setting leverage"""
        _, mock_instance = mock_ccxt
        
        client = CCXTExchangeClient("bitget", "key", "secret", "pass")
        client.set_leverage("BTC/USDT:USDT", 20)
        
        mock_instance.set_leverage.assert_called_once_with(20, "BTC/USDT:USDT")
    
    def test_fetch_ticker(self, mock_ccxt):
        """Test fetching ticker data"""
        _, mock_instance = mock_ccxt
        
        mock_instance.fetch_ticker.return_value = {
            'last': 90000.0,
            'info': {
                'markPrice': '90500.0'
            }
        }
        
        client = CCXTExchangeClient("bitget", "key", "secret", "pass")
        ticker = client.fetch_ticker("BTC/USDT:USDT")
        
        assert ticker['last'] == 90000.0
        assert ticker['mark'] == 90500.0
    
    def test_get_open_orders(self, mock_ccxt):
        """Test fetching open orders"""
        _, mock_instance = mock_ccxt
        
        mock_instance.fetch_open_orders.return_value = [
            {
                'id': 'order1',
                'symbol': 'BTC/USDT:USDT',
                'side': 'buy',
                'amount': 0.1,
                'price': 89000.0,
                'status': 'open',
                'filled': 0.0,
                'remaining': 0.1
            }
        ]
        
        client = CCXTExchangeClient("bitget", "key", "secret", "pass")
        orders = client.get_open_orders("BTC/USDT:USDT")
        
        assert len(orders) == 1
        assert orders[0].id == 'order1'
        assert orders[0].status == 'open'


# ============================================================================
# Factory Function Tests
# ============================================================================

class TestGetClient:
    """Test get_client factory function"""
    
    @pytest.fixture(autouse=True)
    def clear_clients(self):
        """Clear singleton cache before each test"""
        _clients.clear()
        yield
        _clients.clear()
    
    @patch.dict(os.environ, {
        'BITGET_API_KEY': 'test_key',
        'BITGET_API_SECRET': 'test_secret',
        'BITGET_PASSPHRASE': 'test_pass',
        'BITGET_SANDBOX': 'true'
    })
    @patch('src.trading.exchange_client.ccxt')
    def test_get_client_bitget(self, mock_ccxt):
        """Test getting Bitget client from factory"""
        mock_exchange_class = MagicMock()
        mock_ccxt.bitget = mock_exchange_class
        mock_ccxt.bitget.return_value = MagicMock()
        
        client = get_client("bitget")
        
        assert isinstance(client, CCXTExchangeClient)
        assert client.exchange_id == "bitget"
        mock_ccxt.bitget.assert_called_once()
    
    @patch.dict(os.environ, {
        'BITGET_API_KEY': 'test_key',
        'BITGET_API_SECRET': 'test_secret',
        'BITGET_PASSPHRASE': 'test_pass'
    })
    @patch('src.trading.exchange_client.ccxt')
    def test_get_client_singleton(self, mock_ccxt):
        """Test singleton pattern - same instance returned"""
        mock_exchange_class = MagicMock()
        mock_ccxt.bitget = mock_exchange_class
        mock_ccxt.bitget.return_value = MagicMock()
        
        client1 = get_client("bitget")
        client2 = get_client("bitget")
        
        assert client1 is client2
        # Should only initialize once
        assert mock_ccxt.bitget.call_count == 1
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_client_missing_credentials(self):
        """Test error when credentials missing"""
        with pytest.raises(ValueError, match="Bitget API credentials not configured"):
            get_client("bitget")
    
    def test_get_client_unknown_exchange(self):
        """Test error for unknown exchange"""
        with pytest.raises(ValueError, match="Unknown exchange"):
            get_client("unknown_exchange")


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling in exchange client"""
    
    @patch('src.trading.exchange_client.ccxt')
    def test_get_account_info_error(self, mock_ccxt):
        """Test error handling in get_account_info"""
        mock_exchange_class = MagicMock()
        mock_ccxt.bitget = mock_exchange_class
        mock_instance = MagicMock()
        mock_exchange_class.return_value = mock_instance
        
        # Simulate API error
        mock_instance.fetch_balance.side_effect = Exception("API Error")
        
        client = CCXTExchangeClient("bitget", "key", "secret", "pass")
        
        with pytest.raises(Exception, match="API Error"):
            client.get_account_info()
    
    @patch('src.trading.exchange_client.ccxt')
    def test_place_order_error(self, mock_ccxt):
        """Test error handling in place_order"""
        mock_exchange_class = MagicMock()
        mock_ccxt.bitget = mock_exchange_class
        mock_instance = MagicMock()
        mock_exchange_class.return_value = mock_instance
        
        # Simulate order placement error
        mock_instance.create_order.side_effect = Exception("Insufficient balance")
        
        client = CCXTExchangeClient("bitget", "key", "secret", "pass")
        
        with pytest.raises(Exception, match="Insufficient balance"):
            client.place_order(
                symbol="BTC/USDT:USDT",
                side="buy",
                order_type="market",
                amount=100.0  # Too large
            )


# ============================================================================
# Integration Test (Optional - requires real credentials)
# ============================================================================

@pytest.mark.skip(reason="Requires real API credentials")
class TestIntegration:
    """Integration tests with real exchange (sandbox)"""
    
    def test_real_connection(self):
        """Test real connection to Bitget sandbox"""
        # Only run if credentials are available
        if not os.getenv("BITGET_API_KEY"):
            pytest.skip("Real credentials not available")
        
        client = get_client("bitget")
        
        # Test basic operations
        balance = client.get_account_info()
        assert balance.total >= 0
        
        positions = client.get_positions()
        assert isinstance(positions, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
