"""
Second Entry Logic - H2/L2 Re-entry State Machine

Implements Brooks' second entry principle:
- H2: Second higher high buy after H1 failed
- L2: Second lower low sell after L1 failed

Brooks principle: "The second entry is often the better trade because
the weak hands have been stopped out."
"""

from enum import Enum
from typing import Any
from dataclasses import dataclass, field

from ..state import TradingState
from ..logger import get_logger

logger = get_logger(__name__)


class SetupState(str, Enum):
    """State machine states for entry logic"""
    WAITING = "waiting"           # No active setup
    H1_TRIGGERED = "h1_triggered"  # H1 buy triggered, watching for failure/success
    L1_TRIGGERED = "l1_triggered"  # L1 sell triggered, watching for failure/success
    H1_FAILED = "h1_failed"        # H1 failed, waiting for H2
    L1_FAILED = "l1_failed"        # L1 failed, waiting for L2
    H2_READY = "h2_ready"          # H2 setup ready to trade
    L2_READY = "l2_ready"          # L2 setup ready to trade


@dataclass
class SecondEntryState:
    """Tracks the state of the second entry logic"""
    current_state: SetupState = SetupState.WAITING
    first_entry_bar_index: int | None = None
    first_entry_price: float | None = None
    first_entry_stop: float | None = None
    failure_bar_index: int | None = None
    second_signal_bar_index: int | None = None
    setup_type: str | None = None  # "H2_buy" or "L2_sell"
    attempts: int = 0
    max_attempts: int = 2  # Max number of re-entry attempts
    notes: list[str] = field(default_factory=list)
    
    def reset(self) -> None:
        """Reset to initial state"""
        self.current_state = SetupState.WAITING
        self.first_entry_bar_index = None
        self.first_entry_price = None
        self.first_entry_stop = None
        self.failure_bar_index = None
        self.second_signal_bar_index = None
        self.setup_type = None
        self.attempts = 0
        self.notes = []
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for state storage"""
        return {
            "current_state": self.current_state.value,
            "first_entry_bar_index": self.first_entry_bar_index,
            "first_entry_price": self.first_entry_price,
            "first_entry_stop": self.first_entry_stop,
            "failure_bar_index": self.failure_bar_index,
            "second_signal_bar_index": self.second_signal_bar_index,
            "setup_type": self.setup_type,
            "attempts": self.attempts,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SecondEntryState":
        """Create from dictionary"""
        if not data:
            return cls()
        state = cls()
        state.current_state = SetupState(data.get("current_state", "waiting"))
        state.first_entry_bar_index = data.get("first_entry_bar_index")
        state.first_entry_price = data.get("first_entry_price")
        state.first_entry_stop = data.get("first_entry_stop")
        state.failure_bar_index = data.get("failure_bar_index")
        state.second_signal_bar_index = data.get("second_signal_bar_index")
        state.setup_type = data.get("setup_type")
        state.attempts = data.get("attempts", 0)
        state.notes = data.get("notes", [])
        return state


def detect_first_entry_failure(
    state: TradingState,
    entry_state: SecondEntryState
) -> bool:
    """
    Detect if a first entry (H1 or L1) has failed.
    
    Failure conditions:
    - H1: Price closes below the entry bar's low
    - L1: Price closes above the entry bar's high
    """
    if entry_state.current_state not in (SetupState.H1_TRIGGERED, SetupState.L1_TRIGGERED):
        return False
    
    bars = state.get("bars", [])
    current_bar_index = state.get("current_bar_index", 0)
    
    if not bars or entry_state.first_entry_bar_index is None:
        return False
    
    # Get the entry bar
    entry_idx = entry_state.first_entry_bar_index
    if entry_idx < 0 or entry_idx >= len(bars):
        return False
    
    entry_bar = bars[entry_idx]
    current_bar = bars[-1] if bars else None
    
    if not current_bar:
        return False
    
    # Check failure conditions
    if entry_state.current_state == SetupState.H1_TRIGGERED:
        # H1 fails if price closes below entry bar's low
        if current_bar.get("close", 0) < entry_bar.get("low", float('inf')):
            entry_state.current_state = SetupState.H1_FAILED
            entry_state.failure_bar_index = current_bar_index
            entry_state.notes.append(f"H1 failed at bar {current_bar_index}")
            logger.info(f"📉 H1 entry failed - watching for H2 setup")
            return True
    
    elif entry_state.current_state == SetupState.L1_TRIGGERED:
        # L1 fails if price closes above entry bar's high
        if current_bar.get("close", 0) > entry_bar.get("high", 0):
            entry_state.current_state = SetupState.L1_FAILED
            entry_state.failure_bar_index = current_bar_index
            entry_state.notes.append(f"L1 failed at bar {current_bar_index}")
            logger.info(f"📈 L1 entry failed - watching for L2 setup")
            return True
    
    return False


def detect_second_entry_signal(
    state: TradingState,
    entry_state: SecondEntryState
) -> bool:
    """
    Detect if a second entry (H2 or L2) signal appears.
    
    Signal conditions:
    - H2: After H1 failure, price makes a new higher high
    - L2: After L1 failure, price makes a new lower low
    """
    if entry_state.current_state not in (SetupState.H1_FAILED, SetupState.L1_FAILED):
        return False
    
    bars = state.get("bars", [])
    current_bar_index = state.get("current_bar_index", 0)
    
    if not bars or len(bars) < 3:
        return False
    
    current_bar = bars[-1]
    prior_bar = bars[-2]
    
    if entry_state.current_state == SetupState.H1_FAILED:
        # H2: New higher high after pullback
        if current_bar.get("high", 0) > prior_bar.get("high", float('inf')):
            # Also check it's making a higher high relative to recent bars
            recent_high = max(b.get("high", 0) for b in bars[-5:-1])
            if current_bar.get("high", 0) > recent_high:
                entry_state.current_state = SetupState.H2_READY
                entry_state.second_signal_bar_index = current_bar_index
                entry_state.setup_type = "H2_buy"
                entry_state.notes.append(f"H2 signal at bar {current_bar_index}")
                logger.info(f"✅ H2 buy signal detected!")
                return True
    
    elif entry_state.current_state == SetupState.L1_FAILED:
        # L2: New lower low after bounce
        if current_bar.get("low", float('inf')) < prior_bar.get("low", 0):
            # Also check it's making a lower low relative to recent bars
            recent_low = min(b.get("low", float('inf')) for b in bars[-5:-1])
            if current_bar.get("low", float('inf')) < recent_low:
                entry_state.current_state = SetupState.L2_READY
                entry_state.second_signal_bar_index = current_bar_index
                entry_state.setup_type = "L2_sell"
                entry_state.notes.append(f"L2 signal at bar {current_bar_index}")
                logger.info(f"✅ L2 sell signal detected!")
                return True
    
    return False


def should_take_second_entry(entry_state: SecondEntryState) -> bool:
    """Check if conditions are met to take a second entry trade"""
    if entry_state.current_state not in (SetupState.H2_READY, SetupState.L2_READY):
        return False
    
    if entry_state.attempts >= entry_state.max_attempts:
        logger.warning(f"⚠️ Max re-entry attempts ({entry_state.max_attempts}) reached")
        return False
    
    return True


def calculate_second_entry_params(
    state: TradingState,
    entry_state: SecondEntryState
) -> dict[str, Any] | None:
    """
    Calculate entry parameters for a second entry trade.
    
    Uses the same principles as first entry but with:
    - Slightly tighter stop (below the pullback low for H2)
    - Potentially larger position size (higher conviction)
    """
    if not should_take_second_entry(entry_state):
        return None
    
    bars = state.get("bars", [])
    if not bars:
        return None
    
    current_bar = bars[-1]
    
    if entry_state.setup_type == "H2_buy":
        # Entry above signal bar high
        entry_price = current_bar.get("high", 0) + 0.0001
        # Stop below signal bar low (tighter than H1)
        stop_loss = current_bar.get("low", 0) * 0.999
        
        return {
            "direction": "LONG",
            "entry_type": "H2_buy",
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "notes": "Second entry after H1 failure - higher conviction",
            "conviction": "high"
        }
    
    elif entry_state.setup_type == "L2_sell":
        # Entry below signal bar low
        entry_price = current_bar.get("low", 0) - 0.0001
        # Stop above signal bar high (tighter than L1)
        stop_loss = current_bar.get("high", 0) * 1.001
        
        return {
            "direction": "SHORT",
            "entry_type": "L2_sell",
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "notes": "Second entry after L1 failure - higher conviction",
            "conviction": "high"
        }
    
    return None


def process_second_entry(state: TradingState) -> dict[str, Any]:
    """
    Main node function for second entry logic.
    
    This should be called after the L1 screener and before strategy generation.
    It tracks first entry attempts and promotes to second entries when appropriate.
    """
    logger.info("🔄 Processing second entry logic...")
    
    # Load or initialize entry state
    entry_state_dict = state.get("second_entry_state")
    entry_state = SecondEntryState.from_dict(entry_state_dict) if entry_state_dict else SecondEntryState()
    
    # Get L1 screening result
    l1_setup_detected = state.get("l1_setup_detected", False)
    l1_setup_type = state.get("l1_setup_type")
    
    result: dict[str, Any] = {}
    
    # State machine transitions
    if entry_state.current_state == SetupState.WAITING:
        # Looking for first entry signals from L1
        if l1_setup_detected and l1_setup_type:
            if l1_setup_type in ("H1_buy", "H2_buy"):
                # H1 will be handled by main flow, we just track it
                if l1_setup_type == "H1_buy":
                    entry_state.current_state = SetupState.H1_TRIGGERED
                    entry_state.first_entry_bar_index = state.get("current_bar_index", 0)
                    current_bar = state.get("current_bar") or {}
                    entry_state.first_entry_price = current_bar.get("close")
                    entry_state.notes.append(f"H1 triggered at bar {entry_state.first_entry_bar_index}")
                    logger.info(f"📊 Tracking H1 entry for potential H2 follow-up")
                    
            elif l1_setup_type in ("L1_sell", "L2_sell"):
                if l1_setup_type == "L1_sell":
                    entry_state.current_state = SetupState.L1_TRIGGERED
                    entry_state.first_entry_bar_index = state.get("current_bar_index", 0)
                    current_bar = state.get("current_bar") or {}
                    entry_state.first_entry_price = current_bar.get("close")
                    entry_state.notes.append(f"L1 triggered at bar {entry_state.first_entry_bar_index}")
                    logger.info(f"📊 Tracking L1 entry for potential L2 follow-up")
    
    elif entry_state.current_state in (SetupState.H1_TRIGGERED, SetupState.L1_TRIGGERED):
        # Check if first entry has failed
        detect_first_entry_failure(state, entry_state)
    
    elif entry_state.current_state in (SetupState.H1_FAILED, SetupState.L1_FAILED):
        # Check for second entry signal
        detect_second_entry_signal(state, entry_state)
    
    elif entry_state.current_state in (SetupState.H2_READY, SetupState.L2_READY):
        # Generate second entry parameters
        entry_params = calculate_second_entry_params(state, entry_state)
        if entry_params:
            result["second_entry_signal"] = True
            result["second_entry_params"] = entry_params
            entry_state.attempts += 1
            logger.info(f"🎯 Second entry ready: {entry_params['entry_type']}")
        
        # Reset after processing (whether successful or not)
        entry_state.reset()
    
    # Timeout: reset if too many bars have passed since first entry
    if entry_state.first_entry_bar_index is not None:
        bars_since_entry = (state.get("current_bar_index", 0) - entry_state.first_entry_bar_index)
        if bars_since_entry > 10:  # Timeout after 10 bars
            logger.info(f"⏰ Second entry timeout - resetting state")
            entry_state.reset()
    
    # Save state
    result["second_entry_state"] = entry_state.to_dict()
    
    return result
