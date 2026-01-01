"""
Trade Filters
Anti-overtrading mechanisms following Al Brooks' "sit on hands" principle.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from ..logger import get_logger

import pandas as pd
import numpy as np
from ..logger import get_logger

logger = get_logger(__name__)

class TradeFilter:
    """
    Implements multiple filters to prevent overtrading.
    
    Filters:
    1. Cooldown period between trades
    2. Daily trade count limit
    3. Probability threshold
    4. TTR (Tight Trading Range) detection
    5. Signal bar quality threshold
    """
    
    def __init__(
        self,
        cooldown_minutes: int = 15,
        max_daily_trades: int = 5,
        min_probability: float = 60.0,
        min_signal_quality: int = 6,
        enable_all: bool = True
    ):
        """
        Initialize trade filter with configuration.
        
        Args:
            cooldown_minutes: Minimum minutes between trades
            max_daily_trades: Maximum number of trades per day
            min_probability: Minimum probability score (0-100)
            min_signal_quality: Minimum signal bar quality (0-10)
            enable_all: Master switch to enable/disable all filters
        """
        self.cooldown_minutes = cooldown_minutes
        self.max_daily_trades = max_daily_trades
        self.min_probability = min_probability
        self.min_signal_quality = min_signal_quality
        self.min_signal_quality = min_signal_quality
        self.enable_all = enable_all
        
        # New settings
        self.enable_bar_close_check = True
        self.enable_atr_check = True
        self.enable_barb_wire_check = True
        self.bar_close_buffer_seconds = 30  # Allow trading in last 30s of candle

        
        # State tracking
        self.last_trade_time: Optional[datetime] = None
        self.trades_today = 0
        self.daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Load state from persistence if available
        self._load_state()
    
    def _load_state(self):
        """Load filter state from file (for persistence across restarts)"""
        state_file = "filter_state.json"
        if os.path.exists(state_file):
            import json
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    
                    if 'last_trade_time' in state and state['last_trade_time']:
                        self.last_trade_time = datetime.fromisoformat(state['last_trade_time'])
                    
                    self.trades_today = state.get('trades_today', 0)
                    
                    if 'daily_reset_time' in state:
                        self.daily_reset_time = datetime.fromisoformat(state['daily_reset_time'])
                    
                    logger.info(f"Loaded trade filter state: {self.trades_today} trades today")
            except Exception as e:
                logger.warning(f"Failed to load filter state: {e}")
    
    def _save_state(self):
        """Save filter state to file"""
        state_file = "filter_state.json"
        import json
        
        state = {
            'last_trade_time': self.last_trade_time.isoformat() if self.last_trade_time else None,
            'trades_today': self.trades_today,
            'daily_reset_time': self.daily_reset_time.isoformat()
        }
        
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            logger.warning(f"Failed to save filter state: {e}")
    
    def _reset_daily_counter(self):
        """Reset daily trade counter if new day"""
        now = datetime.now()
        if now >= self.daily_reset_time + timedelta(days=1):
            logger.info(f"New trading day - resetting counter (previous: {self.trades_today} trades)")
            self.trades_today = 0
            self.daily_reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            self._save_state()
    
    def check_cooldown(self) -> tuple[bool, str]:
        """
        Check if enough time has passed since last trade.
        
        Returns:
            (passed: bool, reason: str)
        """
        if not self.enable_all:
            return True, ""
        
        if self.last_trade_time is None:
            return True, ""
        
        elapsed = datetime.now() - self.last_trade_time
        required = timedelta(minutes=self.cooldown_minutes)
        
        if elapsed < required:
            remaining = required - elapsed
            minutes_left = int(remaining.total_seconds() / 60)
            reason = f"Cooldown active: {minutes_left} minutes remaining (minimum {self.cooldown_minutes}m between trades)"
            return False, reason
        
        return True, ""
    
    def check_daily_limit(self) -> tuple[bool, str]:
        """
        Check if daily trade limit has been reached.
        
        Returns:
            (passed: bool, reason: str)
        """
        if not self.enable_all:
            return True, ""
        
        self._reset_daily_counter()
        
        if self.trades_today >= self.max_daily_trades:
            reason = f"Daily limit reached: {self.trades_today}/{self.max_daily_trades} trades today"
            return False, reason
        
        return True, ""
    
    def check_probability_threshold(self, decision: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check if decision probability meets minimum threshold.
        
        Args:
            decision: Decision dict with 'probability_score' field
            
        Returns:
            (passed: bool, reason: str)
        """
        if not self.enable_all:
            return True, ""
        
        prob = decision.get('probability_score', 0.0)
        
        if prob < self.min_probability:
            reason = f"Probability too low: {prob:.1f}% < {self.min_probability}% threshold"
            return False, reason
        
        return True, ""
    
    def check_signal_bar_quality(self, brooks_analysis: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check if signal bar quality meets minimum threshold.
        
        Args:
            brooks_analysis: Brooks analysis dict with 'signal_bar' field
            
        Returns:
            (passed: bool, reason: str)
        """
        if not self.enable_all:
            return True, ""
        
        if not brooks_analysis or 'signal_bar' not in brooks_analysis:
            reason = "No Brooks analysis available - cannot verify signal bar quality"
            return False, reason
        
        quality = brooks_analysis['signal_bar'].get('quality_score', 0)
        
        if quality < self.min_signal_quality:
            reason = f"Signal bar quality too low: {quality}/10 < {self.min_signal_quality}/10 threshold"
            return False, reason
        
        return True, ""
    
    def check_ttr_condition(self, brooks_analysis: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check for Tight Trading Range (TTR) with poor setup.
        Al Brooks: "In a TTR, probability is 50/50. Only trade with excellent signal bars."
        
        Args:
            brooks_analysis: Brooks analysis dict
            
        Returns:
            (passed: bool, reason: str)
        """
        if not self.enable_all:
            return True, ""
        
        if not brooks_analysis:
            return True, ""
        
        market_cycle = brooks_analysis.get('market_cycle', '')
        
        # If in trading range, require higher quality
        if 'trading_range' in market_cycle or market_cycle == 'ttr':
            signal_quality = brooks_analysis.get('signal_bar', {}).get('quality_score', 0)
            setup_quality = brooks_analysis.get('setup_quality', 0)
            
            # In TTR, require signal bar >= 8/10
            if signal_quality < 8:
                reason = f"Trading Range detected - signal bar quality {signal_quality}/10 is insufficient (need 8+ in ranging market)"
                return False, reason
            
            # Also check overall setup quality
            if setup_quality < 7:
                reason = f"Trading Range with mediocre setup quality {setup_quality}/10 (need 7+ in ranging market)"
                return False, reason
        
        return True, ""
    
    def check_validation_errors(self, brooks_analysis: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check if Brooks analysis has validation errors (potential VL hallucination).
        
        Args:
            brooks_analysis: Brooks analysis dict with '_validation' field
            
        Returns:
            (passed: bool, reason: str)
        """
        if not self.enable_all:
            return True, ""
        
        if not brooks_analysis or '_validation' not in brooks_analysis:
            return True, ""
        
        validation = brooks_analysis['_validation']
        
        if not validation.get('valid', True):
            errors = validation.get('errors', [])
            reason = f"VL model validation failed: {'; '.join(errors[:2])}"  # Show first 2 errors
            return False, reason
        
        # Check warnings count
        warnings = validation.get('warnings', [])
        if len(warnings) >= 3:
            reason = f"Too many validation warnings ({len(warnings)}): Possible VL hallucination"
            logger.warning(reason)
            return False, reason
        
        return True, ""
    
    def check_bar_close(self, current_time: datetime = None) -> tuple[bool, str]:
        """
        Rule: Only trade near the close of the bar (e.g., last 30 seconds).
        Brooks: "Decisions should be made as the bar closes."
        
        Exception: Strong breakout markets (handled by caller overriding this).
        """
        if not self.enable_all or not self.enable_bar_close_check:
            return True, ""
            
        if current_time is None:
            current_time = datetime.now()
            
        # Assuming 5-minute bars for the primary execution timeframe
        # TODO: Make timeframe dynamic if needed, defaulting to 5m logic
        interval_seconds = 300 # 5 minutes
        
        # Calculate seconds into the current interval
        timestamp = current_time.timestamp()
        seconds_elapsed = timestamp % interval_seconds
        seconds_remaining = interval_seconds - seconds_elapsed
        
        # Allow trading if we are in the last X seconds OR first X seconds (latency buffer)
        buffer = self.bar_close_buffer_seconds
        
        if seconds_remaining <= buffer or seconds_elapsed <= 10:
            return True, ""
            
        return False, f"Not near bar close ({int(seconds_remaining)}s remaining). Wait for signal bar to close."

    def check_atr_stop(self, decision: Dict[str, Any], market_data: pd.DataFrame | List[Dict]) -> tuple[bool, str]:
        """
        Rule: Stop loss must be reasonable relative to volatility (ATR).
        If SL is too tight (< 0.5 * ATR), it's likely noise.
        """
        if not self.enable_all or not self.enable_atr_check:
            return True, ""
            
        # Extract Stop Loss distance
        sl_price = None
        entry_price = None
        
        # Parse decision to find prices
        # Parse decision to find prices
        entry = decision.get('entry_price')
        sl = decision.get('stop_loss')
        
        if entry is None or sl is None:
             # Try deeper structure if needed, or return True
             return True, ""
             
        # Calculate ATR
        if isinstance(market_data, pd.DataFrame):
             atr = self.calculate_atr(market_data)
        elif isinstance(market_data, list):
             df = pd.DataFrame(market_data)
             atr = self.calculate_atr(df)
        else:
             return True, ""
             
        if atr == 0:
            return True, ""
            
        sl_distance = abs(entry - sl)
        
        # Rule: Min Stop should be 0.5 * ATR (approx)
        min_stop = 0.5 * atr
        
        if sl_distance < min_stop:
             return False, f"Stop Loss too tight ({sl_distance:.2f}), minimum is 0.5*ATR ({min_stop:.2f}). Noise will hit it."
             
        return True, ""

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Helper to calculate ATR"""
        if len(df) < period + 1:
            return 0.0
            
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        return atr

    def check_barb_wire(self, market_data: pd.DataFrame | List[Dict] | Any) -> tuple[bool, str]:
        """
        Rule: Detect "Barb Wire" (Tight Trading Range).
        If recent bars have high overlap, DO NOT TRADE.
        
        Logic: Check last 5 bars. If > 3 bars overlap significantly with the previous bar's range.
        """
        if not self.enable_all or not self.enable_barb_wire_check:
            return True, ""
            
        # Convert to DataFrame if needed
        if not isinstance(market_data, pd.DataFrame):
            if isinstance(market_data, list):
                market_data = pd.DataFrame(market_data)
            elif hasattr(market_data, 'model_dump'): # Pydantic/Data Object
                 # This might happen if passed raw object
                 return True, "" 
            else:
                 # Unknown format or empty
                 return True, ""
                 
        if len(market_data) < 7:
            return True, ""
            
        # Get last 7 completed bars (excluding current forming bar if possible)
        # Assuming last row is current forming bar, take previous 7
        recent = market_data.iloc[-8:-1].copy() if len(market_data) > 8 else market_data.iloc[:-1].copy()
        
        if len(recent) < 5:
            return True, ""
            
        overlap_count = 0
        total_checks = 0
        
        for i in range(1, len(recent)):
            curr = recent.iloc[i]
            prev = recent.iloc[i-1]
            
            # Entity (Body) overlap check
            # User rule: "80% of K line entities are in the range of the previous one"
            curr_body_top = max(curr['open'], curr['close'])
            curr_body_bottom = min(curr['open'], curr['close'])
            prev_high = prev['high']
            prev_low = prev['low']
            
            # Check if body is mostly inside previous range
            # Actually, Brooks "Barb Wire" is often defined by:
            # - Bars overlapping
            # - Dojis
            # - No clear trend
            
            # Strict implementation of user rule:
            # Check if the BODY of current bar is engulfed by RANGE of previous bar
            if curr_body_top <= prev_high and curr_body_bottom >= prev_low:
                overlap_count += 1
            
            
            total_checks += 1
            
        # Exception: If the market is trending (making progress), ignore overlap
        # Check Net Movement vs Total Movement
        period_high = recent['high'].max()
        period_low = recent['low'].min()
        net_move = period_high - period_low
        
        avg_range = (recent['high'] - recent['low']).mean()
        # If net move is > 4x average bar range, it's trending enough
        if avg_range > 0 and (net_move / avg_range) > 4.0:
             # logger.info(f"High overlap ({overlap_count}/{total_checks}) but Strong Trend detected (Move {net_move:.2f} / AvgRange {avg_range:.2f}). Safe.")
             return True, ""
            
        # Threshold: If > 60% of recent bars are "inside" bars (overlap previous range), it's choppy
        if total_checks > 0 and (overlap_count / total_checks) >= 0.6:
            return False, f"Barb Wire detected: {overlap_count}/{total_checks} recent bars overlapping. MARKET IS CHOPPY."
            
        return True, ""

    def check_trading_range_logic(self, decision: Dict[str, Any], brooks_analysis: Dict[str, Any], market_data: pd.DataFrame | Any) -> tuple[bool, str]:
        """
        Rule: In Trading Range:
        - Buy Low (Lower 1/3)
        - Sell High (Upper 1/3)
        - Avoid Middle
        """
        if not self.enable_all:
             return True, ""
             
        if not brooks_analysis:
            return True, ""
            
        market_cycle = str(brooks_analysis.get('market_cycle', '')).lower()
        if 'trading_range' not in market_cycle and 'trading range' not in market_cycle:
            return True, ""
            
        # We are in a trading range. Check location.
        # Need current price vs Range High/Low. 
        # Brooks analysis might provide context, or we calculate from market data.
        
        # Try to use prediction key levels if available
        # prediction = decision.get('prediction', {})
        # key_levels = prediction.get('key_levels', {})
        # But prediction is populated BY the decision we are checking, so it might match.
        
        # Better: Calculate recent range from market data (last 20-30 bars)
        if hasattr(market_data, 'iloc'):
            recent = market_data.iloc[-30:] # Last 30 bars
            range_high = recent['high'].max()
            range_low = recent['low'].min()
            current_price = recent['close'].iloc[-1]
            
            range_size = range_high - range_low
            if range_size == 0: return True, ""
            
            position_in_range = (current_price - range_low) / range_size # 0.0 = Low, 1.0 = High
            
            op = decision.get('operation')
            
            if op == 'Buy':
                if position_in_range > 0.66:
                    return False, f"Trading Range Disciple: Buying at top of range ({position_in_range:.2f}). Wait for pullback."
            elif op == 'Sell':
                if position_in_range < 0.33:
                    return False, f"Trading Range Discipline: Selling at bottom of range ({position_in_range:.2f}). Wait for bounce."
                    
        return True, ""

    def apply_all_filters(
        self,
        decision: Dict[str, Any],
        brooks_analysis: Optional[Dict[str, Any]] = None,
        market_data: Optional[Any] = None
    ) -> tuple[bool, List[str]]:

        """
        Apply all filters to a trading decision.
        
        Args:
            decision: Trading decision dict
            brooks_analysis: Optional Brooks analysis dict
            
        Returns:
            (passed: bool, reasons: List[str]) - reasons列表包含所有未通过的过滤器原因
        """
        if not self.enable_all:
            return True, []
        
        failed_reasons = []
        
        # Filter 1: Cooldown
        passed, reason = self.check_cooldown()
        if not passed:
            failed_reasons.append(f"[Cooldown] {reason}")
        
        # Filter 2: Daily limit
        passed, reason = self.check_daily_limit()
        if not passed:
            failed_reasons.append(f"[Daily Limit] {reason}")
        
        # Filter 3: Probability
        passed, reason = self.check_probability_threshold(decision)
        if not passed:
            failed_reasons.append(f"[Probability] {reason}")
        
        # Brooks-specific filters (only if brooks_analysis available)
        if brooks_analysis:
            # Filter 4: Signal bar quality
            passed, reason = self.check_signal_bar_quality(brooks_analysis)
            if not passed:
                failed_reasons.append(f"[Signal Quality] {reason}")
            
            # Filter 5: TTR condition
            passed, reason = self.check_ttr_condition(brooks_analysis)
            if not passed:
                failed_reasons.append(f"[TTR] {reason}")
            
            # Filter 6: Validation errors
            passed, reason = self.check_validation_errors(brooks_analysis)
            if not passed:
                failed_reasons.append(f"[Validation] {reason}")
                
            # Filter 7: Trading Range Logic
            passed, reason = self.check_trading_range_logic(decision, brooks_analysis, market_data)
            if not passed:
                failed_reasons.append(f"[TR Logic] {reason}")

        # Quantitative Checks (requiring Market Data)
        if market_data is not None:
             # Filter 8: Bar Close Check
             # Exception: Strong Trends might allow mid-bar entries (checked via brooks_analysis)
             is_strong_trend = False
             if brooks_analysis and 'strong' in brooks_analysis.get('market_cycle', ''):
                 is_strong_trend = True
                 
            #  if not is_strong_trend:
            #      passed, reason = self.check_bar_close()
            #      if not passed:
            #          failed_reasons.append(f"[Timing] {reason}")
            
             # Filter 9: Barb Wire
             passed, reason = self.check_barb_wire(market_data)
             if not passed:
                 failed_reasons.append(f"[Barb Wire] {reason}")
                 
             # Filter 10: ATR Stop
             passed, reason = self.check_atr_stop(decision, market_data)
             if not passed:
                 failed_reasons.append(f"[ATR Stop] {reason}")

        
        passed_all = len(failed_reasons) == 0
        
        if not passed_all:
            logger.info(f"Trade filtered by {len(failed_reasons)} rule(s): {'; '.join(failed_reasons)}")
        
        return passed_all, failed_reasons
    
    def record_trade_execution(self):
        """
        Record that a trade was executed.
        Updates counters and saves state.
        """
        self.last_trade_time = datetime.now()
        self.trades_today += 1
        self._save_state()
        
        logger.info(f"Trade executed - Total today: {self.trades_today}/{self.max_daily_trades}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current filter status for monitoring"""
        self._reset_daily_counter()
        
        cooldown_remaining = 0
        if self.last_trade_time:
            elapsed = datetime.now() - self.last_trade_time
            required = timedelta(minutes=self.cooldown_minutes)
            if elapsed < required:
                cooldown_remaining = int((required - elapsed).total_seconds() / 60)
        
        return {
            "enabled": self.enable_all,
            "trades_today": self.trades_today,
            "max_daily_trades": self.max_daily_trades,
            "cooldown_remaining_minutes": cooldown_remaining,
            "last_trade_time": self.last_trade_time.isoformat() if self.last_trade_time else None,
            "min_probability": self.min_probability,
            "min_signal_quality": self.min_signal_quality
        }
    
    def reset(self):
        """Reset all counters (for testing or manual reset)"""
        self.last_trade_time = None
        self.trades_today = 0
        self.daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self._save_state()
        logger.info("Trade filter reset")


# Global singleton instance
_trade_filter: Optional[TradeFilter] = None

def get_trade_filter() -> TradeFilter:
    """Get global trade filter instance"""
    global _trade_filter
    
    if _trade_filter is None:
        # Load configuration from environment
        cooldown = int(os.getenv("TRADE_COOLDOWN_MINUTES", "15"))
        max_daily = int(os.getenv("MAX_DAILY_TRADES", "5"))
        min_prob = float(os.getenv("MIN_PROBABILITY", "60.0"))
        min_quality = int(os.getenv("MIN_SIGNAL_QUALITY", "6"))
        
        _trade_filter = TradeFilter(
            cooldown_minutes=cooldown,
            max_daily_trades=max_daily,
            min_probability=min_prob,
            min_signal_quality=min_quality
        )
    
    return _trade_filter
