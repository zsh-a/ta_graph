"""
Position Guard Node - Python-based Automated Stop Management

Implements Brooks' trailing stop modes based on the TradingPlan:
1. BELOW_PRIOR_BAR - Trail stop to below prior bar's low (for longs)
2. BELOW_SWING_LOW - Trail to below recent swing low
3. TIGHT - Use ATR-based tight trailing stop
4. BREAKEVEN - Move to breakeven after reaching 1R profit
"""

from typing import Any
from dataclasses import dataclass
from enum import Enum
import os
from langfuse import observe

from ..trading.exchange_client import get_client, normalize_symbol
from ..logger import get_logger
from ..notification.alerts import notify_trade_event
from ..state import TradingState
from ..utils.l0_preprocessor import calculate_atr
from .followthrough_analyzer import analyze_followthrough

logger = get_logger(__name__)


class TrailStopMode(str, Enum):
    """Trail stop modes from TradingPlan"""
    BELOW_PRIOR_BAR = "BELOW_PRIOR_BAR"
    BELOW_SWING_LOW = "BELOW_SWING_LOW"
    TIGHT = "TIGHT"
    BREAKEVEN = "BREAKEVEN"
    NONE = "NONE"


@dataclass
class StopUpdate:
    """Result of stop calculation"""
    new_stop: float | None
    reason: str
    mode_used: TrailStopMode


def calculate_trail_stop(
    state: TradingState,
    mode: TrailStopMode | str,
    atr_multiplier: float = 1.0
) -> StopUpdate:
    """
    Calculate new trailing stop based on mode.
    
    Args:
        state: Current trading state
        mode: Trail stop mode from TradingPlan
        atr_multiplier: ATR multiplier for TIGHT mode
        
    Returns:
        StopUpdate with new stop price and reason
    """
    position = state.get("position")
    if not position:
        return StopUpdate(None, "No position", TrailStopMode.NONE)
    
    side = position.get("side", "long")
    entry_price = position.get("entry_price", 0)
    current_stop = position.get("stop_loss") or state.get("stop_loss")
    bars = state.get("bars", [])
    
    # Normalize mode to enum
    if isinstance(mode, str):
        try:
            mode = TrailStopMode(mode)
        except ValueError:
            mode = TrailStopMode.NONE

    # Breakeven does not require bar history.
    if mode != TrailStopMode.BREAKEVEN and (not bars or len(bars) < 2):
        return StopUpdate(None, "Insufficient bar data", TrailStopMode.NONE)
    
    current_bar = bars[-1] if bars else {}
    prior_bar = bars[-2] if len(bars) >= 2 else {}
    is_long = side.lower() in ("long", "buy")
    
    new_stop: float | None = None
    reason = ""
    
    if mode == TrailStopMode.BELOW_PRIOR_BAR:
        # Trail to below prior bar's low (for longs) or above high (for shorts)
        if is_long:
            # Small buffer below prior bar's low
            buffer = (prior_bar.get("high", 0) - prior_bar.get("low", 0)) * 0.1
            proposed_stop = prior_bar.get("low", 0) - buffer
            
            # Only move stop up, never down
            if current_stop is None or proposed_stop > current_stop:
                new_stop = proposed_stop
                reason = f"Trail to below prior bar low: {new_stop:.2f}"
            else:
                reason = f"Current stop {current_stop:.2f} already better than prior bar {proposed_stop:.2f}"
        else:
            # Short position - trail to above prior bar's high
            buffer = (prior_bar.get("high", 0) - prior_bar.get("low", 0)) * 0.1
            proposed_stop = prior_bar.get("high", 0) + buffer
            
            if current_stop is None or proposed_stop < current_stop:
                new_stop = proposed_stop
                reason = f"Trail to above prior bar high: {new_stop:.2f}"
            else:
                reason = f"Current stop {current_stop:.2f} already better than prior bar {proposed_stop:.2f}"
    
    elif mode == TrailStopMode.BELOW_SWING_LOW:
        # Find recent swing low/high
        swing_stop = _find_swing_stop(bars, is_long, lookback=10)
        
        if swing_stop:
            if is_long:
                if current_stop is None or swing_stop > current_stop:
                    new_stop = swing_stop
                    reason = f"Trail to below swing low: {new_stop:.2f}"
                else:
                    reason = f"Current stop {current_stop:.2f} already better than swing {swing_stop:.2f}"
            else:
                if current_stop is None or swing_stop < current_stop:
                    new_stop = swing_stop
                    reason = f"Trail to above swing high: {new_stop:.2f}"
                else:
                    reason = f"Current stop {current_stop:.2f} already better than swing {swing_stop:.2f}"
        else:
            reason = "No swing point found in lookback period"
    
    elif mode == TrailStopMode.TIGHT:
        # ATR-based tight trailing stop
        atr = calculate_atr(bars)
        if atr > 0:
            current_price = current_bar.get("close", 0)
            
            if is_long:
                proposed_stop = current_price - (atr * atr_multiplier)
                if current_stop is None or proposed_stop > current_stop:
                    new_stop = proposed_stop
                    reason = f"Tight ATR stop ({atr_multiplier}x): {new_stop:.2f}"
                else:
                    reason = f"Current stop {current_stop:.2f} already tight"
            else:
                proposed_stop = current_price + (atr * atr_multiplier)
                if current_stop is None or proposed_stop < current_stop:
                    new_stop = proposed_stop
                    reason = f"Tight ATR stop ({atr_multiplier}x): {new_stop:.2f}"
                else:
                    reason = f"Current stop {current_stop:.2f} already tight"
        else:
            reason = "Could not calculate ATR"
    
    elif mode == TrailStopMode.BREAKEVEN:
        # Move stop to breakeven (entry price)
        if is_long:
            if current_stop is None or entry_price > current_stop:
                new_stop = entry_price
                reason = f"Moved to breakeven: {new_stop:.2f}"
            else:
                reason = f"Stop already at or above breakeven"
        else:
            if current_stop is None or entry_price < current_stop:
                new_stop = entry_price
                reason = f"Moved to breakeven: {new_stop:.2f}"
            else:
                reason = f"Stop already at or below breakeven"
    
    else:
        reason = "No trail mode specified"
    
    return StopUpdate(new_stop, reason, mode)


def _find_swing_stop(
    bars: list[dict[str, Any]],
    is_long: bool,
    lookback: int = 10
) -> float | None:
    """
    Find recent swing low (for longs) or swing high (for shorts).
    
    Uses a simple 3-bar swing point detection.
    """
    if len(bars) < 5:
        return None
    
    recent_bars = bars[-lookback:] if len(bars) >= lookback else bars
    
    if is_long:
        # Find lowest low with confirmation (3-bar swing low)
        swing_lows = []
        for i in range(1, len(recent_bars) - 1):
            if (recent_bars[i].get("low", float('inf')) < recent_bars[i-1].get("low", float('inf')) and
                recent_bars[i].get("low", float('inf')) < recent_bars[i+1].get("low", float('inf'))):
                swing_lows.append(recent_bars[i].get("low"))
        
        if swing_lows:
            # Use the most recent swing low with a small buffer
            lowest = min(swing_lows)
            buffer = (max(b.get("high", 0) for b in recent_bars) - lowest) * 0.02
            return lowest - buffer
    else:
        # Find highest high with confirmation (3-bar swing high)
        swing_highs = []
        for i in range(1, len(recent_bars) - 1):
            if (recent_bars[i].get("high", 0) > recent_bars[i-1].get("high", 0) and
                recent_bars[i].get("high", 0) > recent_bars[i+1].get("high", 0)):
                swing_highs.append(recent_bars[i].get("high"))
        
        if swing_highs:
            # Use the most recent swing high with a small buffer
            highest = max(swing_highs)
            buffer = (highest - min(b.get("low", float('inf')) for b in recent_bars)) * 0.02
            return highest + buffer
    
    return None


def should_move_to_breakeven(state: TradingState) -> bool:
    """
    Check if position has reached 1R profit to warrant breakeven stop.
    
    Brooks principle: Move to breakeven after 1x risk is captured.
    """
    position = state.get("position")
    if not position:
        return False
    
    entry_price = position.get("entry_price", 0)
    stop_loss = position.get("stop_loss") or state.get("stop_loss")
    
    if not entry_price or not stop_loss:
        return False
    
    risk = abs(entry_price - stop_loss)
    if risk == 0:
        return False
    
    current_bar = state.get("current_bar") or (state.get("bars", [{}])[-1] if state.get("bars") else {})
    current_price = current_bar.get("close", 0)
    
    if not current_price:
        return False
    
    side = position.get("side", "long")
    is_long = side.lower() in ("long", "buy")
    
    if is_long:
        profit = current_price - entry_price
    else:
        profit = entry_price - current_price
    
    # Check if profit >= 1R
    return profit >= risk


@observe()
def guard_position(state: TradingState) -> dict[str, Any]:
    """
    Position Guard Node - Main entry point.
    
    Manages trailing stops based on TradingPlan or default logic.
    
    Flow:
    1. Check if position exists
    2. Determine trail stop mode (from TradingPlan or default)
    3. Calculate new stop if applicable
    4. Update stop on exchange if changed
    
    Returns:
        State updates with new stop loss if applicable
    """
    logger.info("🛡️  Position Guard - Checking trail stop...")
    
    # Check prerequisites
    if state.get("status") != "managing_position":
        logger.debug("Not in position management mode, skipping guard")
        return {}
    
    position = state.get("position")
    if not position:
        logger.warning("No position found in state")
        return {}

    # Run follow-through analysis in the same node, so guard_position is the
    # single execution point for stop/exit actions.
    followthrough_updates = analyze_followthrough(state)
    effective_state: TradingState = {**state, **followthrough_updates}

    position = effective_state.get("position") or position
    side = str(position.get("side", "long")).lower()
    stop_loss = effective_state.get("stop_loss") or position.get("stop_loss")
    current_bar = effective_state.get("current_bar") or (effective_state.get("bars", [{}])[-1] if effective_state.get("bars") else {})
    current_low = current_bar.get("low")
    current_high = current_bar.get("high")

    # Unified exit handling: explicit exit signal or hard stop touched.
    stop_hit = bool(
        stop_loss is not None and (
            (side in ("long", "buy") and current_low is not None and float(current_low) <= float(stop_loss))
            or (side not in ("long", "buy") and current_high is not None and float(current_high) >= float(stop_loss))
        )
    )
    if effective_state.get("should_exit") or stop_hit:
        reason = effective_state.get("exit_reason") or ("stop_loss_hit" if stop_hit else "guard_exit")
        logger.warning(f"🚪 Exiting position. reason={reason}")
        if _close_position_market(effective_state):
            return {
                **followthrough_updates,
                "status": "looking_for_trade",
                "position": None,
                "pending_order_id": None,
                "stop_loss": None,
                "take_profit": None,
                "should_exit": False,
                "exit_reason": str(reason),
            }
        return {**followthrough_updates, "error": f"Failed to close position for reason={reason}"}
    
    # Determine trail stop mode
    trading_plan = effective_state.get("trading_plan")
    trail_mode = TrailStopMode.NONE
    
    if trading_plan:
        # Get mode from TradingPlan.management_strategy
        if hasattr(trading_plan, "management_strategy") and trading_plan.management_strategy:
            trail_mode_str = trading_plan.management_strategy.trail_stop_mode
            try:
                trail_mode = TrailStopMode(trail_mode_str)
            except (ValueError, TypeError):
                trail_mode = TrailStopMode.BELOW_PRIOR_BAR  # Default fallback
        else:
            trail_mode = TrailStopMode.BELOW_PRIOR_BAR
    else:
        # Default behavior: check for breakeven first, then trail by prior bar
        if should_move_to_breakeven(effective_state):
            trail_mode = TrailStopMode.BREAKEVEN
            logger.info("✅ Position at 1R profit - moving to breakeven")
        else:
            trail_mode = TrailStopMode.BELOW_PRIOR_BAR
    
    # Calculate default trailing stop candidate
    atr_multiplier = float(os.getenv("TRAIL_TIGHT_ATR_MULTIPLIER", "1.0"))
    stop_update = calculate_trail_stop(effective_state, trail_mode, atr_multiplier=atr_multiplier)

    # Follow-through analysis can request a tighter stop; keep single writer here.
    requested_tight_stop = effective_state.get("followthrough_tight_stop")
    if isinstance(requested_tight_stop, (int, float)):
        requested_val = float(requested_tight_stop)
        current_stop = position.get("stop_loss") or state.get("stop_loss")
        is_better = (
            current_stop is None
            or (side in ("long", "buy") and requested_val > float(current_stop))
            or (side not in ("long", "buy") and requested_val < float(current_stop))
        )
        if is_better and (stop_update.new_stop is None or (
            side in ("long", "buy") and requested_val > stop_update.new_stop
        ) or (
            side not in ("long", "buy") and requested_val < stop_update.new_stop
        )):
            stop_update = StopUpdate(
                new_stop=requested_val,
                reason="Follow-through tighten stop",
                mode_used=TrailStopMode.TIGHT,
            )
    
    if stop_update.new_stop:
        logger.info(f"📍 Stop update: {stop_update.reason} (mode: {stop_update.mode_used})")
        
        # Try to update on exchange
        update_success = _update_stop_on_exchange(state, stop_update.new_stop)
        
        # Update position in state
        updated_position = {**position, "stop_loss": stop_update.new_stop}
        
        notify_trade_event(
            event="stop_moved",
            state=dict(state),
            old_stop=position.get("stop_loss"),
            new_stop=stop_update.new_stop,
            reason=stop_update.reason
        )
        
        return {
            **followthrough_updates,
            "position": updated_position,
            "stop_loss": stop_update.new_stop,
            "stop_update_reason": stop_update.reason,
            "followthrough_tighten_requested": False,
            "followthrough_tight_stop": None,
        }
    else:
        logger.debug(f"No stop update: {stop_update.reason}")
        return followthrough_updates


def _update_stop_on_exchange(state: TradingState, new_stop: float) -> bool:
    """
    Update stop loss order on exchange.

    Returns:
        True if successful, False otherwise
    """
    trading_mode = os.getenv("TRADING_MODE", "dry-run").lower()

    if trading_mode != "live":
        logger.debug(f"Dry-run mode: would update stop to {new_stop}")
        return True

    try:
        symbol = state.get("symbol")
        if not symbol:
            return False

        exchange_name = os.getenv("EXCHANGE_NAME", "bitget")
        client = get_client(exchange_name)
        trading_symbol = normalize_symbol(symbol, exchange_name)

        position = state.get("position", {})
        side = position.get("side", "long")
        size = position.get("size", 0)

        if not size:
            logger.warning("No position size found, cannot update stop")
            return False

        # Cancel existing stop order if tracked
        existing_stop_id = state.get("stop_loss_order_id")
        if existing_stop_id:
            try:
                client.cancel_order(existing_stop_id, trading_symbol)
                logger.debug(f"Canceled old stop order: {existing_stop_id}")
            except Exception as e:
                logger.warning(f"Failed to cancel old stop order: {e}")

        # Place new stop-market order
        close_side = "sell" if side.lower() in ("long", "buy") else "buy"

        stop_order = client.place_order(
            symbol=trading_symbol,
            side=close_side,
            order_type="stop_market",
            amount=size,
            price=None,
            reduce_only=True,
            params={"stopPrice": new_stop}
        )

        logger.info(f"✅ Stop loss updated to {new_stop} on exchange (Order: {stop_order.id})")
        return True

    except Exception as e:
        logger.error(f"Failed to update stop on exchange: {e}")
        return False


def _close_position_market(state: TradingState) -> bool:
    trading_mode = os.getenv("TRADING_MODE", "dry-run").lower()
    if trading_mode != "live":
        logger.info("Dry-run mode: simulated close position")
        return True

    try:
        symbol = state.get("symbol")
        position = state.get("position", {})
        if not symbol or not position:
            return False

        exchange_name = os.getenv("EXCHANGE_NAME", "bitget")
        client = get_client(exchange_name)
        trading_symbol = normalize_symbol(symbol, exchange_name)

        side = str(position.get("side", "long")).lower()
        size = position.get("size")
        if not size:
            return False

        close_side = "sell" if side in ("long", "buy") else "buy"
        order = client.place_order(
            symbol=trading_symbol,
            side=close_side,
            order_type="market",
            amount=float(size),
            reduce_only=True,
        )
        logger.info(f"✅ Position closed at market: {order.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to close position: {e}")
        return False


def check_volatility_interrupt(state: TradingState, atr_threshold_multiplier: float = 2.0) -> bool:
    """
    Check if market volatility requires immediate attention.
    
    Triggers when current bar range exceeds N times ATR.
    
    Args:
        state: Current trading state
        atr_threshold_multiplier: How many ATRs to trigger interrupt
        
    Returns:
        True if volatility interrupt triggered
    """
    bars = state.get("bars", [])
    if len(bars) < 14:
        return False
    
    atr = calculate_atr(bars)
    if atr == 0:
        return False
    
    current_bar = bars[-1]
    bar_range = current_bar.get("high", 0) - current_bar.get("low", 0)
    
    if bar_range > atr * atr_threshold_multiplier:
        logger.warning(f"⚠️ VOLATILITY INTERRUPT: Bar range {bar_range:.2f} > {atr_threshold_multiplier}x ATR ({atr:.2f})")
        return True

    return False


def calculate_measured_move_target(bars: list[dict], side: str) -> float | None:
    """
    Calculate Measured Move target price.

    Brooks principle: Leg 1 = Leg 2.
    Finds the most recent swing high/low and projects the same distance.

    Args:
        bars: OHLC bar data
        side: Position direction ("long" or "short")

    Returns:
        Target price, or None if insufficient data
    """
    if len(bars) < 20:
        return None

    recent_bars = bars[-20:]

    if side == "long":
        swing_low = min(bar["low"] for bar in recent_bars)
        swing_high = max(bar["high"] for bar in recent_bars)
        leg_height = swing_high - swing_low
        return swing_high + leg_height
    else:  # short
        swing_high = max(bar["high"] for bar in recent_bars)
        swing_low = min(bar["low"] for bar in recent_bars)
        leg_height = swing_high - swing_low
        return swing_low - leg_height
