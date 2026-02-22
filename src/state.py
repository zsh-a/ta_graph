"""
统一的交易状态定义 (Unified Trading State)

用于 LangGraph Supervisor 架构和各子图的统一通信协议。
设计原则：
1. 扁平化常用字段（symbol, status, timeframe）
2. 模块化专业字段（analysis, execution, risk）
3. 强类型化（尽量通过 TypedDict 约束）

Field Ownership Legend:
  Set by: which node(s) write this field
  Read by: which node(s) consume this field
"""

from typing import TypedDict


class TradingState(TypedDict, total=False):
    """
    统一的交易系统状态

    All node functions receive this state and return a partial dict
    that gets merged back. Nodes must NEVER mutate the state dict directly.
    """

    # ── 1. Runtime ──────────────────────────────────────────────
    # Core identifiers and lifecycle tracking.
    run_id: str                 # Set by: supervisor       | Read by: all nodes (DB persistence)
    thread_id: str              # Set by: main.py          | Read by: supervisor
    status: str                 # Set by: init, order_monitor, position_sync, execution
                                # Read by: supervisor_router, all position-management nodes
                                # Values: 'looking_for_trade', 'order_pending', 'managing_position', 'cooldown'
    loop_count: int             # Set by: supervisor       | Read by: supervisor (loop guard)
    last_update: str            # Set by: supervisor       | Read by: frontend

    # ── 2. Market Data (set by: market_data node) ───────────────
    # Raw and processed bar data consumed by analysis & strategy nodes.
    symbol: str                 # Set by: config/main      | Read by: all nodes
    timeframe: str              # Set by: config/main      | Read by: order_monitor, market_data
    exchange: str               # Set by: config/main      | Read by: order_monitor, execution, position_sync

    bars: list[dict[str, object]]            # Set by: market_data | Read by: brooks_analyzer, strategy, position_guard, risk, followthrough
    current_bar: dict[str, object] | None    # Set by: market_data | Read by: order_monitor, position_guard, followthrough
    current_bar_index: int                   # Set by: market_data | Read by: order_monitor, followthrough, second_entry
    current_price: float                     # Set by: market_data | Read by: position_guard, risk

    market_states: list[dict[str, object]]   # Set by: market_data | Read by: strategy, risk
    market_data: dict[str, object]           # Set by: market_data | Read by: strategy, frontend

    # Visual artifacts
    chart_image_path: str       # Set by: market_data      | Read by: brooks_analyzer, followthrough
    focus_chart_image_path: str # Set by: market_data      | Read by: brooks_analyzer

    # ── 3. Analysis Pipeline ────────────────────────────────────
    # Multi-tier funnel: L0 (Python) → L1 (text LLM) → L2 (vision LLM) → Strategy

    # L0: Python Preprocessing (set by: market_data node)
    is_dead_market: bool                  # Read by: supervisor_router (gate to skip L1+)
    brooks_notation: str                  # Read by: l1_screener
    market_context: dict[str, object]     # Read by: l1_screener

    # L1: Text Model Screening (set by: l1_screener)
    l1_analysis: dict[str, object]        # Read by: brooks_analyzer (L2 confirmation)
    l1_market_state: dict[str, object]    # Read by: brooks_analyzer, l1_screener (prev state)
    l1_setup_detected: bool               # Read by: supervisor_router
    l1_setup_type: str | None             # Read by: brooks_analyzer
    l1_reasoning: str                     # Read by: brooks_analyzer
    l1_confidence: str                    # Read by: supervisor_router

    # L2: Vision Model (set by: brooks_analyzer)
    brooks_analysis: dict[str, object]    # Read by: strategy_enhanced, risk
    validation_result: dict[str, object]  # Read by: strategy_enhanced
    trading_plan: object                  # Read by: execution, position_guard (TradingPlan model)

    # Strategy output (set by: strategy_enhanced)
    decisions: list[dict[str, object]]    # Read by: risk, execution

    # ── 4. Account & Position ───────────────────────────────────
    # Financial state and active position tracking.
    account_info: dict[str, object]       # Set by: config/main    | Read by: strategy, risk
    account_balance: float                # Set by: config/main    | Read by: risk
    daily_pnl: float                      # Set by: config/main    | Read by: risk

    # Position management
    position: dict[str, object] | None    # Set by: order_monitor, position_sync, execution
                                          # Read by: position_guard, followthrough, order_monitor
    entry_bar_index: int                  # Set by: order_monitor  | Read by: followthrough

    # Pending order tracking
    pending_order_id: str | None          # Set by: execution      | Read by: order_monitor
    order_placed_time: str | None         # Set by: execution      | Read by: order_monitor

    # ── 5. Execution & Risk ─────────────────────────────────────
    # Outputs from risk assessment and trade execution.
    execution_results: list[dict[str, object]]  # Set by: risk     | Read by: execution
    execution_metadata: dict[str, object]       # Set by: execution| Read by: order_monitor

    # Risk controls
    consecutive_losses: int               # Set by: supervisor     | Read by: risk
    max_daily_loss_pct: float             # Set by: config         | Read by: risk
    is_trading_enabled: bool              # Set by: safety_check   | Read by: supervisor_router

    # ── 6. Signals & Feedback ───────────────────────────────────
    # Routing directives, exit signals, and error tracking.
    next_action: str             # Set by: supervisor_router | Read by: supervisor
                                 # Values: 'scan', 'manage', 'cooldown', 'halt'

    # Exit signals
    should_exit: bool            # Set by: followthrough     | Read by: position_guard
    exit_reason: str             # Set by: followthrough     | Read by: supervisor
    stop_loss: float             # Set by: position_guard, followthrough | Read by: position_guard
    stop_loss_order_id: str      # Set by: position_guard    | Read by: position_guard

    # Error tracking
    error: str                   # Set by: any node          | Read by: supervisor
    errors: list[str]            # Set by: any node (append) | Read by: supervisor, frontend
    warnings: list[str]          # Set by: any node (append) | Read by: frontend
    messages: list[object]       # Set by: any node          | Read by: frontend

    # PnL feedback
    last_trade_pnl: float | None # Set by: supervisor        | Read by: risk
