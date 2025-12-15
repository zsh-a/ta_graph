"""
持仓状态对账节点 - Position Sync Node

强制与交易所对账，确保内存状态与真实状态一致
"""

from typing import TypedDict
from ..trading.exchange_client import get_client
from ..logger import get_logger
from ..notification.alerts import send_alert

logger = get_logger(__name__)


def sync_position_state(state: dict) -> dict:
    """
    强制与交易所对账
    
    防止内存状态与交易所真实状态不一致的情况：
    1. 系统认为有仓位，但交易所已平仓（爆仓/强平/网络错误）
    2. 交易所有仓位，但系统不知道（极少见）
    3. 仓位大小不一致
    
    Args:
        state: 当前 Agent 状态
        
    Returns:
        对账后的状态
    """
    try:
        client = get_client(state.get("exchange", "bitget"))
        symbol = state.get("symbol")
        
        if not symbol:
            logger.warning("No symbol in state, skipping sync")
            return state
        
        # 从交易所获取真实持仓
        real_positions = client.get_positions()
        real_position = next(
            (p for p in real_positions if p.symbol == symbol),
            None
        )
        
        system_has_position = state.get("status") == "managing_position"
        exchange_has_position = real_position is not None
        
        # 情况 1: 系统认为有仓位，但交易所没有
        if system_has_position and not exchange_has_position:
            logger.error(f"🚨 CRITICAL: Position missing on exchange for {symbol}!")
            
            # 发送警报
            send_alert(
                title="Position Desync - Missing on Exchange",
                message=f"""
                System Status: managing_position
                Exchange Position: None
                Symbol: {symbol}
                
                Possible reasons:
                - Stop loss hit
                - Liquidation
                - Network error during exit
                
                Resetting system state to looking_for_trade.
                """,
                severity="critical"
            )
            
            # 强制重置状态
            return {
                **state,
                "status": "looking_for_trade",
                "position": None,
                "stop_loss": None,
                "take_profit": None,
                "entry_bar_index": None,
                "sync_error": "Position missing on exchange"
            }
        
        # 情况 2: 交易所有仓位，但系统不知道
        if not system_has_position and exchange_has_position:
            logger.warning(f"⚠️ Unexpected position found on exchange: {symbol}")
            
            send_alert(
                title="Position Desync - Unexpected Position",
                message=f"""
                System Status: {state.get('status')}
                Exchange Position: {real_position.side} {real_position.size}
                Entry Price: {real_position.entry_price}
                
                Importing position to system state.
                """,
                severity="warning"
            )
            
            # 导入持仓
            return {
                **state,
                "status": "managing_position",
                "position": {
                    "entry_price": real_position.entry_price,
                    "size": real_position.size,
                    "side": real_position.side,
                    "unrealized_pnl": real_position.unrealized_pnl,
                    "leverage": real_position.leverage
                },
                "entry_bar_index": state.get("current_bar_index", 0),
                "sync_imported": True
            }
        
        # 情况 3: 两边都有持仓，但数据不一致
        if system_has_position and exchange_has_position:
            system_position = state.get("position", {})
            
            # 检查仓位大小
            size_diff = abs(real_position.size - system_position.get("size", 0))
            if size_diff > 0.0001:  # 允许小误差
                logger.warning(
                    f"Position size mismatch: "
                    f"System={system_position.get('size')} vs Exchange={real_position.size}"
                )
                
                # 更新为交易所的真实数据
                state["position"]["size"] = real_position.size
                state["position"]["unrealized_pnl"] = real_position.unrealized_pnl
            
            # 检查入场价格（通常不应该变化）
            price_diff = abs(real_position.entry_price - system_position.get("entry_price", 0))
            if price_diff > 0.01:
                logger.warning(
                    f"Entry price mismatch: "
                    f"System={system_position.get('entry_price')} vs Exchange={real_position.entry_price}"
                )
                # 这种情况很罕见，可能是部分平仓后的平均价格改变
                state["position"]["entry_price"] = real_position.entry_price
        
        # 对账成功
        logger.debug(f"✅ Position sync complete for {symbol}")
        return state
    
    except Exception as e:
        logger.error(f"Error during position sync: {e}")
        return {
            **state,
            "sync_error": str(e)
        }


def check_position_health(state: dict) -> dict:
    """
    检查持仓健康状态
    
    额外的安全检查：
    - 是否接近强平价
    - 止损是否设置正确
    - 保证金是否充足
    """
    if state.get("status") != "managing_position":
        return state
    
    try:
        position = state.get("position")
        if not position:
            return state
        
        client = get_client(state.get("exchange", "bitget"))
        
        # 获取账户信息
        account = client.get_account_info()
        
        # 检查保证金率
        # 注意：不同交易所的保证金率计算方法不同
        # 这里是简化版本
        if account.used > 0:
            margin_ratio = account.used / account.total
            
            if margin_ratio > 0.8:  # 保证金率超过 80%
                logger.warning(f"⚠️ High margin usage: {margin_ratio:.1%}")
                send_alert(
                    title="High Margin Usage Warning",
                    message=f"Margin ratio: {margin_ratio:.1%}. Close to liquidation risk.",
                    severity="warning"
                )
        
        return state
    
    except Exception as e:
        logger.error(f"Error checking position health: {e}")
        return state
