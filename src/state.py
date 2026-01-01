"""
统一的交易状态定义

用于LangGraph Supervisor架构和Analysis Graph
合并了原 TradingState 和 AgentState
"""

from typing import TypedDict, Any


class TradingState(TypedDict, total=False):
    """
    统一的交易系统状态
    
    合并了 Supervisor Graph 和 Analysis Graph 的所有字段
    使用TypedDict确保类型安全，total=False允许部分字段可选
    """
    
    # ========== 核心状态 ==========
    status: str  # 'looking_for_trade', 'order_pending', 'managing_position', 'cooldown', 'halted'
    loop_count: int
    last_update: str  # ISO格式时间戳
    # Base indicators
    bars: list[dict[str, Any]]
    current_bar: dict[str, Any] | None
    current_bar_index: int
    entry_bar_index: int
    symbol: str
    timeframe: str
    exchange: str
    
    # Market analysis
    market_data: dict[str, Any]
    market_states: dict[str, Any]
    market_analysis: dict[str, Any]
    brooks_analysis: dict[str, Any]
    decisions: list[dict[str, Any]]
    
    # Account & Position
    account_info: dict[str, Any]
    positions: list[dict[str, Any]]
    position: dict[str, Any] | None
    
    # Strategy & Execution
    last_followthrough_analysis: dict[str, Any] | None
    execution_results: list[dict[str, Any]]
    execution_metadata: dict[str, Any]
    
    # Flow control
    pending_order_id: str | None
    order_placed_time: str | None
    next_node: str | None
    
    # Error & Cancel
    cancel_reason: str | None
    error: str | None
    
    # ========== 风险管理 ==========
    account_balance: float
    daily_pnl: float
    consecutive_losses: int
    max_daily_loss_pct: float
    is_trading_enabled: bool
    
    # ========== Follow-through分析 ==========
    followthrough_checked: bool
    
    # ========== 内部决策信号 ==========
    next_action: str | None  # 'scan', 'manage', 'sleep', 'halt'
    exit_reason: str | None
    should_exit: bool
    
    # ========== 执行结果 ==========
    last_trade_pnl: float | None
    
    # ========== 元数据 ==========
    run_id: str | None  # Run ID for data persistence
    messages: list[Any]  # 日志消息
    errors: list[str]  # 错误记录
    warnings: list[str] | None  # 警告信息


# ========== 类型别名（向后兼容）==========

# AgentState 现在是 TradingState 的别名
# 所有使用 AgentState 的代码无需修改
AgentState = TradingState
