"""
统一的交易状态定义

用于LangGraph Supervisor架构和Analysis Graph
合并了原 TradingState 和 AgentState
"""

from typing import TypedDict, Optional, List, Any
from datetime import datetime


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
    run_id: Optional[str]  # Database run ID for persistence
    
    # ========== 配置信息 ==========
    symbol: str
    exchange: str
    timeframe: int  # 分钟
    primary_timeframe: str  # 字符串格式 (e.g., "15m", "1h") - 兼容 AgentState
    
    # ========== 市场数据 ==========
    bars: List[dict]
    current_bar: Optional[dict]
    current_bar_index: int
    current_price: float
    market_data: Optional[dict]  # 兼容 AgentState
    market_states: Optional[List[dict]]  # 多时间框架数据
    
    # ========== 分析结果 ==========
    market_analysis: Optional[dict]
    brooks_analysis: Optional[dict]
    decisions: Optional[List[dict]]
    
    # ========== 账户与持仓 ==========
    account_info: dict  # 兼容 AgentState
    positions: dict  # 兼容 AgentState: {symbol: position_dict}
    position: Optional[dict]  # 单个持仓: {"side": "long/short", "entry_price": float, "size": float, ...}
    entry_bar_index: Optional[int]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    breakeven_locked: bool
    
    # ========== 订单信息 ==========
    pending_order_id: Optional[str]
    order_placed_time: Optional[str]
    
    # ========== 风险管理 ==========
    account_balance: float
    daily_pnl: float
    consecutive_losses: int
    max_daily_loss_pct: float
    is_trading_enabled: bool
    
    # ========== Follow-through分析 ==========
    followthrough_checked: bool
    last_followthrough_analysis: Optional[dict]
    
    # ========== 内部决策信号 ==========
    next_action: Optional[str]  # 'scan', 'manage', 'sleep', 'halt'
    exit_reason: Optional[str]
    should_exit: bool
    
    # ========== 执行结果 ==========
    execution_results: Optional[List[dict]]
    execution_metadata: Optional[dict]  # 执行跟踪元数据
    last_trade_pnl: Optional[float]
    
    # ========== 元数据 ==========
    messages: List[Any]  # 日志消息
    errors: List[str]  # 错误记录
    warnings: Optional[List[str]]  # 警告信息


# ========== 类型别名（向后兼容）==========

# AgentState 现在是 TradingState 的别名
# 所有使用 AgentState 的代码无需修改
AgentState = TradingState

