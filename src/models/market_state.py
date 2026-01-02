"""
Market State and Trading Plan - Pydantic Models

市场状态快照和交易计划的结构化定义。
用于 L1 文本模型的增量更新和 Python 执行引擎。
"""

from typing import Literal, Any
from pydantic import BaseModel, Field


# ==================== Market State (L1 维护) ====================

class MarketStateSnapshot(BaseModel):
    """
    市场状态快照 - 由 L1 模型在每根 K 线收盘时更新
    
    设计原则：
    - 只存储"状态"而非"数据"
    - 下一时刻只需输入"上一状态 + 新K线特征"
    """
    timestamp: str = Field(description="ISO 格式时间戳")
    
    # Al Brooks 核心概念
    always_in_direction: Literal["long", "short", "unclear"] = Field(
        default="unclear",
        description="Always In 方向：当前市场主导力量"
    )
    market_phase: Literal[
        "strong_bull_trend", "weak_bull_trend", 
        "strong_bear_trend", "weak_bear_trend",
        "trading_range", "breakout", "climax"
    ] = Field(
        default="trading_range",
        description="市场阶段"
    )
    
    # 形态观察
    recent_pattern: str | None = Field(
        default=None,
        description="正在形成的形态，如 'Wedge Top forming', 'H2 setup'"
    )
    
    # 关键价位
    key_levels: dict[str, float] = Field(
        default_factory=dict,
        description="关键价位，如 {'support': 100.5, 'resistance': 105.0}"
    )
    
    # L1 模型的推理记录
    notes: str = Field(
        default="",
        description="重要观察和推理过程"
    )


# ==================== Trading Plan Protocol ====================

class EntryConfig(BaseModel):
    """入场配置 - 由 AI 输出，Python 执行"""
    order_type: Literal["STOP", "LIMIT", "MARKET"] = Field(
        description="订单类型：STOP=突破单, LIMIT=回调单, MARKET=市价单"
    )
    price: float = Field(description="挂单价格")
    expiration_bars: int = Field(
        default=2,
        ge=1,
        le=10,
        description="有效期（K 线数），超过则取消"
    )


class RiskConfig(BaseModel):
    """风控配置"""
    initial_sl: float = Field(description="初始止损价格")
    hard_tp: float | None = Field(
        default=None,
        description="固定止盈价格（Measured Move 目标）"
    )
    breakeven_trigger: float | None = Field(
        default=None,
        description="保本触发价格：当价格触及此处，移动止损到成本价"
    )


class ManagementConfig(BaseModel):
    """持仓管理策略配置"""
    logic: Literal["TREND_FOLLOWING", "SCALP", "SWING"] = Field(
        default="TREND_FOLLOWING",
        description="管理逻辑类型"
    )
    trail_stop_mode: Literal["BAR_BY_BAR", "SWING_POINTS", "FIXED"] = Field(
        default="BAR_BY_BAR",
        description="追踪止损模式"
    )
    premise_invalidation: str | None = Field(
        default=None,
        description="假设失效条件，如 'BEAR_TREND_BAR_CLOSE'"
    )


class TradingPlan(BaseModel):
    """
    完整的交易计划 - AI 输出结构
    
    核心设计：
    - AI 只负责生成/修改此对象
    - Python 执行引擎负责将计划转化为实际 API 调用
    """
    status: Literal["PENDING", "ACTIVE", "CLOSED"] = Field(
        default="PENDING",
        description="计划状态"
    )
    direction: Literal["LONG", "SHORT"] = Field(
        description="交易方向"
    )
    entry: EntryConfig = Field(description="入场配置")
    risk_management: RiskConfig = Field(description="风控配置")
    management_strategy: ManagementConfig = Field(
        default_factory=lambda: ManagementConfig(),
        description="管理策略"
    )
    
    # 元数据
    created_at: str | None = Field(default=None, description="创建时间")
    symbol: str | None = Field(default=None, description="交易对")
    
    def to_execution_params(self) -> dict[str, Any]:
        """转换为执行引擎需要的参数格式"""
        return {
            "side": "buy" if self.direction == "LONG" else "sell",
            "order_type": self.entry.order_type.lower(),
            "entry_price": self.entry.price,
            "stop_loss": self.risk_management.initial_sl,
            "take_profit": self.risk_management.hard_tp,
            "expiration_bars": self.entry.expiration_bars
        }


# ==================== L1 Screener Response ====================

class L1ScreenerResponse(BaseModel):
    """L1 文本模型的结构化输出"""
    
    updated_state: MarketStateSnapshot = Field(
        description="更新后的市场状态"
    )
    setup_detected: bool = Field(
        default=False,
        description="是否检测到潜在的 setup"
    )
    setup_type: str | None = Field(
        default=None,
        description="Setup 类型，如 'H2_buy', 'Wedge_bottom'"
    )
    reasoning: str = Field(
        default="",
        description="推理过程说明"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        default="low",
        description="置信度"
    )
    
    def should_escalate_to_l2(self) -> bool:
        """是否应该升级到 L2 视觉模型"""
        return self.setup_detected and self.confidence in ["high", "medium"]
