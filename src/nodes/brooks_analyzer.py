"""
Brooks Analyzer Node
Implements Al Brooks-specific price action analysis including:
- Always In direction tracking
- Market cycle classification
- Signal bar quality evaluation
- Pattern detection (Wedge, MTR, H2/L2, TTR)
"""

import os
import base64
import json
from typing import Any, Literal, cast, Protocol, runtime_checkable
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langfuse import observe

from ..state import TradingState
from ..logger import get_logger
from ..utils.model_manager import get_llm
from ..utils.timeout_decorator import with_timeout
from ..utils.error_handler import with_error_handling, APIError
from ..utils.event_bus import get_event_bus

logger = get_logger(__name__)

from ..models.decisions import (
    BrooksSignalBarQuality,
    BrooksPattern,
    BrooksRiskAssessment,
    BrooksAnalysis,
    create_hold_decision,
    should_force_hold
)

# ==================== Prompts ====================

def get_brooks_analysis_prompt(
    bar_data_table: str,
    include_htf: bool = False,
    htf_summary: str = ""
) -> str:
    """
    Generate prompt for Brooks analysis using VL model with strict CoT enforcement.
    
    Args:
        bar_data_table: OHLC data in table format
        include_htf: Whether to include higher timeframe analysis
        htf_summary: Summary of HTF analysis
    """
    
    htf_section = ""
    if include_htf:
        htf_section = f"""
## Higher Timeframe Context
{htf_summary}
RULE: If HTF is in a strong trend, bias trades in that direction. If HTF is ranging, expect chop.
"""
    
    return f"""You are Al Brooks, the legendary price action trader. You see every tick, every wick, and every trap.
{htf_section}
## OBJECTIVE
Analyze the provided chart images (Context + Focus) and determine the strict "Market Cycle". Then, if and ONLY if a high-quality setup exists, provide a trade recommendation with precise risk parameters.

## THOUGHT PROCESS (Chain of Thought)
You MUST think in this exact order:

1. **PHASE 1: Market Cycle Diagnosis** (The "Context")
   - Is the market in a **Breakout** (Strong Trend)? -> *Action: Go with it.*
   - Is the market in a **Channel** (Weak Trend)? -> *Action: Trade pullbacks.*
   - Is the market in a **Trading Range**? -> *Action: Buy Low / Sell High. Fade breakouts.*
   - Is the market in **Barb Wire** (Tight Trading Range)? -> *Action: DO NOT TRADE. SIT ON HANDS.*
   - **Check for "Barb Wire"**: Look at the last 5-10 bars. Are they overlapping? Are there many dojis? If yes, declare "Barb Wire" and set Action = Wait.

2. **PHASE 2: Signal Bar Evaluation** (The "Trigger")
   - Look at Bar -1 (the last completed bar).
   - Is it a strong Trend Bar? (Big body, small tails).
   - Is it a Reversal Bar? (Hammer/Shooting Star at a swing point).
   - **Trading Range Rule**: If in a Trading Range, Signal Bar MUST be perfect (9/10 quality) to enter. If mediocre, WAIT.

3. **PHASE 3: Risk Assessment** (The "Math")
   - If you recommend a trade, where is the invalidation point (Stop Loss)?
   - Where is the target (Measured Move)?
   - Is Reward/Risk > 2.0? If not, is the probability high enough (60%+) to justify 1:1?

## PATTERN REFERENCE
- **Wedge**: 3 pushes + divergence. Strong reversal signal.
- **MTR (Major Trend Reversal)**: Trend break + test of extreme + lower high/higher low.
- **H1/H2 (L1/L2)**: Pullbacks in a trend. In a Bull trend, look to buy H1 or H2.
- **Barb Wire**: 3+ consecutive overlapping bars with dojis. **DEATH ZONE - DO NOT TRADE.**

## VISUAL INPUTS
- **Context Chart**: 120 bars. Use for Trend Lines, Support/Resistance, and Broad Cycle.
- **Focus Chart**: Last 30 bars. Use for Signal Bar details.
- **Markers**:
    - "S1, S2, S3": Swing Points. Use for stop placement (e.g., "Stop below S2").
    - "-1": The Signal Bar.

## Bar Data (Text)
{bar_data_table}

## OUTPUT REQUIREMENTS
Return valid JSON matching the schema.

### CRITICAL RULES
1. **Trading Range Logic**: If Market Cycle = "Trading Range", you are FORBIDDEN to Buy in the upper third or Sell in the lower third.
2. **Barb Wire Block**: If >= 3 of the last 5 bars overlap heavily -> Action = "wait", Reason = "Barb Wire - market is chopping".
3. **Trend Logic**: In a Strong Bull Trend, ignore weak sell signals (Counter-Trend). In a Strong Bear Trend, ignore weak buy signals.
"""

def create_brooks_messages(
    prompt_text: str,
    chart_image_path: str,
    focus_chart_path: str | None = None,
    htf_chart_path: str | None = None
) -> list[HumanMessage]:
    """Create message list with text and image(s) for VL model"""
    
    def encode_image(path: str) -> str:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    content_parts = [
        {"type": "text", "text": prompt_text}
    ]
    
    # Add HTF chart first if available (for context)
    if htf_chart_path and os.path.exists(htf_chart_path):
        htf_base64 = encode_image(htf_chart_path)
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{htf_base64}",
            }
        })
        content_parts.append({
            "type": "text",
            "text": "☝️ ABOVE: Higher Timeframe Chart (for context)"
        })
    
    # Add Context chart (Primary)
    if os.path.exists(chart_image_path):
        primary_base64 = encode_image(chart_image_path)
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{primary_base64}",
            }
        })
        content_parts.append({
            "type": "text",
            "text": "☝️ ABOVE: Context Chart (120 bars, broad view)"
        })

    # Add Focus chart (Detail)
    if focus_chart_path and os.path.exists(focus_chart_path):
        focus_base64 = encode_image(focus_chart_path)
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{focus_base64}",
            }
        })
        content_parts.append({
            "type": "text",
            "text": "☝️ ABOVE: Focus Chart (Zoomed-in view of the last 30 bars). Use this for precise calculations!"
        })
    
    return [HumanMessage(content=content_parts)]

# ==================== Validation Functions ====================

def validate_brooks_analysis(
    analysis: BrooksAnalysis,
    ohlcv_data: list[list[float]],
    ema20_values: list[float]
) -> dict[str, Any]:
    """
    Cross-check VL analysis against raw OHLC data to detect hallucinations.
    
    Returns:
        Dict with keys: valid (bool), warnings (list), errors (list)
    """
    warnings = []
    errors = []
    
    if len(ohlcv_data) < 2:
        return {"valid": False, "errors": ["Insufficient data"], "warnings": []}
    
    # Get signal bar (index -1)
    signal_bar = ohlcv_data[-2]  # -1 in Python indexing
    current_bar = ohlcv_data[-1]
    
    open_s, high_s, low_s, close_s = signal_bar[1], signal_bar[2], signal_bar[3], signal_bar[4]
    
    # Calculate actual body size
    body = abs(close_s - open_s)
    total_range = high_s - low_s
    body_pct = (body / total_range * 100) if total_range > 0 else 0
    
    # Validation 1: Signal bar body size
    reported_body = analysis.signal_bar.body_size_percent
    if abs(reported_body - body_pct) > 15:  # 15% tolerance
        warnings.append(
            f"Signal bar body size mismatch: VL={reported_body:.1f}%, Actual={body_pct:.1f}%"
        )
    
    # Validation 2: Bar type consistency
    is_bull = close_s > open_s
    is_bear = close_s < open_s
    
    if "bull" in analysis.signal_bar.bar_type and not is_bull:
        errors.append(f"VL says bull bar but Close={close_s} <= Open={open_s}")
    
    if "bear" in analysis.signal_bar.bar_type and not is_bear:
        errors.append(f"VL says bear bar but Close={close_s} >= Open={open_s}")
    
    # Validation 3: EMA relationship
    if len(ema20_values) > 0:
        current_ema = ema20_values[-1]
        current_price = close_s
        
        if "above" in analysis.ema20_relationship and current_price < current_ema:
            warnings.append(
                f"VL says price above EMA but {current_price:.2f} < {current_ema:.2f}"
            )
        
        if "below" in analysis.ema20_relationship and current_price > current_ema:
            warnings.append(
                f"VL says price below EMA but {current_price:.2f} > {current_ema:.2f}"
            )
    
    # Validation 4: Always In direction vs trend
    if analysis.always_in_direction == "long":
        # Check recent bars for higher highs/higher lows
        if len(ohlcv_data) >= 5:
            recent_highs = [bar[2] for bar in ohlcv_data[-5:]]
            if recent_highs[-1] < recent_highs[0]:
                warnings.append("Always In Long but recent highs are declining")
    
    valid = len(errors) == 0
    
    return {
        "valid": valid,
        "warnings": warnings,
        "errors": errors
    }

# ==================== Fallback Function ====================

def brooks_fallback(state: TradingState) -> dict:
    """
    Fallback if Brooks analysis times out.
    Returns conservative Hold recommendation.
    """
    logger.warning("⏱️ Brooks analysis timed out - using conservative fallback")
    return {
        "brooks_analysis": {
            "market_cycle": "trading_range",
            "always_in_direction": "neutral",
            "setup_quality": 0,
            "signal_bar": {
                "bar_index": -1,
                "quality_score": 0,
                "bar_type": "doji",
                "body_size_percent": 50.0,
                "tail_ratio": 1.0,
                "follow_through": False,
                "closes_near": "mid"
            },
            "detected_patterns": [],
            "buying_pressure": 5,
            "selling_pressure": 5,
            "context_summary": "Analysis timed out - no context available",
            "ema20_relationship": "at",
            "recommended_action": "wait",
            "wait_reason": "Brooks analysis exceeded timeout - recommending HOLD for safety",
            "risk_assessment": None,
            "_validation": {"valid": False, "errors": ["Timeout"], "warnings": ["Analysis did not complete"]}
        },
        "validation_result": {"valid": False, "errors": ["Timeout"], "warnings": []}
    }

# ==================== Node Function ====================

@observe()
@with_timeout(timeout_seconds=120, fallback_fn=brooks_fallback, operation_name="Brooks Analysis")
@with_error_handling(max_retries=2, retryable_exceptions=(APIError, ConnectionError, TimeoutError))
def brooks_analyzer(state: TradingState) -> dict:
    """
    Brooks-specific price action analysis node.
    
    Uses VL model to analyze chart with Brooks methodology.
    Validates results against OHLC data.
    
    Returns:
        Dict with 'brooks_analysis' and 'validation_result' keys
    """
    logger.info("Running Brooks Analyzer...")
    bus = get_event_bus()
    bus.emit_sync("node_start", {"node": "brooks_analyzer"})
    
    # Extract data from state with fallback logic
    chart_path = state.get("chart_image_path")
    focus_chart_path = state.get("focus_chart_image_path")
    
    # Debug: log what we got from state
    logger.info(f"Chart paths from state: Context={chart_path}, Focus={focus_chart_path}")
    
    # Try to get from market_data if not in state directly
    market_data = state.get("market_data")
    if isinstance(market_data, dict):
        if not chart_path: chart_path = market_data.get('chart_image_path')
        if not focus_chart_path: focus_chart_path = market_data.get('focus_chart_image_path')
    
    htf_chart_path = state.get("htf_chart_path")
    
    if not market_data:
        logger.error("No market data available")
        return {"brooks_analysis": None}
    
    # Get bar data table - handle both dict and object cases
    if isinstance(market_data, dict):
        bar_data_table = market_data.get('bar_data_table', '')
        ohlcv = market_data.get('ohlcv', [])
    else:
        bar_data_table = market_data.bar_data_table if hasattr(market_data, 'bar_data_table') else ""
        ohlcv = market_data.ohlcv if hasattr(market_data, 'ohlcv') else []
    
    if not chart_path or not os.path.exists(chart_path):
        logger.error(f"Chart not found: {chart_path}")
        return {"brooks_analysis": None}
    
    # Build prompt
    htf_summary = ""
    if htf_chart_path and state.get("htf_analysis"):
        htf_analysis = state["htf_analysis"]
        htf_summary = f"""
HTF Trend: {htf_analysis.get('trend', 'Unknown')}
HTF Always In: {htf_analysis.get('always_in_direction', 'Unknown')}
HTF Signal: {htf_analysis.get('signal', 'Unknown')}
"""
    
    prompt_text = get_brooks_analysis_prompt(
        bar_data_table=bar_data_table,
        include_htf=bool(htf_chart_path),
        htf_summary=htf_summary
    )
    
    bus.emit_sync("ai_thinking", {"node": "brooks_analyzer", "step": "analyzing_chart", "message": "Analyzing price action with Brooks methodology..."})
    
    # Create messages with images
    messages = create_brooks_messages(
        prompt_text=prompt_text,
        chart_image_path=chart_path,
        focus_chart_path=focus_chart_path,
        htf_chart_path=htf_chart_path
    )
    
    # Get LLM with structured output
    llm = get_llm()
    structured_llm = llm.with_structured_output(BrooksAnalysis)
    
    try:
        # Invoke VL model
        brooks_analysis = structured_llm.invoke(messages)
        
        if not brooks_analysis:
            logger.error("Brooks analysis returned None")
            return {"brooks_analysis": None}
        
        # Validate against OHLC data
        ema20_values = []
        if hasattr(market_data, 'ohlcv'):
            # Extract EMA values if available in state
            import pandas as pd
            df = pd.DataFrame(market_data.ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
            ema20_values = df['ema20'].tolist()
        
        validation_result = validate_brooks_analysis(
            analysis=brooks_analysis,
            ohlcv_data=ohlcv,
            ema20_values=ema20_values
        )
        
        # Log validation warnings/errors
        if validation_result['warnings']:
            logger.warning(f"Brooks analysis warnings: {validation_result['warnings']}")
        
        if validation_result['errors']:
            logger.error(f"Brooks analysis errors: {validation_result['errors']}")
        
        # Convert to dict for state storage
        analysis_dict = brooks_analysis.model_dump()
        
        # Add validation metadata
        analysis_dict['_validation'] = validation_result
        
        bus.emit_sync("analysis_complete", {"node": "brooks_analyzer", "analysis": analysis_dict})
        
        # NEW: Emit LLM log for frontend display (similar to strategy node)
        bus.emit_sync("llm_log", {
            "node": "brooks_analyzer",
            "model": "VL Model (Brooks Analysis)",
            "prompt": prompt_text,
            "response": json.dumps(analysis_dict, indent=2),
            "reasoning": analysis_dict.get("context_summary", "")
        })
        
        # Persistence
        run_id = state.get("run_id")
        if run_id:
            from ..database.persistence_manager import get_persistence_manager
            try:
                with get_persistence_manager() as pm:
                    pm.record_analysis(
                        run_id=run_id,
                        node_name="brooks_analyzer",
                        content=analysis_dict,
                        reasoning=analysis_dict.get("context_summary", "")
                    )
            except Exception as e:
                logger.warning(f"⚠️  Failed to record Brooks analysis: {e}")

        logger.info(f"Brooks Analysis Complete: {brooks_analysis.market_cycle} | Always In: {brooks_analysis.always_in_direction} | Setup Quality: {brooks_analysis.setup_quality}/10")
        
        return {
            "brooks_analysis": analysis_dict,
            "validation_result": validation_result
        }
        
    except Exception as e:
        logger.error(f"Error in Brooks analyzer: {e}", exc_info=True)
        return {
            "brooks_analysis": None,
            "validation_result": {"valid": False, "errors": [str(e)], "warnings": []}
        }

# Helper functions moved to src/models/decisions.py
