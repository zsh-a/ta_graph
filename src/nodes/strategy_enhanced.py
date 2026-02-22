"""
Enhanced Strategy Node with Dynamic Prompts and Trade Filters
Integrates Brooks analysis and applies anti-overtrading filters.
"""

import json
from langfuse import observe
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage

from ..state import TradingState
from ..prompts import get_trading_system_prompt, get_user_prompt_parts, get_dynamic_trading_prompt
from ..logger import get_logger
from ..database import ModelType
from ..utils.model_manager import get_llm
from ..utils.trade_filters import get_trade_filter
from ..utils.timeout_decorator import with_timeout
from ..utils.event_bus import get_event_bus
import asyncio

load_dotenv()
logger = get_logger(__name__)

from ..models.decisions import (
    EntryPriceRule,
    StopLossPriceRule,
    TakeProfitPriceRule,
    BuyDecision,
    SellDecision,
    AdjustProfit,
    MarketPhase,
    KeyLevels,
    Prediction,
    TradingDecision,
    DecisionResponse,
    create_hold_decision,
    should_force_hold
)


# ==================== Fallback Function ====================

def strategy_fallback(state: TradingState) -> dict:
    """
    Fallback if strategy generation times out.
    Returns safe Hold decision.
    """
    logger.warning("⏱️ Strategy generation timed out - defaulting to HOLD")
    symbol = state.get("symbol", "BTC")
    brooks_analysis = state.get("brooks_analysis")
    return {
        "decisions": [create_hold_decision(
            symbol=symbol,
            wait_reason="Strategy generation exceeded timeout - recommending HOLD for safety",
            brooks_analysis=brooks_analysis
        )]
    }

# ==================== Enhanced Node Logic ====================

@observe()
@with_timeout(timeout_seconds=90, fallback_fn=strategy_fallback, operation_name="Strategy Generation")
def generate_strategy(state: TradingState) -> dict:
    """
    Enhanced strategy generation with Brooks analysis and trade filters.
    
    Flow:
    1. Check if Brooks analysis forces a Hold
    2. Generate decision using dynamic prompt based on market cycle
    3. Apply trade filters
    4. Return decision (potentially overridden to Hold)
    """
    logger.info("Generating Strategy (Enhanced with Brooks)...")
    bus = get_event_bus()
    bus.emit_sync("node_start", {"node": "strategy"})
    
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
            symbol = state.get("symbol", "BTC")
            logger.info(f"Brooks analysis forces HOLD for {symbol}: {hold_reason}")
            hold_decision = create_hold_decision(symbol, hold_reason, brooks_analysis)
            bus.emit_sync("strategy_complete", {"node": "strategy", "decision": hold_decision, "forced": True})
            
            # IMPORTANT: Persist Hold decisions too!
            run_id = state.get("run_id")
            if run_id:
                from ..database.persistence_manager import get_persistence_manager
                try:
                    with get_persistence_manager() as pm:
                        pm.record_decision(
                            run_id=str(run_id),
                            operation="Hold",
                            symbol=hold_decision.get("symbol", state.get("symbol", "BTC")),
                            rationale=hold_reason,
                            wait_reason=hold_reason
                        )
                        
                        # Record minimal chat for Hold decision
                        pm.record_chat(
                            model=ModelType.Qwen,
                            reasoning=hold_reason,
                            user_prompt="Brooks analysis forced Hold",
                            chat_content=json.dumps(hold_decision)
                        )
                        
                        # Emit LLM log for frontend
                        bus.emit_sync("llm_log", {
                            "node": "strategy",
                            "model": "Brooks Analyzer",
                            "prompt": "Brooks analysis forced Hold",
                            "response": json.dumps(hold_decision, indent=2),
                            "reasoning": hold_reason
                        })
                except Exception as e:
                    logger.warning(f"⚠️  Failed to persist Hold decision: {e}")
            
            return {"decisions": [hold_decision]}
    
    # ========== Build Dynamic Prompt ==========
    
    symbols = [s.get("symbol", state.get("symbol", "BTC")) for s in market_states]
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
    
    # Use DeepSeek Reasoner with thinking mode for strategy generation
    # llm = get_llm("deepseek_reasoner")
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
        
        # Prepare market data for quantitative filters
        import pandas as pd
        market_data_df = None
        
        # Try to extract OHLC data from the first market state or main market_data
        md_source = market_states[0] if market_states else state.get("market_data", {})
        
        if hasattr(md_source, 'ohlcv'):
            if isinstance(md_source.ohlcv, list):
                try:
                    market_data_df = pd.DataFrame(
                        md_source.ohlcv, 
                        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    )
                except Exception as e:
                    logger.warning(f"Failed to convert OHLCV to DataFrame properly: {e}")
        elif isinstance(md_source, dict) and 'ohlcv' in md_source:
             try:
                market_data_df = pd.DataFrame(
                    md_source['ohlcv'], 
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
             except Exception:
                pass

        # Apply all filters
        trade_filter = get_trade_filter()
        passed, failed_reasons = trade_filter.apply_all_filters(
            decision=decision_dict,
            brooks_analysis=brooks_analysis,
            market_data=market_data_df
        )
        
        if not passed:
            # Override to Hold with combined reasons
            combined_reason = "; ".join(failed_reasons)
            logger.info(f"Trade filtered: {combined_reason}")
            
            hold_decision = create_hold_decision(
                symbol=state.get("symbol", "BTC"),
                wait_reason=combined_reason,
                brooks_analysis=brooks_analysis
            )
            
            return {"decisions": [hold_decision]}
        
        # ========== Decision Passed All Checks ==========
        
        logger.info(f"Generated {decision.operation} decision (passed all filters)")
        bus.emit_sync("strategy_complete", {"node": "strategy", "decision": decision_dict})
        
        # Persistence
        run_id = state.get("run_id")
        if run_id:
            from ..database.persistence_manager import get_persistence_manager
            try:
                with get_persistence_manager() as pm:
                    # Record detailed decision
                    db_decision = pm.record_decision(
                        run_id=str(run_id),
                        operation=str(decision.operation),
                        symbol=str(decision.symbol),
                        rationale=decision.rationale,
                        probability_score=decision.probability_score,
                        entry_rules=decision.buy.model_dump() if decision.buy else (decision.sell.model_dump() if decision.sell else None),
                        prediction=decision.prediction.model_dump() if decision.prediction else None
                    )
                    
                    # Record analysis for tracking
                    pm.record_analysis(
                        run_id=str(run_id),
                        node_name="strategy",
                        content=decision_dict,
                        reasoning=decision.rationale
                    )
                    
                    # Record legacy chat for compatibility
                    pm.record_chat(
                        model=ModelType.Qwen, # Assuming default
                        reasoning=decision.rationale,
                        user_prompt=str(user_content_parts),
                        chat_content=json.dumps(decision_dict)
                    )
                    
                    # NEW: Emit detailed LLM log for frontend display
                    bus.emit_sync("llm_log", {
                        "node": "strategy",
                        "model": "Qwen",
                        "prompt": str(user_content_parts),
                        "response": json.dumps(decision_dict, indent=2),
                        "reasoning": decision.rationale
                    })
                    
                    # Add decision_id to the state so execution can link to it
                    decision_dict["id"] = db_decision.id
                    
            except Exception as e:
                logger.warning(f"⚠️  Failed to record strategy persistence: {e}")

        return {"decisions": [decision_dict]}
        
    except Exception as e:
        logger.error(f"Error in strategy generation: {e}", exc_info=True)
        return {"decisions": []}
