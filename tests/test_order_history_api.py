
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import pytest
from unittest.mock import MagicMock, patch

# Need to set up path to import src
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.dashboard import app

client = TestClient(app)

def test_get_history_orders_structure():
    """Test the structure of the response from /history/orders"""
    # We mock the database call to avoid needing a real DB connection
    with patch("src.database.trading_history.get_order_history") as mock_get:
        mock_get.return_value = {
            "stats": {
                "total_trades": 10,
                "winning_trades": 6,
                "losing_trades": 4,
                "total_pnl": 100.0,
                "win_rate": 60.0
            },
            "orders": [],
            "total": 10,
            "page": 1,
            "limit": 50
        }
        
        response = client.get("/history/orders")
        assert response.status_code == 200
        data = response.json()
        
        assert "stats" in data
        assert "orders" in data
        assert data["stats"]["total_trades"] == 10
        assert data["stats"]["win_rate"] == 60.0

def test_get_history_orders_params():
    """Test that params are passed correctly"""
    with patch("src.database.trading_history.get_order_history") as mock_get:
        mock_get.return_value = {}
        
        client.get("/history/orders?start_date=2024-01-01T00:00:00Z&limit=20")
        
        # Verify arguments passed to get_order_history
        args, kwargs = mock_get.call_args
        assert kwargs["limit"] == 20
        assert kwargs["start_date"].year == 2024

if __name__ == "__main__":
    # Manually run if executed as script
    test_get_history_orders_structure()
    test_get_history_orders_params()
    print("All tests passed!")
