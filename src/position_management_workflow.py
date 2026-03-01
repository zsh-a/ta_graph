"""
持仓管理 LangGraph Workflow

整合所有持仓管理模块的完整工作流
使用统一的TradingState，支持作为subgraph直接添加到supervisor graph
"""

from typing import Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from .state import TradingState
from .nodes.order_monitor import monitor_pending_order
from .nodes.position_sync import sync_position_state, check_position_health
from .nodes.position_guard import guard_position  # Position Guard with trail stops
from .safety import get_equity_protector, ConvictionTracker
from .logger import get_logger

logger = get_logger(__name__)


# 使用统一的TradingState，不再需要单独定义PositionManagementState
# TradingState已包含所有持仓管理需要的字段

# 单例模式 - 编译好的 position management subgraph
_position_management_subgraph: Optional[CompiledStateGraph] = None


def get_position_management_subgraph() -> CompiledStateGraph:
    """
    获取编译好的 Position Management Subgraph（单例模式）
    
    使用统一的TradingState，可以直接作为subgraph添加到supervisor graph
    
    Returns:
        编译好的 Position Management Graph
    """
    global _position_management_subgraph
    
    if _position_management_subgraph is None:
        logger.info("Creating Position Management Subgraph (singleton)...")
        workflow = create_position_management_workflow()
        _position_management_subgraph = workflow.compile()
        logger.info("✓ Position Management Subgraph created")
    
    return _position_management_subgraph


def create_position_management_workflow() -> StateGraph:
    """
    创建持仓管理工作流
    
    使用统一的TradingState，可以直接作为subgraph添加到supervisor graph
    
    Returns:
        LangGraph StateGraph (未编译)
    """
    
    # 创建 Graph - 使用统一的TradingState
    workflow = StateGraph(TradingState)
    
    # ========== Loop B: Managing Mode 节点 ==========

    # 1. 订单监控
    workflow.add_node("monitor_order", monitor_pending_order)
    # Note: confirm_fill is not used in current flow, removed to fix subgraph visualization

    # 2. 持仓状态对账
    workflow.add_node("sync_position", sync_position_state)
    workflow.add_node("check_health", check_position_health)

    # 3. Position Guard - Automated trail stop management
    workflow.add_node("guard_position", guard_position)

    # 4. 安全检查
    workflow.add_node("safety_check", perform_safety_check)
    
    # ========== 条件边：状态路由 ==========
    
    def route_by_status(state: TradingState) -> str:
        """根据状态路由到下一个节点"""
        status = state.get("status", "looking_for_trade")
        
        if status == "order_pending":
            return "monitor_order"
        elif status == "managing_position":
            return "sync_position"
        else:  # looking_for_trade
            return END
    
    def route_after_monitor(state: TradingState) -> str:
        """订单监控后的路由"""
        if state.get("status") == "managing_position":
            return "sync_position"
        else:
            return END

    # ========== 添加边 ==========

    # Entry point
    workflow.set_entry_point("safety_check")

    # Safety check -> Route by status
    workflow.add_conditional_edges(
        "safety_check",
        route_by_status,
        {
            "monitor_order": "monitor_order",
            "sync_position": "sync_position",
            END: END
        }
    )

    # Order monitoring flow
    workflow.add_conditional_edges(
        "monitor_order",
        route_after_monitor,
        {
            "sync_position": "sync_position",
            END: END
        }
    )

    # Position management flow
    workflow.add_edge("sync_position", "check_health")
    workflow.add_edge("check_health", "guard_position")
    workflow.add_edge("guard_position", END)
    
    return workflow




def perform_safety_check(state: TradingState) -> dict:
    """
    执行安全检查
    
    1. 检查 Equity Protector（是否允许交易）
    2. 检查 Conviction Tracker（信念是否足够）
    
    Returns:
        dict: 状态更新
    """
    # 1. Equity Protector 检查
    equity_protector = get_equity_protector()
    
    if not equity_protector.can_trade():
        logger.warning("🛑 Trading disabled by Equity Protector")
        return {
            "status": "looking_for_trade",
            "errors": state.get("errors", []) + ["Trading disabled by equity protector"]
        }
    
    # 2. Conviction Tracker（如果在决策阶段）
    # 注：TradingState中没有pending_decision字段，这里跳过
    
    return {}


# ========== 使用示例 ==========

def example_usage():
    """示例：如何使用持仓管理工作流"""
    
    # 1. 创建工作流
    workflow = create_position_management_workflow()
    app = workflow.compile()
    
    # 2. 初始化 Equity Protector
    equity_protector = get_equity_protector(
        max_daily_loss_pct=2.0,
        max_consecutive_losses=3
    )
    
    # 3. 准备初始状态
    initial_state = {
        "symbol": "BTC/USDT",
        "exchange": "bitget",
        "status": "managing_position",
        "position": {
            "side": "long",
            "entry_price": 90000.0,
            "size": 0.001,
            "leverage": 20
        },
        "entry_bar_index": 100,
        "current_bar_index": 101,
        "stop_loss": 89000.0,
        "breakeven_locked": False,
        "followthrough_checked": False,
        "should_exit": False,
        "conviction_tracker": ConvictionTracker(),
        "account_balance": 10000.0,
        "bars": [],  # 实际使用时应该包含历史 K 线
        "current_bar": {
            "open": 90500,
            "high": 91000,
            "low": 90200,
            "close": 90800,
            "volume": 1000
        },
        "timeframe": 60
    }
    
    # 4. 运行一次循环
    result = app.invoke(initial_state)
    
    logger.info(f"Workflow completed. Status: {result.get('status')}")
    
    
    # 6. 如果交易结束，更新 Equity Protector
    if result.get("exit_reason"):
        pnl = result.get("exit_pnl", 0)
        equity_protector.update_trade_result(pnl, result["account_balance"])


if __name__ == "__main__":
    example_usage()
