"""
统一的交易状态定义 (Unified Trading State)

用于 LangGraph Supervisor 架构和各子图的统一通信协议。
设计原则：
1. 扁平化常用字段（symbol, status, timeframe）
2. 模块化专业字段（analysis, execution, risk）
3. 强类型化（尽量通过 TypedDict 约束）
"""

from typing import TypedDict


class TradingState(TypedDict, total=False):
    """
    统一的交易系统状态
    """
    
    # ========== 1. 核心运行时状态 (Runtime) ==========
    run_id: str                 # 当前 Tick 的运行 ID，用于日志追踪和持久化
    thread_id: str              # 会话 ID (e.g. BTC_USDT_15m)
    status: str                 # 系统状态: 'looking_for_trade', 'order_pending', 'managing_position', 'cooldown'
    loop_count: int             # 循环计数
    last_update: str            # 最后更新时间 (ISO)
    
    # ========== 2. 市场数据 (Market Data) ==========
    symbol: str                 # 标的符号 (e.g. BTC/USDT)
    timeframe: str              # 时间周期 (e.g. '15m')
    exchange: str               # 交易所名称
    
    # 原始与处理后的 K 线数据
    bars: list[dict[str, object]]            # 标准 K 线列表 [open, high, low, close, volume]
    current_bar: dict[str, object] | None    # 当前未收盘/最新收盘 K 线
    current_bar_index: int                # 当前 K 线在数据集中的索引
    
    # 视觉辅助
    chart_image_path: str       # 回测/分析图表路径
    focus_chart_image_path: str # 焦点区域图表路径
    
    # ========== 3. 分析结果 (Analysis Funnel) ==========
    
    # L0: Python Preprocessing (Volatility/Range)
    is_dead_market: bool                 # 是否为死寂市场（低波动）
    brooks_notation: str                 # 简化的价格行为标记文本，用于 L1 输入
    market_context: dict[str, object]       # 市场上下文特征 (ATR, Volatility, Range Position)
    
    # L1: Text Model Screening (Setup Detection)
    l1_analysis: dict[str, object]          # L1 模型的完整输出 (setup_detected, setup_type, reasoning, confidence)
    l1_market_state: dict[str, object]      # L1 维护的增量市场状态快照 (MarketStateSnapshot)
    
    # L2: Vision Model / Comprehensive Analysis
    brooks_analysis: dict[str, object]      # 详细的 Brooks 价格行为分析结果
    trading_plan: object                    # L2 生成的结构化 TradingPlan (详见 src/models/market_state.py)
    
    # Internal Decision Buffers
    decisions: list[dict[str, object]]      # 策略层生成的初步决策 (TradingDecision)
    
    # ========== 4. 账户与持仓 (Account & Position) ==========
    account_info: dict[str, object]          # 账户余额、可用保证金等
    account_balance: float               # 总权益
    daily_pnl: float                     # 今日盈亏
    
    # 持仓管理
    position: dict[str, object] | None       # 当前活跃持仓详情
    entry_bar_index: int                 # 入场时的 K 线索引
    
    # 挂单管理
    pending_order_id: str | None         # 正在等待成交的订单 ID
    order_placed_time: str | None        # 下单时间
    
    # ========== 5. 执行与风险控制 (Execution & Risk) ==========
    execution_results: list[dict[str, object]] # 风险管理后最终确认的执行方案 (ExecutionPlan)
    execution_metadata: dict[str, object]      # 执行统计 (decisions_received, trades_executed)
    
    # 风险状态
    consecutive_losses: int      # 连续亏损次数
    max_daily_loss_pct: float    # 允许的最大日内亏损比例
    is_trading_enabled: bool     # 交易总开关 (风控熔断)
    
    # ========== 6. 指令与反馈 (Signals & Logs) ==========
    next_action: str             # 路由器使用的下一步指令: 'scan', 'manage', 'cooldown', 'halt'
    
    # 退出与错误
    should_exit: bool                    # 是否在当前循环结束后退出
    exit_reason: str                      # 退出原因
    error: str                           # 最后一个错误信息
    errors: list[str]                    # 错误历史记录
    warnings: list[str]                  # 警告记录
    messages: list[object]                  # 系统运行日志消息
    
    # 盈亏反馈
    last_trade_pnl: float | None         # 上一笔平仓交易的盈亏


# ========== 向后兼容处理 (Compatibility) ==========

# AgentState 是 TradingState 的别名
AgentState = TradingState
