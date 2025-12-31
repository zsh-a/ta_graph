import pytest
import os
from unittest.mock import MagicMock, patch
from typing import Any, cast
from datetime import datetime
from src.supervisor_graph import build_trading_supervisor
from src.state import TradingState
from src.nodes.execution import execute_trade

class TestOrderTransition:
    @pytest.fixture
    def mock_env(self):
        with patch.dict(os.environ, {"TRADING_MODE": "simulation"}):
            yield

    @patch("src.supervisor_graph.get_analysis_subgraph")
    @patch("src.database.account_manager.get_account_manager")
    def test_scanner_to_managing_transition(self, mock_get_am, mock_get_analysis, mock_env):
        # This test verifies supervisor transition logic in post_scanner_node
        mock_am = MagicMock()
        mock_get_am.return_value = mock_am
        
        mock_subgraph = MagicMock()
        mock_get_analysis.return_value = mock_subgraph
        
        execution_res = {
            "execution_id": "sim_btc_123",
            "order_id": "sim_btc_123",
            "execution_status": "FILLED",
            "side": "buy",
            "entry_price": 90000.0,
            "executed_price": 90000.0,
            "amount": 0.1,
            "executed_amount": 0.1,
            "leverage": 20,
            "symbol": "BTC/USDT"
        }
        
        updates = {
            "execution_results": [execution_res],
            "decisions": [{"operation": "Buy", "symbol": "BTC/USDT"}]
        }
        
        mock_subgraph.return_value = updates
        mock_subgraph.invoke.return_value = updates

        supervisor_app = build_trading_supervisor()

        initial_state = TradingState(
            status="looking_for_trade",
            symbol="BTC/USDT",
            exchange="bitget",
            is_trading_enabled=True,
            current_bar_index=100
        )

        result = supervisor_app.invoke(initial_state)

        # Assert successful transition
        assert result["status"] == "managing_position"
        assert result["position"] is not None
        assert result["position"]["entry_price"] == 90000.0
        assert result["pending_order_id"] is None

    @patch("src.database.account_manager.get_account_manager")
    def test_execution_node_updates_mock_state_and_alias(self, mock_get_am, mock_env):
        # This test verifies execution node logic: order_id alias and mock state update
        mock_am = MagicMock()
        mock_am.use_mock = True
        mock_am.mock_balance = 10000.0
        mock_am.mock_available = 10000.0
        mock_get_am.return_value = mock_am
        
        state = TradingState(
            symbol="BTC/USDT",
            exchange="bitget",
            decisions=[{
                "operation": "Buy",
                "symbol": "BTC/USDT"
            }],
            execution_results=[{
                "status": "APPROVED",
                "symbol": "BTC/USDT",
                "trading_symbol": "BTC/USDT:USDT",
                "operation": "Buy",
                "side": "LONG",
                "amount": 0.1,
                "entry_price": 90000.0,
                "stop_loss": 89000.0,
                "take_profit": 92000.0,
                "leverage": 20
            }]
        )
        
        # We need to mock get_client inside execute_trade
        with patch("src.nodes.execution.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            
            # Mock place_order to return a success OrderResult
            from src.trading.exchange_client import OrderResult
            mock_client.place_order.return_value = OrderResult(
                id="sim_btc_123",
                symbol="BTC/USDT",
                side="buy",
                price=90000.0,
                amount=0.1,
                status="filled",
                filled=0.1,
                remaining=0.0
            )
            
            result = execute_trade(state)
            
            exec_results = result.get("execution_results", [])
            assert len(exec_results) > 0
            res = exec_results[0]
            
            # Verify alias exists
            assert "order_id" in res
            assert res["order_id"] == res["execution_id"]
            
            # Verify mock AM was called
            mock_am.add_mock_position.assert_called_once()
            # Verify available balance update was triggered
            mock_am.update_balance.assert_called_once()
            # The second argument to update_balance should be less than 10000
            args, kwargs = mock_am.update_balance.call_args
            assert args[1] < 10000.0

    @patch("src.supervisor_graph.get_account_manager")
    def test_init_node_syncs_open_orders(self, mock_get_am: MagicMock, mock_env: Any) -> None:
        # This test verifies that init_node syncs existing open orders
        from src.database.account_manager import AccountInfo
        from src.supervisor_graph import init_node
        from datetime import timezone
        
        mock_am = MagicMock()
        mock_get_am.return_value = mock_am
        
        # Simulate an existing open order on the exchange
        timestamp = 1703750400000  # Example timestamp in ms
        mock_order = {
            "id": "existing_order_123",
            "symbol": "BTC/USDT",
            "side": "buy",
            "price": 40000.0,
            "amount": 1.0,
            "status": "open",
            "filled": 0.0,
            "remaining": 1.0,
            "timestamp": timestamp
        }
        
        mock_ai = AccountInfo(
            total_balance=10000.0,
            available_balance=9000.0,
            used_margin=1000.0,
            unrealized_pnl=0.0,
            positions=[],
            open_orders=[mock_order]
        )
        mock_am.get_account_info.return_value = mock_ai
        
        state = TradingState(symbol="BTC/USDT")
        
        updates = init_node(state)
        updates_dict = cast(dict[str, Any], cast(object, updates))
        
        assert updates_dict.get("status") == "order_pending"
        assert updates_dict.get("pending_order_id") == "existing_order_123"
        assert "order_placed_time" in updates
        
        # Verify timestamp conversion (ms to ISO)
        expected_dt = datetime.fromtimestamp(timestamp / 1000.0, tz=timezone.utc)
        assert updates["order_placed_time"] == expected_dt.isoformat()

if __name__ == "__main__":
    pytest.main([__file__])
