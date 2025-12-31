import pytest
from unittest.mock import MagicMock, patch
from src.nodes.execution import save_trade_to_database, TradeResult
from src.database.models import SymbolType, OperationType

@patch("src.nodes.execution.get_session")
@patch("src.nodes.execution.create_trading_record")
def test_save_trade_to_database_symbol_mapping(mock_create, mock_get_session):
    # Mock DB session
    mock_db = MagicMock()
    mock_get_session.return_value = mock_db
    
    # Mock create_trading_record return value
    mock_trade = MagicMock()
    mock_trade.id = "test-uuid"
    mock_create.return_value = mock_trade
    
    # Test case 1: ETH/USDT
    plan = {
        "symbol": "ETH/USDT",
        "operation": "Buy",
        "amount": 1,
        "entry_price": 3000,
        "risk_amount": 100.0
    }
    result = TradeResult(
        success=True,
        order_id="123",
        executed_price=3000.0,
        executed_amount=1.0,
        error=None
    )
    
    save_trade_to_database(plan, result)
    
    # Verify symbol was mapped to ETH
    args, kwargs = mock_create.call_args
    assert kwargs["symbol"] == SymbolType.ETH
    assert kwargs["operation"] == OperationType.Buy
    
    # Test case 2: BTC/USDT (using trading_symbol)
    plan = {
        "trading_symbol": "BTC/USDT",
        "operation": "Sell",
        "amount": 1,
        "entry_price": 60000
    }
    result = TradeResult(
        success=True,
        order_id="456",
        executed_price=60000.0,
        executed_amount=0.5,
        error=None
    )
    
    save_trade_to_database(plan, result)
    
    args, kwargs = mock_create.call_args
    assert kwargs["symbol"] == SymbolType.BTC
    assert kwargs["operation"] == OperationType.Sell

    # Test case 3: Unknown symbol (should default to BTC)
    plan = {
        "symbol": "UNKNOWN/USDT",
        "operation": "Buy"
    }
    save_trade_to_database(plan, result)
    
    args, kwargs = mock_create.call_args
    assert kwargs["symbol"] == SymbolType.BTC
