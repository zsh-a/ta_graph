import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.utils.trade_filters import get_trade_filter, TradeFilter

class TestBrooksFilters(unittest.TestCase):
    def setUp(self):
        self.tf = get_trade_filter()
        # Reset any state
        self.tf.trades_today = 0
        self.tf.last_reset_date = datetime.now().date()
        
        # Mock Market Data (Strong Trend / Breakout)
        dates = pd.date_range(end=datetime.now(), periods=20, freq='5min')
        # Slope of 5 per bar
        data = {
            'timestamp': dates,
            'open': [100 + i*5 for i in range(20)],
            'high': [100 + i*5 + 2 for i in range(20)], # Range 2
            'low': [100 + i*5 - 1 for i in range(20)],  # Range 3
            'close': [100 + i*5 + 4 for i in range(20)],
            'volume': [1000] * 20
        }
        self.trend_df = pd.DataFrame(data)

    def test_check_barb_wire_clean(self):
        """Test that barb wire is NOT detected in a clean trend."""
        is_safe, msg = self.tf.check_barb_wire(self.trend_df)
        self.assertTrue(is_safe, f"Trend should be safe but got: {msg}")

    def test_check_barb_wire_detected(self):
        """Test that barb wire IS detected in overlapping chop."""
        dates = pd.date_range(end=datetime.now(), periods=20, freq='5min')
        # Create overlapping bars (Doijis in a row)
        data = {
            'timestamp': dates,
            'open': [100] * 20,
            'high': [101] * 20,
            'low': [99] * 20,
            'close': [100] * 20,
            'volume': [1000] * 20
        }
        chop_df = pd.DataFrame(data)
        
        is_safe, msg = self.tf.check_barb_wire(chop_df)
        self.assertFalse(is_safe, "Choppy overlapping bars should be flagged as Barb Wire")
        self.assertIn("Barb Wire detected", msg)

    def test_trading_range_logic_buy_high(self):
        """Test forbidding BUY at the top of a Trading Range."""
        # Setup: Current price 110, Range 100-110
        decision = {"operation": "Buy"}
        brooks_analysis = {"market_cycle": "Trading Range"}
        
        # Last close is 110 (Top of range 100-110)
        # We need data that establishes this range
        dates = pd.date_range(end=datetime.now(), periods=20, freq='5min')
        # Alternating 100 and 110
        closes = [100, 110] * 10
        data = {
            'timestamp': dates,
            'open': closes, # Simplified
            'high': [c + 1 for c in closes],
            'low': [c - 1 for c in closes],
            'close': closes,
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        # Test Buy at top
        is_safe, msg = self.tf.check_trading_range_logic(decision, brooks_analysis, df)
        self.assertFalse(is_safe, "Buying at top of TR should fail")
        self.assertIn("Buying at top of range", msg)

    def test_trading_range_logic_buy_low(self):
        """Test allowing BUY at the bottom of a Trading Range."""
        # Setup: Current price 100, Range 100-110
        decision = {"operation": "Buy"}
        brooks_analysis = {"market_cycle": "Trading Range"}
        
        dates = pd.date_range(end=datetime.now(), periods=20, freq='5min')
        closes = [100, 110] * 10
        # Make the last one 100 (Bottom)
        closes[-1] = 100
        
        data = {
            'timestamp': dates,
            'open': closes,
            'high': [c + 1 for c in closes],
            'low': [c - 1 for c in closes],
            'close': closes,
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        is_safe, msg = self.tf.check_trading_range_logic(decision, brooks_analysis, df)
        self.assertTrue(is_safe, f"Buying at bottom should pass. Msg: {msg}")

    def test_bar_close_timing(self):
        """Test bar close proximity check."""
        # 5 minute candles. 
        # Case 1: 30 seconds remaning -> Pass
        t1 = datetime(2024, 1, 1, 12, 4, 30) # 0, 5, 10
        # 12:05:00 is next close. 12:04:30 is 30s remaining.
        
        # Note: check_bar_close uses current system time usually, but we can patch execute?
        # The method asks for `current_time`.
        
        is_safe, msg = self.tf.check_bar_close(current_time=t1)
        self.assertTrue(is_safe, "Should pass when 30s remaining")
        
        # Case 2: 2 minutes elapsed (mid bar) -> Fail
        t2 = datetime(2024, 1, 1, 12, 2, 0)
        is_safe, msg = self.tf.check_bar_close(current_time=t2)
        self.assertFalse(is_safe, "Should fail when in middle of bar")

    def test_atr_stop_validation(self):
        """Test ATR stop loss distance check."""
        
        # Create data with ATR=2.0 roughly
        # High-Low = 2.0
        dates = pd.date_range(end=datetime.now(), periods=20, freq='5min')
        data = {
            'timestamp': dates,
            'open': [100] * 20,
            'high': [102] * 20,
            'low': [100] * 20,
            'close': [101] * 20,
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        # ATR should be approx 2.0 (High 102 - Low 100)
        
        # Scenario 1: Tight Stop (0.1 dist, < 0.5 ATR)
        decision_tight = {
            "entry_price": 100.0,
            "stop_loss": 99.9 # Dist 0.1
        }
        is_safe, msg = self.tf.check_atr_stop(decision_tight, df)
        # Should ideally fail or warn. The implementation might return true with warning?
        # Let's check implementation behavior. We implemented it to failing if < 0.5 * ATR.
        
        # 0.5 * ATR(2.0) = 1.0. 
        # Dist 0.1 is < 1.0.
        
        self.assertFalse(is_safe, f"Stop is too tight (0.1 vs ATR 2.0). Msg: {msg}")
        self.assertIn("Stop Loss too tight", msg)
        
        # Scenario 2: Wide Stop (3.0 dist)
        decision_good = {
            "entry_price": 100.0,
            "stop_loss": 97.0 # Dist 3.0
        }
        is_safe, msg = self.tf.check_atr_stop(decision_good, df)
        self.assertTrue(is_safe, f"Stop should be fine. Msg: {msg}")

if __name__ == '__main__':
    unittest.main()
