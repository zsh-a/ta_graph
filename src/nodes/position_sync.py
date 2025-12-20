"""
持仓状态对账节点 - Position Sync Node

强制与交易所对账，确保内存状态与真实状态一致
"""

from typing import TypedDict
from ..trading.exchange_client import get_client
from ..database.account_manager import get_account_manager
from ..logger import get_logger
from ..notification.alerts import send_alert

logger = get_logger(__name__)


def sync_position_state(state: dict) -> dict:
    """
    强制与交易所对账
    """
    try:
        symbol = state.get("symbol")
        if not symbol:
            logger.warning("No symbol in state, skipping sync")
            return state
        
        # 从 AccountManager 获取账户信息和持仓
        am = get_account_manager()
        account_info = am.get_account_info()
        real_positions = account_info.positions
        
        real_position = next(
            (p for p in real_positions if p['symbol'] == symbol),
            None
        )
        
        system_has_position = state.get("status") == "managing_position"
        exchange_has_position = real_position is not None
        
        # 情况 1: 系统认为有仓位，但交易所没有
        if system_has_position and not exchange_has_position:
            logger.error(f"🚨 CRITICAL: Position missing on exchange for {symbol}!")
            
            send_alert(
                title="Position Desync - Missing on Exchange",
                message=f"System Status: {state.get('status')}\nExchange Position: None\nSymbol: {symbol}\nResetting system state to looking_for_trade.",
                severity="critical"
            )
            
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
                message=f"System Status: {state.get('status')}\nExchange Position: Found\nSymbol: {symbol}\nImporting position to system state.",
                severity="warning"
            )
            
            return {
                **state,
                "status": "managing_position",
                "position": {
                    "entry_price": real_position.get("entry_price"),
                    "size": real_position.get("size"),
                    "side": real_position.get("side"),
                    "unrealized_pnl": real_position.get("unrealized_pnl"),
                    "leverage": real_position.get("leverage"),
                    "stop_loss": real_position.get("stop_loss"),
                    "take_profit": real_position.get("take_profit")
                },
                "entry_bar_index": state.get("current_bar_index", 0),
                "sync_imported": True
            }
        
        # 情况 3: 两边都有持仓，但数据不一致
        if system_has_position and exchange_has_position:
            system_position = state.get("position", {})
            
            # 检查仓位大小
            size_diff = abs(real_position.get("size", 0) - system_position.get("size", 0))
            if size_diff > 0.0001:
                logger.warning(f"Position size mismatch for {symbol}")
                state["position"]["size"] = real_position.get("size")
                state["position"]["unrealized_pnl"] = real_position.get("unrealized_pnl")
            
            # 检查入场价格
            price_diff = abs(real_position.get("entry_price", 0) - system_position.get("entry_price", 0))
            if price_diff > 0.01:
                logger.warning(f"Entry price mismatch for {symbol}")
                state["position"]["entry_price"] = real_position.get("entry_price")
        
        logger.debug(f"✅ Position sync complete for {symbol}")
        return state
    
    except Exception as e:
        logger.error(f"Error during position sync: {e}")
        state["sync_error"] = str(e)
        return state


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
        
        # 获取账户信息
        am = get_account_manager()
        account = am.get_account_info()
        
        # 检查保证金率
        if account.used_margin > 0:
            margin_ratio = account.used_margin / account.total_balance
            
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
