"""
Market State and Trading Plan - Pydantic Models

交易计划的结构化定义。
用于 Python 执行引擎。
"""

from typing import Literal, Any
from pydantic import BaseModel, Field

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
