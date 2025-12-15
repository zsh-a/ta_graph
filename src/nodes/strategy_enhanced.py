"""
Enhanced Strategy Node with Dynamic Prompts and Trade Filters
Integrates Brooks analysis and applies anti-overtrading filters.
"""

import os
import json
from typing import List, Literal, Union, Dict, Any
from pydantic import BaseModel, Field
from langfuse.openai import OpenAI
from langfuse import observe
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage

from ..state import AgentState
from ..prompts import get_trading_system_prompt, get_user_prompt_parts, get_dynamic_trading_prompt
from ..logger import get_logger
from ..utils.model_manager import get_llm
from ..utils.trade_filters import get_trade_filter
from ..nodes.brooks_analyzer import create_hold_decision, should_force_hold

load_dotenv()
logger = get_logger(__name__)

# (Keep existing Pydantic models - EntryPriceRule, StopLossPriceRule, etc.)
# ... [Previous model definitions remain the same] ...

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
    market_phases: List[MarketPhase] = Field(min_length=2, max_length=4)
    key_levels: KeyLevels
    setup_type: Literal["pullback", "breakout", "failure_test", "two_way_scalp", "none"] | None = "none"
    primary_timeframe: str | None = None

class TradingDecision(BaseModel):
    operation: Literal["Buy", "Sell", "Hold"]
    symbol: Literal["BTC", "ETH", "SOL", "BNB", "DOGE"]
    wait_reason: str | None = None
    probability_score: float = Field(description="Probability score 0-100")
    cancelOrderIds: List[str] | None = None
    rationale: str
    buy: BuyDecision | None = None
    sell: SellDecision | None = None
    adjustProfit: AdjustProfit | None = None
    prediction: Prediction

class DecisionResponse(BaseModel):
    decisions: List[TradingDecision] = Field(min_length=1, max_length=1)


# ==================== Enhanced Node Logic ====================

@observe()
def generate_strategy(state: AgentState) -> dict:
    """
    Enhanced strategy generation with Brooks analysis and trade filters.
    
    Flow:
    1. Check if Brooks analysis forces a Hold
    2. Generate decision using dynamic prompt based on market cycle
    3. Apply trade filters
    4. Return decision (potentially overridden to Hold)
    """
    logger.info("Generating Strategy (Enhanced with Brooks)...")
    
    # ========== Extract Context ==========
    
    market_states = state.get("market_states", [])
    
    # Adapt legacy market_data if needed
    if not market_states and state.get("market_data"):
        legacy_data = state["market_data"]
        data_dict = legacy_data.model_dump() if hasattr(legacy_data, 'model_dump') else legacy_data
        if state.get("chart_image_path") and not data_dict.get("chart_image_path"):
            data_dict["chart_image_path"] = state["chart_image_path"]
        market_states = [data_dict]

    if not market_states:
        logger.warning("No market states found")
        return {"decisions": []}

    account_info = state.get("account_info", {"available_cash": 0.0, "open_orders": []})
    recent_trades_summary = state.get("recent_trades_summary", "No recent trades.")
    market_analysis = state.get("market_analysis", {})
    brooks_analysis = state.get("brooks_analysis")  # NEW: Brooks analysis
    
    # ========== Check Brooks Forced Hold ==========
    
    if brooks_analysis:
        force_hold, hold_reason = should_force_hold(brooks_analysis)
        
        if force_hold:
            logger.info(f"Brooks analysis forces HOLD: {hold_reason}")
            hold_decision = create_hold_decision(hold_reason, brooks_analysis)
            return {"decisions": [hold_decision]}
    
    # ========== Build Dynamic Prompt ==========
    
    symbols = [s.get("symbol", "BTC") for s in market_states]
    primary_tf = state.get("primary_timeframe", "15m")
    
    # Use dynamic prompt if Brooks analysis available
    if brooks_analysis:
        system_prompt = get_dynamic_trading_prompt(
            symbols=symbols,
            primary_timeframe=primary_tf,
            market_cycle=brooks_analysis.get('market_cycle', 'unknown'),
            always_in_direction=brooks_analysis.get('always_in_direction', 'neutral')
        )
    else:
        # Fallback to standard prompt
        system_prompt = get_trading_system_prompt(symbols, primary_tf)
    
    # Build user prompt with market states and context
    analysis_json = json.dumps(market_analysis, indent=2) if market_analysis else "No prior analysis."
    
    # Inject Brooks analysis into prompt if available
    if brooks_analysis:
        brooks_summary = f"""
## Brooks Price Action Analysis
- Market Cycle: {brooks_analysis.get('market_cycle')}
- Always In: {brooks_analysis.get('always_in_direction')}
- Signal Bar Quality: {brooks_analysis.get('signal_bar', {}).get('quality_score', 0)}/10
- Setup Quality: {brooks_analysis.get('setup_quality', 0)}/10
- Patterns: {', '.join([p.get('pattern_type', 'Unknown') for p in brooks_analysis.get('detected_patterns', [])])}
- Recommended Action: {brooks_analysis.get('recommended_action')}

IMPORTANT: Respect the Brooks analysis. If it says "wait", you should strongly consider Hold.
"""
        analysis_json = brooks_summary + "\n\n" + analysis_json
    
    user_content_parts = get_user_prompt_parts(
        market_states=market_states,
        account_info=account_info,
        recent_trades_summary=recent_trades_summary,
        market_analysis_json=analysis_json
    )
    
    # ========== Call LLM ==========
    
    llm = get_llm()
    structured_llm = llm.with_structured_output(DecisionResponse)
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content_parts)
    ]
    
    try:
        response = structured_llm.invoke(messages)
        
        if not response or not response.decisions:
            logger.warning("LLM returned no decisions")
            return {"decisions": []}
        
        decision = response.decisions[0]
        decision_dict = decision.model_dump()
        
        # ========== Apply Trade Filters ==========
        
        # Skip filters if decision is already Hold
        if decision.operation == "Hold":
            logger.info("Decision is already Hold - skipping filters")
            return {"decisions": [decision_dict]}
        
        # Apply all filters
        trade_filter = get_trade_filter()
        passed, failed_reasons = trade_filter.apply_all_filters(
            decision=decision_dict,
            brooks_analysis=brooks_analysis
        )
        
        if not passed:
            # Override to Hold with combined reasons
            combined_reason = "; ".join(failed_reasons)
            logger.info(f"Trade filtered: {combined_reason}")
            
            hold_decision = create_hold_decision(
                wait_reason=combined_reason,
                brooks_analysis=brooks_analysis
            )
            
            return {"decisions": [hold_decision]}
        
        # ========== Decision Passed All Checks ==========
        
        logger.info(f"Generated {decision.operation} decision (passed all filters)")
        return {"decisions": [decision_dict]}
        
    except Exception as e:
        logger.error(f"Error in strategy generation: {e}", exc_info=True)
        return {"decisions": []}
