"""
交易系统监督者图 (Supervisor Graph)

核心架构：
1. 将while循环重构为声明式图结构
2. 状态持久化（SqliteSaver）
3. 条件路由替代if/else
4. 支持Human-in-the-loop
"""

import os
from datetime import datetime, timezone
from typing import Literal, cast, Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.database.account_manager import get_account_manager
from src.trading.exchange_client import normalize_symbol
from src.logger import get_logger
from src.nodes.market_data import fetch_market_data
from src.position_management_workflow import get_position_management_subgraph
from src.safety import ConvictionTracker, get_equity_protector
from src.state import TradingState
from src.graph import get_analysis_subgraph
from src.utils.event_emitter import emit_node_event

logger = get_logger(__name__)



def init_node(state: TradingState) -> TradingState:
    """Initialize the trading system state"""
    logger.info("🎬 Initializing trading system...")
    emit_node_event("node_start", "init", message="Initializing trading system")
    
    # Sync with account manager to get latest state
    am = get_account_manager()
    account_info = am.get_account_info()
    
    # Get current position for the symbol
    symbol = state.get("symbol")
    if symbol:
        symbol = normalize_symbol(symbol)
        
    current_position = next(
        (p for p in account_info.positions if p["symbol"] == symbol), None
    )
    
    # Get any open orders for this symbol
    current_order = next(
        (o for o in account_info.open_orders if o["symbol"] == symbol), None
    )

    updates = {
        "loop_count": state.get("loop_count", 0),
        "last_update": datetime.now(timezone.utc).isoformat(),
        "is_trading_enabled": True,
        "messages": state.get("messages", []) + ["System initialized"],
        "errors": [],
        "account_balance": account_info.total_balance,
        "daily_pnl": state.get("daily_pnl", 0.0),
        "position": current_position,
        "warnings": [],
    }

    # Sync status with actual position/order state
    current_status = state.get("status")
    if current_position:
        updates["status"] = "managing_position"
        updates["next_action"] = "manage"
    elif current_order:
        # If order exists but position doesn't, sync order info
        updates["status"] = "order_pending"
        updates["pending_order_id"] = current_order["id"]
        updates["next_action"] = "manage"
        
        # Use order timestamp if available, format to ISO
        if current_order.get("timestamp"):
            dt = datetime.fromtimestamp(float(current_order["timestamp"]) / 1000.0, tz=timezone.utc)
            updates["order_placed_time"] = dt.isoformat()
        else:
            updates["order_placed_time"] = datetime.now(timezone.utc).isoformat()
            
        logger.info(f"🔄 Synced existing open order: {current_order['id']} at {updates['order_placed_time']}")
    elif state.get("pending_order_id"):
        updates["status"] = "order_pending"
        updates["next_action"] = "manage"
    elif current_status in [
        None,
        "hunting",
        "managing",
        "managing_position",
        "order_pending",
        "looking_for_trade",
    ]:
        # If no position/order, and currently in a "working" state (or old legacy state),
        # ensure it's set to looking_for_trade and next_action is scan
        updates["status"] = "looking_for_trade"
        updates["next_action"] = "scan"

    logger.info(
        f"✓ Initialization complete (Balance: ${account_info.total_balance:.2f}, Position: {'Yes' if current_position else 'No'})"
    )
    emit_node_event("node_complete", "init", {
        "balance": account_info.total_balance,
        "has_position": current_position is not None
    })
    return cast(TradingState, cast(object, updates))


def risk_guard_node(state: TradingState) -> TradingState:
    """
    风控守卫节点 - 每个循环必经之路

    检查：
    1. Equity Protector状态
    2. 日内亏损限制
    3. 连败保护
    """
    logger.debug("🛡️  Risk guard checking...")
    emit_node_event("node_start", "risk_guard", message="Checking risk limits")

    protector = get_equity_protector()

    # 检查是否可以交易
    can_trade = protector.can_trade()

    if not can_trade:
        logger.warning("⏸️  Trading halted by equity protector")
        status = get_equity_protector().get_status()

        return {
            "status": "cooldown",
            "is_trading_enabled": False,
            "next_action": "halt",
            "messages": state.get("messages", [])
            + [f"Risk guard: Trading disabled - {status}"],
        }

    # 通过风控
    logger.debug("✓ Risk guard passed")
    emit_node_event("node_complete", "risk_guard", {"passed": True})
    return cast(TradingState, cast(Any, {
        "is_trading_enabled": True,
        "loop_count": state.get("loop_count", 0) + 1,
        "last_update": datetime.now(timezone.utc).isoformat(),
    }))


def pre_scanner_node(state: TradingState) -> TradingState:
    """
    扫描前置节点 - 准备analysis subgraph需要的状态字段

    由于parent graph和subgraph共享TradingState，
    这里负责设置subgraph需要但parent中格式不同的字段
    """
    logger.info("🔍 HUNTING MODE: Scanning market...")
    emit_node_event("node_start", "pre_scanner", message="Scanning market for opportunities")

    # 准备 subgraph 需要的字段格式
    updates: dict = {
        "primary_timeframe": f"{state.get('timeframe', 60)}m",
    }

    # 确保 positions 格式正确 (subgraph期望 {symbol: position})
    if state.get("position") and state.get("symbol"):
        updates["positions"] = {state["symbol"]: state.get("position")}
    else:
        updates["positions"] = {}

    # 确保 account_info 格式正确
    account_balance = state.get("account_balance", 10000.0)
    daily_pnl = state.get("daily_pnl", 0.0)
    updates["account_info"] = {
        "available_cash": account_balance,
        "daily_pnl_percent": (daily_pnl / account_balance * 100)
        if account_balance > 0
        else 0.0,
        "open_orders": [],
    }

    return cast(TradingState, cast(object, updates))


def post_scanner_node(state: TradingState) -> dict:
    """
    扫描后置节点 - 处理analysis subgraph的执行结果

    检查是否有新订单，更新系统状态
    """
    updates: dict = {"messages": state.get("messages", []) + ["Market scan completed"]}

    # 检查是否有新订单
    exec_results = state.get("execution_results", [])
    if exec_results:
        for res_raw in exec_results:
            res: dict[str, Any] = cast(dict[str, Any], res_raw)
            order_id = cast(str | None, res.get("order_id") or res.get("execution_id"))
            if order_id:
                status: str = res.get("execution_status", "PENDING")
                logger.info(f"📝 Execution result: {order_id} (Status: {status})")

                if status == "FILLED":
                    # If filled, switch to managing mode immediately
                    updates.update(
                        {
                            "status": "managing_position",
                            "position": {
                                "side": cast(str, res.get("side", "long")).lower(),
                                "entry_price": res.get("executed_price")
                                or res.get("entry_price"),
                                "size": res.get("executed_amount") or res.get("amount"),
                                "leverage": res.get("leverage", 20),
                            },
                            "entry_bar_index": state.get("current_bar_index", 0),
                            "pending_order_id": None,
                            "next_action": "manage",
                        }
                    )
                else:
                    # Otherwise, it's pending
                    updates.update(
                        {
                            "status": "order_pending",
                            "pending_order_id": order_id,
                            "order_placed_time": datetime.now(timezone.utc).isoformat(),
                            "next_action": "manage",
                        }
                    )
                break
    else:
        # 无交易信号，继续寻找
        updates["next_action"] = "scan"

    return updates


def pre_manager_node(state: TradingState) -> dict:
    """
    持仓管理前置节点 - 准备manager subgraph需要的状态

    管理活跃订单和持仓
    """
    logger.info("📊 MANAGING MODE: Managing position/order...")

    # 确保我们有市场数据 (bars, current_bar) 用于风险管理
    updates: dict = {}

    if not state.get("current_bar"):
        logger.info("📥 Fetching fresh market data for management...")
        # 准备fetch_market_data需要的输入
        data_input = {
            "symbol": state.get("symbol", "BTC/USDT"),
            "primary_timeframe": f"{state.get('timeframe', 60)}m",
        }
        # 调用fetch_market_data节点
        data_result = fetch_market_data(data_input)  # type: ignore
        updates.update(data_result)

    return updates


def post_manager_node(state: TradingState) -> dict:
    """
    持仓管理后置节点 - 处理manager subgraph的结果

    包括：
    - 检查持仓是否已结束
    - 更新PnL
    - 更新equity protector
    """
    updates: dict = {}

    # 检查是否退出了持仓
    if state.get("status") == "looking_for_trade":
        logger.info("💤 Position closed. Returning to looking_for_trade mode.")
        updates["next_action"] = "scan"

        # 记录PnL
        exit_pnl = state.get("last_trade_pnl")
        if exit_pnl is not None:
            updates["daily_pnl"] = state.get("daily_pnl", 0) + exit_pnl

            # 更新equity protector
            protector = get_equity_protector()
            protector.update_trade_result(
                exit_pnl, state.get("account_balance", 10000.0)
            )
    else:
        # 继续管理
        updates["next_action"] = "manage"

    updates["messages"] = state.get("messages", []) + ["Position management completed"]

    return updates


def cooldown_node(state: TradingState) -> dict:
    """
    冷却节点 - 风控触发后的休息状态
    """
    logger.info("❄️  In cooldown period...")

    # 检查是否可以恢复
    protector = get_equity_protector()
    if protector.can_trade():
        logger.info("✓ Cooldown period ended. Resuming trading.")
        return {
            "status": "looking_for_trade",
            "is_trading_enabled": True,
            "next_action": "scan",
            "messages": state.get("messages", []) + ["Cooldown ended, resuming"],
        }

    # 继续冷却
    return {
        "next_action": "halt",
        "messages": state.get("messages", []) + ["Still in cooldown"],
    }


# ========== 路由函数 ==========


def supervisor_router(
    state: TradingState,
) -> Literal["scanner", "manager", "cooldown", "__end__"]:
    """
    监督者路由 - 核心决策逻辑

    替代原来的 if/elif/else 嵌套
    """

    # 1. 优先处理风控熔断
    if not state.get("is_trading_enabled", True) or state.get("status") == "cooldown":
        logger.debug("→ Router: cooldown")
        return "cooldown"

    # 2. 如果有持仓或挂单，进入管理模式
    if state.get("position") or state.get("pending_order_id"):
        logger.debug("→ Router: manager (has position/order)")
        return "manager"

    # 3. 如果明确指示需要管理
    if state.get("next_action") == "manage":
        logger.debug("→ Router: manager (action=manage)")
        return "manager"

    # 4. 如果需要暂停
    if state.get("next_action") == "halt":
        logger.debug("→ Router: halt")
        return "__end__"

    # 5. 默认：扫描市场
    logger.debug("→ Router: scanner")
    return "scanner"


# ========== 构建监督者图 ==========


def build_trading_supervisor(checkpointer=None) -> CompiledStateGraph[TradingState, Any, TradingState]:
    """
    构建交易系统监督者图

    Args:
        checkpointer: 可选的checkpoint saver（用于状态持久化）

    Returns:
        编译好的StateGraph
    """
    logger.info("🏗️  Building trading supervisor graph...")

    # 创建图
    builder = StateGraph(TradingState)

    # 添加节点
    builder.add_node("init", init_node)
    builder.add_node("risk_guard", risk_guard_node)

    # Scanner分支: pre_scanner -> analysis_subgraph -> post_scanner
    builder.add_node("pre_scanner", pre_scanner_node)
    builder.add_node("scanner", get_analysis_subgraph())  # 直接添加subgraph作为节点
    builder.add_node("post_scanner", post_scanner_node)

    # Manager分支: pre_manager -> manager_subgraph -> post_manager
    builder.add_node("pre_manager", pre_manager_node)
    builder.add_node(
        "manager", get_position_management_subgraph()
    )  # 直接添加subgraph作为节点
    builder.add_node("post_manager", post_manager_node)

    builder.add_node("cooldown", cooldown_node)

    # 设置入口点
    builder.set_entry_point("init")

    # 定义边
    builder.add_edge("init", "risk_guard")

    # 风控后的条件路由
    builder.add_conditional_edges(
        "risk_guard",
        supervisor_router,
        {
            "scanner": "pre_scanner",  # 路由到pre_scanner
            "manager": "pre_manager",  # 路由到pre_manager
            "cooldown": "cooldown",
            "__end__": END,
        },
    )

    # Scanner分支的边: pre_scanner -> scanner (subgraph) -> post_scanner -> END
    builder.add_edge("pre_scanner", "scanner")
    builder.add_edge("scanner", "post_scanner")
    builder.add_edge("post_scanner", END)

    # Manager分支的边: pre_manager -> manager (subgraph) -> post_manager -> END
    builder.add_edge("pre_manager", "manager")
    builder.add_edge("manager", "post_manager")
    builder.add_edge("post_manager", END)

    # Cooldown分支
    builder.add_edge("cooldown", END)

    # 编译
    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
        logger.info("✓ Persistence enabled via injected checkpointer")

    app = builder.compile(**compile_kwargs)

    logger.info("✓ Supervisor graph built successfully")
    return app


# ========== Human-in-the-Loop 支持 ==========


def build_trading_supervisor_with_hitl(
    enable_persistence: bool = True, db_path: str = "./data/trading_state.db"
) -> CompiledStateGraph[TradingState, Any, TradingState]:
    """
    构建支持人工审批的监督者图

    在下单前暂停，等待人工确认
    """
    builder = StateGraph(TradingState)

    # ... (同上，但添加审批节点)

    def approval_node(state: TradingState) -> dict:
        """人工审批节点"""
        logger.info("⏸️  Waiting for human approval...")
        return {}

    builder.add_node("approval", approval_node)

    # 在scanner和manager之间插入approval
    # builder.add_edge("scanner", "approval")
    # builder.add_edge("approval", "manager")

    # 编译时设置中断点
    memory = SqliteSaver.from_conn_string(db_path) if enable_persistence else None

    app = builder.compile(
        checkpointer=cast(Any, memory),
        interrupt_before=["approval"],  # 在审批前暂停
    )

    return cast(CompiledStateGraph[TradingState, Any, TradingState, TradingState], app)
