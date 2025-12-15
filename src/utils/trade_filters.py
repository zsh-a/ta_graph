"""
Trade Filters
Anti-overtrading mechanisms following Al Brooks' "sit on hands" principle.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
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
        self.enable_all = enable_all
        
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
    
    def apply_all_filters(
        self,
        decision: Dict[str, Any],
        brooks_analysis: Optional[Dict[str, Any]] = None
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
