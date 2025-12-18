"""
持仓管理 LangGraph Workflow

整合所有持仓管理模块的完整工作流
"""

from typing import Literal, TypedDict
from langgraph.graph import StateGraph, END
from datetime import datetime

from .nodes.order_monitor import monitor_pending_order, confirm_order_fill
from .nodes.position_sync import sync_position_state, check_position_health
from .nodes.followthrough_analyzer import analyze_followthrough
from .nodes.risk_manager import manage_risk, check_stop_hit
from .safety import get_equity_protector, ConvictionTracker, check_hallucination_guard
from .logger import get_logger

logger = get_logger(__name__)


class PositionManagementState(TypedDict):
    """持仓管理状态定义"""
    
    # 市场数据
    symbol: str
    exchange: str
    bars: list[dict]
    current_bar: dict
    current_bar_index: int
    timeframe: int
    
    # 系统状态
    status: Literal["looking_for_trade", "order_pending", "managing_position"]
    
    # 订单信息
    pending_order_id: str | None
    order_placed_time: datetime | None
    stop_loss_order_id: str | None
    
    # 持仓信息
    position: dict | None  # {side, entry_price, size, unrealized_pnl, leverage}
    entry_bar_index: int | None
    stop_loss: float | None
    take_profit: float | None
    breakeven_locked: bool
    
    # Follow-through 分析
    followthrough_checked: bool
    last_followthrough_analysis: dict | None
    should_exit: bool
    
    # 风控与安全
    conviction_tracker: ConvictionTracker | None
    account_balance: float
    
    # 其他
    error: str | None
    exit_reason: str | None


def create_position_management_workflow() -> StateGraph:
    """
    创建持仓管理工作流
    
    实现双环架构：
    - Loop A: Hunting Mode（寻找交易机会）
    - Loop B: Managing Mode（持仓管理）
    
    Returns:
        LangGraph StateGraph
    """
    
    # 创建 Graph
    workflow = StateGraph(PositionManagementState)
    
    # ========== Loop B: Managing Mode 节点 ==========
    
    # 1. 订单监控
    workflow.add_node("monitor_order", monitor_pending_order)
    workflow.add_node("confirm_fill", confirm_order_fill)
    
    # 2. 持仓状态对账
    workflow.add_node("sync_position", sync_position_state)
    workflow.add_node("check_health", check_position_health)
    
    # 3. Follow-through 分析
    workflow.add_node("analyze_followthrough", analyze_followthrough)
    
    # 4. 风险管理
    workflow.add_node("manage_risk", manage_risk)
    workflow.add_node("check_stop", check_stop_hit)
    
    # 5. 安全检查
    workflow.add_node("safety_check", perform_safety_check)
    
    # ========== 条件边：状态路由 ==========
    
    def route_by_status(state: PositionManagementState) -> str:
        """根据状态路由到下一个节点"""
        status = state.get("status", "looking_for_trade")
        
        if status == "order_pending":
            return "monitor_order"
        elif status == "managing_position":
            return "sync_position"
        else:  # looking_for_trade
            return END
    
    def route_after_monitor(state: PositionManagementState) -> str:
        """订单监控后的路由"""
        if state.get("status") == "managing_position":
            return "sync_position"
        else:
            return END
    
    def route_after_stop_check(state: PositionManagementState) -> str:
        """止损检查后的路由"""
        # 持仓管理完成，返回主循环
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
    workflow.add_edge("check_health", "analyze_followthrough")
    workflow.add_edge("analyze_followthrough", "manage_risk")
    workflow.add_edge("manage_risk", "check_stop")
    
    workflow.add_edge("check_stop", END)
    
    return workflow




def perform_safety_check(state: PositionManagementState) -> PositionManagementState:
    """
    执行安全检查
    
    1. 检查 Equity Protector（是否允许交易）
    2. 检查 Conviction Tracker（信念是否足够）
    """
    # 1. Equity Protector 检查
    equity_protector = get_equity_protector()
    
    if not equity_protector.can_trade():
        logger.warning("🛑 Trading disabled by Equity Protector")
        state["status"] = "looking_for_trade"
        state["error"] = "Trading disabled by equity protector"
        return state
    
    # 2. Conviction Tracker（如果在决策阶段）
    if state.get("pending_decision"):
        decision = state["pending_decision"]
        
        if not check_hallucination_guard(state, decision):
            logger.warning("🛑 Decision blocked by hallucination guard")
            state["pending_decision"] = None
            return state
    
    return state


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
