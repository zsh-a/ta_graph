"""
交易系统监督者图 (Supervisor Graph)

核心架构：
1. 将while循环重构为声明式图结构
2. 状态持久化（SqliteSaver）
3. 条件路由替代if/else
4. 支持Human-in-the-loop
"""

import os
from datetime import datetime
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from src.state import TradingState, AgentState
from src.graph import create_graph
from src.position_management_workflow import create_position_management_workflow
from src.safety import get_equity_protector, ConvictionTracker
from src.logger import get_logger

logger = get_logger(__name__)


# ========== 节点定义 ==========

def init_node(state: TradingState) -> dict:
    """
    初始化节点 - 系统启动时执行一次
    """
    logger.info("🔧 Initializing trading system...")
    
    updates = {
        "loop_count": state.get("loop_count", 0),
        "last_update": datetime.now().isoformat(),
        "is_trading_enabled": True,
        "messages": state.get("messages", []) + ["System initialized"],
        "errors": []
    }
    
    # 确保基本字段存在
    if not state.get("status"):
        updates["status"] = "hunting"
    
    if not state.get("account_balance"):
        updates["account_balance"] = 10000.0
    
    logger.info("✓ Initialization complete")
    return updates


def risk_guard_node(state: TradingState) -> dict:
    """
    风控守卫节点 - 每个循环必经之路
    
    检查：
    1. Equity Protector状态
    2. 日内亏损限制
    3. 连败保护
    """
    logger.debug("🛡️  Risk guard checking...")
    
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
            "messages": state.get("messages", []) + [
                f"Risk guard: Trading disabled - {status}"
            ]
        }
    
    # 通过风控
    logger.debug("✓ Risk guard passed")
    return {
        "is_trading_enabled": True,
        "loop_count": state.get("loop_count", 0) + 1,
        "last_update": datetime.now().isoformat()
    }


def market_scanner_node(state: TradingState) -> dict:
    """
    市场扫描节点 - 包装analysis graph
    
    寻找交易机会
    """
    logger.info("🔍 HUNTING MODE: Scanning market...")
    
    # 准备analysis graph的输入
    analysis_input: AgentState = {
        "symbol": state["symbol"],
        "primary_timeframe": f"{state.get('timeframe', 60)}m",
        "messages": [],
        "positions": {},
        "account_info": {
            "available_cash": state.get("account_balance", 10000.0),
            "daily_pnl_percent": 0.0,
            "open_orders": []
        }
    }
    
    # 调用analysis graph
    # try:
    analysis_graph = create_graph(enable_checkpointing=False, enable_hitl=False)
    result = analysis_graph.invoke(analysis_input)
    
    # 提取结果
    updates = {
        "market_analysis": result.get("market_analysis"),
        "brooks_analysis": result.get("brooks_analysis"),
        "decisions": result.get("decisions"),
        "bars": result.get("bars", []),
        "current_bar": result.get("current_bar"),
        "execution_results": result.get("execution_results"),
        "messages": state.get("messages", []) + ["Market scan completed"]
    }
    
    # 检查是否有新订单
    exec_results = result.get("execution_results", [])
    if exec_results:
        for res in exec_results:
            if res.get("order_id"):
                logger.info(f"📝 New order: {res['order_id']}")
                updates.update({
                    "status": "order_pending",
                    "pending_order_id": res["order_id"],
                    "order_placed_time": datetime.now().isoformat(),
                    "next_action": "manage"
                })
                break
    else:
        # 无交易信号，继续hunting
        updates["next_action"] = "scan"
    
    return updates
        
    # except Exception as e:
    #     logger.error(f"❌ Market scan failed: {e}", exc_info=True)
    #     return {
    #         "errors": state.get("errors", []) + [str(e)],
    #         "next_action": "scan",  # 失败后重试
    #         "messages": state.get("messages", []) + [f"Scan error: {str(e)}"]
    #     }


def position_manager_node(state: TradingState) -> dict:
    """
    持仓管理节点 - 包装position management workflow
    
    管理活跃订单和持仓
    """
    logger.info("📊 MANAGING MODE: Managing position/order...")
    
    # 调用position management workflow
    try:
        pm_workflow = create_position_management_workflow().compile()
        
        # 准备输入（直接使用TradingState，两者兼容）
        pm_input = dict(state)
        
        result = pm_workflow.invoke(pm_input)
        
        # 提取更新
        updates = {
            "status": result.get("status"),
            "position": result.get("position"),
            "stop_loss": result.get("stop_loss"),
            "take_profit": result.get("take_profit"),
            "breakeven_locked": result.get("breakeven_locked", False),
            "followthrough_checked": result.get("followthrough_checked", False),
            "last_followthrough_analysis": result.get("last_followthrough_analysis"),
            "pending_order_id": result.get("pending_order_id"),
            "messages": state.get("messages", []) + ["Position management completed"]
        }
        
        # 检查是否退出了持仓
        if result.get("status") == "looking_for_trade":
            logger.info("💤 Position closed. Returning to hunting mode.")
            updates["next_action"] = "scan"
            
            # 记录PnL
            if result.get("exit_pnl") is not None:
                updates["last_trade_pnl"] = result["exit_pnl"]
                updates["daily_pnl"] = state.get("daily_pnl", 0) + result["exit_pnl"]
                
                # 更新equity protector
                protector = get_equity_protector()
                protector.update_trade_result(
                    result["exit_pnl"],
                    state.get("account_balance", 10000.0)
                )
        else:
            # 继续管理
            updates["next_action"] = "manage"
        
        return updates
        
    except Exception as e:
        logger.error(f"❌ Position management failed: {e}", exc_info=True)
        return {
            "errors": state.get("errors", []) + [str(e)],
            "next_action": "manage",  # 失败后重试管理
            "messages": state.get("messages", []) + [f"Management error: {str(e)}"]
        }


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
            "status": "hunting",
            "is_trading_enabled": True,
            "next_action": "scan",
            "messages": state.get("messages", []) + ["Cooldown ended, resuming"]
        }
    
    # 继续冷却
    return {
        "next_action": "halt",
        "messages": state.get("messages", []) + ["Still in cooldown"]
    }


# ========== 路由函数 ==========

def supervisor_router(state: TradingState) -> Literal["scanner", "manager", "cooldown", "__end__"]:
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

def build_trading_supervisor(
    checkpointer=None
) -> StateGraph:
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
    builder.add_node("scanner", market_scanner_node)
    builder.add_node("manager", position_manager_node)
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
            "scanner": "scanner",
            "manager": "manager",
            "cooldown": "cooldown",
            "__end__": END
        }
    )
    
    # 各节点执行完后都结束（由外部控制循环频率）
    builder.add_edge("scanner", END)
    builder.add_edge("manager", END)
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
    enable_persistence: bool = True,
    db_path: str = "./data/trading_state.db"
) -> StateGraph:
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
        checkpointer=memory,
        interrupt_before=["approval"]  # 在审批前暂停
    )
    
    return app
