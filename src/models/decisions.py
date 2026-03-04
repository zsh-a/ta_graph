from typing import Literal
from collections.abc import Mapping
from pydantic import BaseModel, Field

class EntryPriceRule(BaseModel):
    type: Literal["bar_high", "bar_low", "bar_close", "current_price"]
    barIndex: int = Field(description="Entry trigger bar index (0 = current, -1 = previous)")
    offset: int | None = Field(default=None, description="Offset in ticks")

class StopLossPriceRule(BaseModel):
    type: Literal["bar_high", "bar_low", "pattern_high", "pattern_low", "swing_high", "swing_low"]
    barIndex: int | None = Field(default=None)
    patternStartBar: int | None = Field(default=None)
    patternEndBar: int | None = Field(default=None)
    swingStartBar: int | None = Field(default=None)
    swingEndBar: int | None = Field(default=None)
    offset: int | None = Field(default=None)
    offsetPercent: float | None = Field(default=None)

class TakeProfitPriceRule(BaseModel):
    type: Literal["measured_move", "risk_multiple", "key_level"]
    measuredMoveBarStart: int | None = Field(default=None)
    measuredMoveBarEnd: int | None = Field(default=None)
    riskMultiple: float | None = Field(default=None)
    keyLevel: float | None = Field(default=None)

class BuyDecision(BaseModel):
    orderType: Literal["STOP", "LIMIT", "MARKET"]
    entryPriceRule: EntryPriceRule
    stopLossPriceRule: StopLossPriceRule
    takeProfitPriceRule: TakeProfitPriceRule
    riskPercent: float = Field(ge=0.5, le=2.0, description="Risk percentage (0.5-2.0%)")

class SellDecision(BaseModel):
    orderType: Literal["STOP", "LIMIT", "MARKET"]
    entryPriceRule: EntryPriceRule
    stopLossPriceRule: StopLossPriceRule
    takeProfitPriceRule: TakeProfitPriceRule
    riskPercent: float = Field(ge=0.5, le=2.0, description="Risk percentage (0.5-2.0%)")

class AdjustProfit(BaseModel):
    stopLoss: float | None = None
    takeProfit: float | None = None

class MarketPhase(BaseModel):
    phase_type: Literal["strong_bull_trend", "weak_bull_trend", "strong_bear_trend", "weak_bear_trend", "trading_range", "breakout_attempt", "reversal"]
    start_bar: int
    end_bar: int
    description: str

class KeyLevels(BaseModel):
    support: float
    resistance: float

class Prediction(BaseModel):
    price_action_bias: Literal["bullish", "bearish", "neutral"]
    market_structure: Literal["trending", "ranging", "transition"]
    confidence: Literal["high", "medium", "low"]
    market_phases: list[MarketPhase] = Field(default_factory=list, description="Recent market phases")
    key_levels: KeyLevels
    setup_type: Literal["pullback", "breakout", "failure_test", "two_way_scalp", "none"] | None = "none"
    primary_timeframe: str | None = None

class TradingDecision(BaseModel):
    operation: Literal["Buy", "Sell", "Hold"]
    symbol: str
    wait_reason: str | None = None
    probability_score: float = Field(description="Probability score 0-100")
    cancelOrderIds: list[str] | None = None
    rationale: str
    buy: BuyDecision | None = None
    sell: SellDecision | None = None
    adjustProfit: AdjustProfit | None = None
    prediction: Prediction

class BrooksSignalBarQuality(BaseModel):
    """Detailed evaluation of the most recent completed bar"""
    bar_index: int = Field(description="Bar index (0 = current, -1 = signal bar)")
    quality_score: int = Field(ge=0, le=10, description="0-10 quality score")
    bar_type: Literal["strong_bull", "weak_bull", "doji", "weak_bear", "strong_bear"]
    body_size_percent: float = Field(description="Body as % of total range (0-100)")
    tail_ratio: float = Field(description="Total tail length / body length")
    follow_through: bool = Field(description="Good continuation from previous bar")
    closes_near: Literal["high", "mid", "low"] = Field(description="Where bar closes relative to its range")

class BrooksPattern(BaseModel):
    """Detected Brooks pattern"""
    pattern_type: Literal[
        "wedge_top", "wedge_bottom",
        "high_1", "high_2", "low_1", "low_2",
        "mtr_top", "mtr_bottom",
        "failed_breakout", "ttr"
    ]
    confidence: Literal["high", "medium", "low"]
    bars_involved: list[int] = Field(description="Bar indices involved in pattern")
    description: str

class BrooksRiskAssessment(BaseModel):
    """Proposed trade risk parameters for Brooks analysis"""
    stop_loss_price: float
    take_profit_price: float
    reward_to_risk_ratio: float = Field(description="Target Reward / Risk. Should be >= 2.0 ideally.")
    stop_loss_type: Literal["swing_low", "swing_high", "bar_extreme", "measured_move"]
    leverage_suggestion: int = Field(ge=1, le=20, default=5)

class BrooksExitManagement(BaseModel):
    """VLM Advanced Stop-Loss & Exit Decision Logic"""
    Market_Context: str = Field(description="Trend, Channel, or Trading Range assessment")
    Trade_Premise: str = Field(description="Definition of why the trade setup is valid")
    Initial_Stop: str = Field(description="Suggested initial stop placement and type")
    Trailing_Strategy: str = Field(description="Conditions for moving the stop loss")
    Proactive_Exit_Triggers: str = Field(description="Measure Move targets, Climax warnings, etc.")
    Actual_Risk_Assessment: str = Field(description="Assessment of actual risk vs initial risk")

class BrooksAnalysis(BaseModel):
    """Complete Al Brooks price action analysis"""
    market_cycle: Literal[
        "strong_bull_trend", "weak_bull_trend",
        "strong_bear_trend", "weak_bear_trend",
        "trading_range", "breakout_mode", "climax"
    ]
    always_in_direction: Literal["long", "short", "neutral"]
    signal_bar: BrooksSignalBarQuality
    detected_patterns: list[BrooksPattern] = Field(default_factory=list)
    buying_pressure: int = Field(ge=0, le=10, description="0-10 scale")
    selling_pressure: int = Field(ge=0, le=10, description="0-10 scale")
    context_summary: str = Field(description="What happened in the last 20-50 bars")
    ema20_relationship: Literal["strong_above", "above", "at", "below", "strong_below"]
    recommended_action: Literal["buy_setup", "sell_setup", "wait"]
    wait_reason: str | None = None
    setup_quality: int = Field(ge=0, le=10, description="Overall setup quality 0-10")
    risk_assessment: BrooksRiskAssessment | None = Field(default=None, description="Required if action is NOT wait")
    exit_management: BrooksExitManagement | None = Field(default=None, description="VLM Stop & Exit strategy")

class DecisionResponse(BaseModel):
    decisions: list[TradingDecision] = Field(min_length=1, max_length=1)


# ==================== Helper Functions ====================

def create_hold_decision(symbol: str, wait_reason: str, brooks_analysis: Mapping[str, object] | None = None) -> dict[str, object]:
    """
    Create a Hold decision with Brooks context.
    Returns a dictionary matching the TradingDecision schema.
    """
    return {
        "operation": "Hold",
        "symbol": symbol,
        "wait_reason": wait_reason,
        "probability_score": 0.0,
        "rationale": f"[Brooks Analysis]: {wait_reason}",
        "buy": None,
        "sell": None,
        "prediction": {
            "price_action_bias": str(brooks_analysis.get('always_in_direction', 'neutral')) if brooks_analysis else 'neutral',
            "market_structure": str(brooks_analysis.get('market_cycle', 'ranging')) if brooks_analysis else 'ranging',
            "confidence": "low",
            "market_phases": [],
            "key_levels": {"support": 0, "resistance": 0}
        }
    }


def should_force_hold(brooks_analysis: Mapping[str, object]) -> tuple[bool, str]:
    """
    Determine if Brooks analysis mandates a Hold decision.
    
    Returns:
        (should_hold: bool, reason: str)
    """
    # Rule 1: TTR with poor signal bar
    if brooks_analysis.get('market_cycle') == 'trading_range':
        signal_bar = brooks_analysis.get('signal_bar', {})
        if isinstance(signal_bar, Mapping):
            score = signal_bar.get('quality_score', 0)
            if isinstance(score, (int, float)) and score < 7:
                return True, "Tight Trading Range with low quality signal bar (< 7/10)"
    
    # Rule 2: Setup quality too low
    setup_quality = brooks_analysis.get('setup_quality', 0)
    if isinstance(setup_quality, (int, float)) and setup_quality < 6:
        return True, f"Overall setup quality {setup_quality}/10 is below threshold (need 6+)"
    
    # Rule 3: VL model recommended wait
    if brooks_analysis.get('recommended_action') == 'wait':
        reason = str(brooks_analysis.get('wait_reason', 'Al Brooks says wait'))
        return True, reason
    
    # Rule 4: Validation errors
    if '_validation' in brooks_analysis:
        validation = brooks_analysis['_validation']
        if isinstance(validation, Mapping):
            if not bool(validation.get('valid', True)):
                return True, f"Validation errors detected: {validation.get('errors')}"
    
    return False, ""
