"""
订单监控节点 - Order Monitor Node

实现 Al Brooks 的 Setup 时效性原则：
如果挂单在当前 K 线收盘时未成交，则取消订单
"""

from datetime import datetime, timedelta
from typing import TypedDict, Literal
from ..trading.exchange_client import get_client
from ..logger import get_logger
from ..utils.event_bus import get_event_bus

logger = get_logger(__name__)
bus = get_event_bus()


class AgentState(TypedDict):
    """Agent 状态定义（部分）"""
    status: Literal["looking_for_trade", "order_pending", "managing_position"]
    symbol: str
    pending_order_id: str | None
    order_placed_time: datetime | None
    current_bar: dict
    timeframe: int  # 分钟数


def monitor_pending_order(state: AgentState) -> AgentState:
    """
    监控挂单状态
    
    Brooks 原则: Setup 必须及时触发，否则 Setup 失效
    
    Args:
        state: 当前 Agent 状态
        
    Returns:
        更新后的状态
    """
    if state["status"] != "order_pending":
        return state
    
    order_id = state.get("pending_order_id")
    if not order_id:
        logger.warning("Status is order_pending but no order_id found")
        return {**state, "status": "looking_for_trade"}
    
    order_time = state.get("order_placed_time")
    if not order_time:
        logger.warning("No order_placed_time found")
        return state
    
    # 计算 K 线收盘时间
    current_bar_close_time = state["current_bar"].get("close_time")
    if not current_bar_close_time:
        current_bar_close_time = datetime.now()
    
    timeframe_minutes = state.get("timeframe", 60)  # 默认 1 小时
    
    # 检查是否已经过了下单所在的 K 线
    time_elapsed = (current_bar_close_time - order_time).total_seconds() / 60
    
    if time_elapsed >= timeframe_minutes:
        # K 线已经收盘，检查订单是否成交
        try:
            client = get_client(state.get("exchange", "bitget"))
            order_status = client.exchange.fetch_order(order_id, state["symbol"])
            
            if order_status["status"] == "open":
                # 订单仍未成交，取消订单
                logger.warning(
                    f"❌ Setup expired. Order {order_id} not filled after {time_elapsed:.0f} minutes. Canceling..."
                )
                
                client.cancel_order(order_id, state["symbol"])
                
                # Emit cancel event
                bus.emit_sync("order_monitor_update", {
                    "node": "order_monitor",
                    "status": "CANCELED",
                    "order_id": order_id,
                    "symbol": state["symbol"],
                    "reason": "Setup not triggered in time (Brooks principle)"
                })
                
                return {
                    **state,
                    "status": "looking_for_trade",
                    "pending_order_id": None,
                    "order_placed_time": None,
                    "cancel_reason": "Setup not triggered in time (Brooks principle)"
                }
            
            elif order_status["status"] in ["filled", "closed"]:
                # 订单已成交，切换到持仓管理模式
                logger.info(f"✅ Order {order_id} filled. Switching to position management.")
                
                # 获取实际持仓
                positions = client.get_positions()
                position = next(
                    (p for p in positions if p.symbol == state["symbol"]),
                    None
                )
                
                if position:
                    # Emit fill event
                    bus.emit_sync("order_monitor_update", {
                        "node": "order_monitor",
                        "status": "FILLED",
                        "order_id": order_id,
                        "symbol": state["symbol"],
                        "fill_price": position.entry_price,
                        "size": position.size,
                        "side": position.side,
                        "message": "Order filled successfully"
                    })
                    
                    return {
                        **state,
                        "status": "managing_position",
                        "position": {
                            "entry_price": position.entry_price,
                            "size": position.size,
                            "side": position.side,
                            "unrealized_pnl": position.unrealized_pnl,
                            "leverage": position.leverage
                        },
                        "entry_bar_index": state.get("current_bar_index", 0),
                        "pending_order_id": None,
                        "order_placed_time": None
                    }
                else:
                    logger.error("Order filled but no position found!")
                    return {
                        **state,
                        "status": "looking_for_trade",
                        "pending_order_id": None,
                        "error": "Position not found after order fill"
                    }
        
        except Exception as e:
            logger.error(f"Error monitoring order: {e}")
            return {
                **state,
                "error": str(e)
            }
    
    # K 线未收盘，继续等待
    logger.debug(f"Order {order_id} still pending. Elapsed: {time_elapsed:.0f}/{timeframe_minutes} minutes")
    
    # Emit ping event to show monitoring is active
    bus.emit_sync("order_monitor_ping", {
        "node": "order_monitor",
        "order_id": order_id,
        "elapsed": f"{time_elapsed:.1f}m",
        "status": "PENDING"
    })
    
    return state


def confirm_order_fill(state: AgentState) -> AgentState:
    """
    确认订单成交并更新状态
    
    用于立即确认订单状态（不等待 K 线收盘）
    """
    order_id = state.get("pending_order_id")
    if not order_id:
        return state
    
    try:
        client = get_client(state.get("exchange", "bitget"))
        order_status = client.exchange.fetch_order(order_id, state["symbol"])
        
        if order_status["status"] in ["filled", "closed"]:
            logger.info(f"✅ Order {order_id} FILLED at {order_status.get('average', 'N/A')}")
            
            # 获取真实持仓
            positions = client.get_positions()
            position = next(
                (p for p in positions if p.symbol == state["symbol"]),
                None
            )
            
            if position:
                # Emit fill event
                bus.emit_sync("order_monitor_update", {
                    "node": "order_monitor",
                    "status": "FILLED",
                    "order_id": order_id,
                    "symbol": state["symbol"],
                    "fill_price": position.entry_price,
                    "size": position.size,
                    "side": position.side,
                    "message": "Order filled (confirmed)"
                })
                
                return {
                    **state,
                    "status": "managing_position",
                    "position": {
                        "entry_price": position.entry_price,
                        "size": position.size,
                        "side": position.side,
                        "unrealized_pnl": position.unrealized_pnl,
                        "leverage": position.leverage
                    },
                    "entry_bar_index": state.get("current_bar_index", 0),
                    "pending_order_id": None,
                    "order_placed_time": None
                }
        
        elif order_status["status"] == "canceled":
            logger.warning(f"Order {order_id} was canceled")
            
            bus.emit_sync("order_monitor_update", {
                "node": "order_monitor",
                "status": "CANCELED",
                "order_id": order_id,
                "symbol": state["symbol"],
                "reason": "Order canceled externaly"
            })
            
            return {
                **state,
                "status": "looking_for_trade",
                "pending_order_id": None,
                "cancel_reason": "Order canceled externally"
            }
    
    except Exception as e:
        logger.error(f"Error confirming order fill: {e}")
        return {**state, "error": str(e)}
    
    return state
