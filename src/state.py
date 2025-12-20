"""
统一的交易状态定义

用于LangGraph Supervisor架构
"""

from typing import TypedDict, Optional, List, Any
from datetime import datetime


class TradingState(TypedDict, total=False):
    """
    完整的交易系统状态
    
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
    
    # ========== 市场数据 ==========
    bars: List[dict]
    current_bar: Optional[dict]
    current_bar_index: int
    current_price: float
    
    # ========== 分析结果 ==========
    market_analysis: Optional[dict]
    brooks_analysis: Optional[dict]
    decisions: Optional[List[dict]]
    
    # ========== 持仓信息 ==========
    position: Optional[dict]  # {"side": "long/short", "entry_price": float, "size": float, ...}
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
    last_trade_pnl: Optional[float]
    
    # ========== 元数据 ==========
    messages: List[str]  # 日志消息
    errors: List[str]  # 错误记录


class AgentState(TypedDict, total=False):
    """
    兼容旧的AgentState定义（用于analysis graph）
    """
    symbol: str
    primary_timeframe: str
    messages: List[Any]
    positions: dict
    account_info: dict
    market_data: Optional[dict]
    market_states: Optional[List[dict]]  # Added for P0 fix
    market_analysis: Optional[dict]
    brooks_analysis: Optional[dict]
    decisions: Optional[List[dict]]
    execution_results: Optional[List[dict]]
    bars: List[dict]
    current_bar: Optional[dict]
    warnings: Optional[List[str]]  # Added for execution visibility
    execution_metadata: Optional[dict]  # Added for execution tracking
    run_id: Optional[str]  # Added for persistence link
