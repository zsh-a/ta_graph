"""
基础风险管理节点 - Basic Risk Manager

DEPRECATED: This module is superseded by position_guard.py which consolidates
all stop management logic (breakeven, trailing stops, measured moves).
The calculate_measured_move_target function has been migrated to position_guard.py.
This file is kept temporarily for reference but is no longer used in the workflow.

Original functionality:
1. Breakeven (保本)
2. Bar-by-Bar Trailing Stop
3. Measured Move Stop
"""

import warnings
warnings.warn(
    "risk_manager is deprecated. Use position_guard instead.",
    DeprecationWarning,
    stacklevel=2,
)

from typing import TypedDict
from ..trading.exchange_client import get_client, normalize_symbol
from ..logger import get_logger
from ..notification.alerts import notify_trade_event

logger = get_logger(__name__)


def manage_risk(state: dict) -> dict:
    """
    动态风险管理
    
    Brooks 止损原则：
    1. 当浮盈 >= 1x Risk 时，移至 Breakeven
    2. 在强趋势中，使用 Bar-by-Bar Trailing Stop
    3. 止损永远不回退（做多时不下移，做空时不上移）
    
    Args:
        state: 当前 Agent 状态
        
    Returns:
        更新后的状态
    """
    if state.get("status") != "managing_position":
        return state
    
    position = state.get("position")
    if not position:
        return state
    
    current_bar = state.get("current_bar")
    if not current_bar:
        return state
    
    current_price = current_bar.get("close")
    entry_price = position.get("entry_price")
    stop_loss = state.get("stop_loss")
    side = position.get("side")
    
    if not all([current_price, entry_price, stop_loss, side]):
        logger.warning("Missing required data for risk management")
        return state
    
    # 计算当前浮盈和初始风险
    if side == "long":
        unrealized_pnl = current_price - entry_price
        risk = entry_price - stop_loss
    else:  # short
        unrealized_pnl = entry_price - current_price
        risk = stop_loss - entry_price
    
    # 1. Breakeven 逻辑
    if unrealized_pnl >= risk and not state.get("breakeven_locked"):
        logger.info(f"💰 Profit >= 1x Risk. Moving stop to Breakeven (Entry: {entry_price})")
        
        new_stop = entry_price
        if update_stop_loss_order(state, new_stop):
            old_stop = stop_loss
            state["stop_loss"] = new_stop
            state["breakeven_locked"] = True
            
            # 发送通知
            notify_trade_event(
                "stop_moved",
                state,
                old_stop=old_stop,
                new_stop=new_stop,
                reason="Breakeven - locked in 1x Risk profit"
            )
    
    # 2. Bar-by-Bar Trailing Stop
    elif state.get("breakeven_locked"):
        bars = state.get("bars", [])
        if len(bars) >= 2:
            prev_bar = bars[-2]
            
            if side == "long":
                # 做多：止损跟随前一根 K 线低点
                potential_stop = prev_bar.get("low")
                if potential_stop and potential_stop > stop_loss:
                    logger.info(f"📈 Trailing stop: {stop_loss} → {potential_stop} (Prev bar low)")
                    
                    if update_stop_loss_order(state, potential_stop):
                        old_stop = stop_loss
                        state["stop_loss"] = potential_stop
                        
                        notify_trade_event(
                            "stop_moved",
                            state,
                            old_stop=old_stop,
                            new_stop=potential_stop,
                            reason="Bar-by-Bar Trailing (Long)"
                        )
            
            else:  # short
                # 做空：止损跟随前一根 K 线高点
                potential_stop = prev_bar.get("high")
                if potential_stop and potential_stop < stop_loss:
                    logger.info(f"📉 Trailing stop: {stop_loss} → {potential_stop} (Prev bar high)")
                    
                    if update_stop_loss_order(state, potential_stop):
                        old_stop = stop_loss
                        state["stop_loss"] = potential_stop
                        
                        notify_trade_event(
                            "stop_moved",
                            state,
                            old_stop=old_stop,
                            new_stop=potential_stop,
                            reason="Bar-by-Bar Trailing (Short)"
                        )
    
    return state


def update_stop_loss_order(state: dict, new_stop_price: float) -> bool:
    """
    更新止损订单
    
    Args:
        state: 当前状态
        new_stop_price: 新的止损价格
        
    Returns:
        是否成功更新
    """
    try:
        client = get_client(state.get("exchange", "bitget"))
        symbol = normalize_symbol(state["symbol"], state.get("exchange", "bitget"))
        position = state.get("position")
        
        if not position:
            return False
        
        # 取消旧的止损订单（如果存在）
        if state.get("stop_loss_order_id"):
            try:
                client.cancel_order(state["stop_loss_order_id"], symbol)
            except Exception as e:
                logger.warning(f"Failed to cancel old stop loss order: {e}")
        
        # 下新的止损订单
        side = "sell" if position["side"] == "long" else "buy"
        
        stop_order = client.place_order(
            symbol=symbol,
            side=side,
            order_type="stop_market",
            amount=position["size"],
            price=None,  # Market order when triggered
            reduce_only=True,
            params={"stopPrice": new_stop_price}
        )
        
        state["stop_loss_order_id"] = stop_order.id
        logger.info(f"✅ Stop loss updated: {new_stop_price} (Order ID: {stop_order.id})")
        
        return True
    
    except Exception as e:
        logger.error(f"Failed to update stop loss: {e}")
        return False


def calculate_measured_move_target(bars: list[dict], side: str) -> float | None:
    """
    计算 Measured Move 目标位
    
    Brooks 原则：Leg 1 = Leg 2
    
    Args:
        bars: K 线数据
        side: 方向 (long/short)
        
    Returns:
        目标价格
    """
    if len(bars) < 20:
        return None
    
    # 简化版本：找最近的 swing high/low
    recent_bars = bars[-20:]
    
    if side == "long":
        # 找最近的 swing low 和从 swing low 开始的涨幅
        swing_low = min(bar["low"] for bar in recent_bars)
        swing_high = max(bar["high"] for bar in recent_bars)
        
        leg_height = swing_high - swing_low
        target = swing_high + leg_height
        
        return target
    
    else:  # short
        swing_high = max(bar["high"] for bar in recent_bars)
        swing_low = min(bar["low"] for bar in recent_bars)
        
        leg_height = swing_high - swing_low
        target = swing_low - leg_height
        
        return target


def check_stop_hit(state: dict) -> dict:
    """
    检查止损是否被触发
    
    Args:
        state: 当前状态
        
    Returns:
        更新后的状态
    """
    if state.get("status") != "managing_position":
        return state
    
    position = state.get("position")
    stop_loss = state.get("stop_loss")
    current_bar = state.get("current_bar")
    
    if not all([position, stop_loss, current_bar]):
        return state
    
    side = position.get("side")
    current_low = current_bar.get("low")
    current_high = current_bar.get("high")
    
    stop_hit = False
    
    if side == "long" and current_low and current_low <= stop_loss:
        logger.warning(f"❌ Stop loss HIT: {stop_loss} (Bar low: {current_low})")
        stop_hit = True
    
    elif side == "short" and current_high and current_high >= stop_loss:
        logger.warning(f"❌ Stop loss HIT: {stop_loss} (Bar high: {current_high})")
        stop_hit = True
    
    if stop_hit:
        # 市价平仓
        try:
            close_position_market(state)
            
            pnl = calculate_pnl(state)
            duration = state.get("current_bar_index", 0) - state.get("entry_bar_index", 0)
            
            notify_trade_event(
                "exit",
                state,
                pnl=pnl,
                reason="Stop Loss Hit",
                duration=duration
            )
            
            return {
                **state,
                "status": "looking_for_trade",
                "position": None,
                "stop_loss": None,
                "take_profit": None,
                "exit_reason": "stop_loss_hit",
                "exit_pnl": pnl
            }
        
        except Exception as e:
            logger.error(f"Failed to close position on stop hit: {e}")
    
    return state


def close_position_market(state: dict):
    """市价平仓"""
    client = get_client(state.get("exchange", "bitget"))
    symbol = normalize_symbol(state["symbol"], state.get("exchange", "bitget"))
    position = state.get("position")
    
    if not position:
        return
    
    # 反向操作平仓
    side = "sell" if position["side"] == "long" else "buy"
    
    order = client.place_order(
        symbol=symbol,
        side=side,
        order_type="market",
        amount=position["size"],
        reduce_only=True
    )
    
    logger.info(f"✅ Position closed at market: {order.id}")


def calculate_pnl(state: dict) -> float:
    """计算盈亏"""
    position = state.get("position")
    current_bar = state.get("current_bar")
    
    if not position or not current_bar:
        return 0.0
    
    entry_price = position.get("entry_price", 0)
    current_price = current_bar.get("close", 0)
    size = position.get("size", 0)
    side = position.get("side")
    
    if side == "long":
        pnl = (current_price - entry_price) * size
    else:
        pnl = (entry_price - current_price) * size
    
    return pnl
