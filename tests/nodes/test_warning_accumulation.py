import pytest
from src.supervisor_graph import init_node
from src.nodes.execution import execute_trade
from src.state import TradingState

from unittest.mock import MagicMock, patch

@patch("src.supervisor_graph.get_account_manager")
def test_init_node_clears_warnings(mock_get_am):
    # Setup state with existing warnings
    state: TradingState = {
        "symbol": "BTC/USDT",
        "warnings": ["Test Warning 1", "Test Warning 2"],
        "messages": [],
        "loop_count": 0
    }
    
    # Setup mock
    mock_am = MagicMock()
    mock_get_am.return_value = mock_am
    mock_am.get_account_info.return_value = MagicMock(
        total_balance=10000.0,
        positions=[],
        open_orders=[]
    )
    
    updated_state = init_node(state)
    assert "warnings" in updated_state
    assert updated_state["warnings"] == []

def test_execute_trade_does_not_duplicate_warnings_internal():
    # Setup state where decisions exist but execution_plans don't (triggers warning)
    state: TradingState = {
        "decisions": [{"operation": "Buy", "symbol": "BTC/USDT"}],
        "execution_results": [],
        "warnings": ["🚨 CRITICAL: 1 trade decision(s) made but NO execution plans created. This indicates a failure in the risk assessment or execution planning stage."]
    }
    
    # Run execute_trade
    result = execute_trade(state)
    
    # Verify warning is not duplicated in the output list
    warnings = result.get("warnings", [])
    critical_warnings = [w for w in warnings if "CRITICAL" in w]
    assert len(critical_warnings) == 1

@patch("src.supervisor_graph.get_account_manager")
def test_tick_cycle_prevents_accumulation(mock_get_am):
    # Simulating two ticks
    
    # Setup mock for init_node
    mock_am = MagicMock()
    mock_get_am.return_value = mock_am
    mock_am.get_account_info.return_value = MagicMock(
        total_balance=10000.0,
        positions=[],
        open_orders=[]
    )
    
    # Tick 1
    state: TradingState = {
        "symbol": "BTC/USDT",
        "decisions": [{"operation": "Buy", "symbol": "BTC/USDT"}],
        "execution_results": [],
        "warnings": []
    }
    
    # Run execute_trade to add warning
    result1 = execute_trade(state)
    assert len(result1["warnings"]) == 1
    
    # Tick 2 Start (init_node should clear)
    # Simulate state at start of Tick 2 (including persistence from Tick 1)
    state_at_end_of_tick1 = {**state, **result1}
    updates_after_init = init_node(state_at_end_of_tick1)
    assert updates_after_init["warnings"] == []
    
    # Apply updates to state for Tick 2
    next_tick_state = {**state_at_end_of_tick1, **updates_after_init}
    
    # Run execute_trade again
    result2 = execute_trade(next_tick_state)
    assert len(result2["warnings"]) == 1 # Should still be 1, not 2
    # The message should be there
    assert any("CRITICAL" in w for w in result2["warnings"])
