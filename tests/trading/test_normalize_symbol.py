"""
Test normalize_symbol helper function
"""

import pytest
from src.trading.exchange_client import normalize_symbol


class TestNormalizeSymbol:
    """Test symbol normalization for different exchanges"""
    
    def test_bitget_adds_usdt_suffix(self):
        """Test Bitget adds :USDT suffix when missing"""
        result = normalize_symbol("BTC/USDT", "bitget")
        assert result == "BTC/USDT:USDT"
    
    def test_bitget_keeps_existing_suffix(self):
        """Test Bitget keeps :USDT suffix if already present"""
        result = normalize_symbol("BTC/USDT:USDT", "bitget")
        assert result == "BTC/USDT:USDT"
    
    def test_bitget_ethereum(self):
        """Test Bitget normalization for ETH"""
        result = normalize_symbol("ETH/USDT", "bitget")
        assert result == "ETH/USDT:USDT"
    
    def test_bitget_solana(self):
        """Test Bitget normalization for SOL"""
        result = normalize_symbol("SOL/USDT", "bitget")
        assert result == "SOL/USDT:USDT"
    
    def test_other_exchange_unchanged(self):
        """Test other exchanges don't modify symbol"""
        result = normalize_symbol("BTC/USDT", "binance")
        assert result == "BTC/USDT"
    
    def test_non_usdt_pair_unchanged(self):
        """Test non-USDT pairs remain unchanged"""
        result = normalize_symbol("BTC/USD", "bitget")
        assert result == "BTC/USD"
    
    def test_default_exchange_is_bitget(self):
        """Test default exchange is bitget"""
        result = normalize_symbol("BTC/USDT")
        assert result == "BTC/USDT:USDT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
