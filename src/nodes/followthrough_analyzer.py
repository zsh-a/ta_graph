"""
Follow-through 分析节点 - Follow-through Analyzer

实现 Al Brooks 的核心理念：
"入场后的一两根 K 线决定了交易的质量"
"""

import os
import base64
from typing import Literal, Any
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langfuse import observe

from ..logger import get_logger
from ..notification.alerts import notify_trade_event
from ..utils.model_manager import get_llm
from ..utils.l0_preprocessor import calculate_atr
from ..state import TradingState
from ..database.persistence_manager import get_persistence_manager

logger = get_logger(__name__)


# ==================== Pydantic Models ====================

class FollowThroughAnalysis(BaseModel):
    """Structured output for follow-through analysis"""
    follow_through_quality: Literal["strong", "weak", "disappointing"]
    recommendation: Literal["hold", "exit_market", "tighten_stop", "add_position"]
    reasoning: str = Field(description="Detailed description of bar structure and market feedback")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence level 0.0-1.0")
    key_observations: list[str] = Field(description="List of key observations from the chart")


# ==================== Prompts ====================

def get_followthrough_prompt(
    side: str,
    entry_price: float,
    entry_bar_index: int,
    current_bar_index: int,
    stop_loss: float
) -> str:
    """Generate follow-through analysis prompt for VL model"""
    return f"""You are a position management assistant for the Al Brooks trading system.

# Current State
- Position Side: {side}
- Entry Price: {entry_price}
- Entry Bar Index: {entry_bar_index}
- Current Bar Index: {current_bar_index}
- Stop Loss: {stop_loss}

# Task
Analyze the quality of follow-through after entry. Al Brooks emphasizes: The performance of 1-2 bars after entry is most important.

## Evaluation Criteria

### Strong Follow-through (Good Follow-through)
- **For Long**: Large bullish bar with full body, close near high, short upper shadow
- **For Short**: Large bearish bar with full body, close near low, short lower shadow
- **Recommendation**: Hold or Add (add to position)

### Disappointment
- **After Long Entry**: Doji, bearish bar, or bullish bar with very small body
- **After Short Entry**: Doji, bullish bar, or bearish bar with very small body
- **Characteristics**: Small bar body, long upper/lower shadows, indecision
- **Recommendation**: Tighten Stop or Exit at Market

### Weak but Acceptable
- Correct direction but weak momentum
- **Recommendation**: Hold, continue monitoring

## Visual Analysis Instructions
- Focus on the bars AFTER the entry point (bar index {entry_bar_index})
- Currently analyzing bar index {current_bar_index} (bar {current_bar_index - entry_bar_index} after entry)
- Look at: Bar shapes, body size, tail length, close position, continuation from previous bar
- Compare the follow-through bar(s) to the entry bar

Return ONLY valid JSON matching the FollowThroughAnalysis schema.
"""


@observe()
def analyze_followthrough(state: TradingState) -> dict:
    """
    Analyze follow-through and decide on position strategy
    
    Brooks Principle: Focus only on the performance of 1-2 bars after entry
    
    Args:
        state: Current Agent state
        
    Returns:
        Updated state
    """
    if state.get("status") != "managing_position":
        return {}
    
    entry_bar_index = state.get("entry_bar_index")
    current_bar_index = state.get("current_bar_index")
    
    if entry_bar_index is None or current_bar_index is None:
        return {}
    
    # Calculate number of bars since entry
    bars_since_entry = current_bar_index - entry_bar_index
    
    # Brooks: Only check follow-through on the 1-2 bars after entry
    if bars_since_entry > 2:
        logger.debug("Beyond follow-through window (>2 bars). Skipping analysis.")
        return {}
    
    if bars_since_entry < 1:
        logger.debug("Still on entry bar. Waiting for next bar.")
        return {}
    
    logger.info(f"📊 Analyzing Follow-through: Bar {bars_since_entry} after entry")
    
    # Get position info
    position = state.get("position", {})
    
    # Get chart image path
    chart_image_path = state.get("chart_image_path")
    
    # Use VL model if chart is available, otherwise use simplified analysis
    if chart_image_path and os.path.exists(chart_image_path):
        try:
            analysis = analyze_followthrough_with_vl(state, chart_image_path)
        except Exception as e:
            logger.error(f"VL model analysis failed: {e}. Falling back to simple analysis.")
            analysis = analyze_followthrough_simple(state)
    else:
        logger.warning("No chart image available. Using simplified OHLC analysis.")
        analysis = analyze_followthrough_simple(state)

    # Persistence
    run_id = state.get("run_id")
    if run_id:
        try:
            with get_persistence_manager() as pm:
                pm.record_analysis(
                    run_id=run_id,
                    node_name="followthrough_analyzer",
                    content=analysis,
                    reasoning=analysis.get("reasoning", "")
                )
        except Exception as e:
            logger.warning(f"⚠️  Failed to record follow-through analysis: {e}")
    
    # Build state updates dict (no direct mutation)
    updates: dict = {
        "last_followthrough_analysis": analysis,
        "followthrough_checked": True,
    }

    # Take action based on analysis results
    if analysis["recommendation"] == "exit_market":
        if analysis["confidence"] > 0.7:
            logger.warning(
                f"⚠️ Disappointing follow-through detected. "
                f"Confidence: {analysis['confidence']:.2f}. Exiting at market."
            )
            updates["exit_reason"] = "disappointing_followthrough"
            updates["followthrough_analysis"] = analysis
            updates["should_exit"] = True

    elif analysis["recommendation"] == "tighten_stop":
        logger.info("🔒 Weak follow-through. Tightening stop loss.")
        new_stop = calculate_tighter_stop(state)
        if new_stop:
            updates["followthrough_tighten_requested"] = True
            updates["followthrough_tight_stop"] = new_stop
            updates["stop_tightened"] = True

    elif analysis["recommendation"] == "add_position":
        if analysis["confidence"] > 0.8:
            logger.info("💪 Strong follow-through! Consider adding position.")
            updates["add_signal"] = True

    return updates


def analyze_followthrough_simple(state: dict) -> dict:
    """
    简化版 Follow-through 分析（基于 OHLC 数据）
    
    TODO: 替换为 VL 模型调用
    
    Args:
        state: 当前状态
        
    Returns:
        分析结果
    """
    bars = state.get("bars", [])
    if len(bars) < 1:
        return {
            "follow_through_quality": "unknown",
            "recommendation": "hold",
            "reasoning": "Insufficient data",
            "confidence": 0.5,
            "key_observations": []
        }
    
    position = state.get("position", {})
    side = position.get("side", "long")
    
    # 获取入场后的第一根 K 线
    entry_bar_index = state.get("entry_bar_index", 0)
    if entry_bar_index >= len(bars) - 1:
        current_bar = bars[-1]
    else:
        # 入场后的下一根
        current_bar = bars[entry_bar_index + 1] if entry_bar_index + 1 < len(bars) else bars[-1]
    
    open_price = current_bar.get("open", 0)
    close_price = current_bar.get("close", 0)
    high_price = current_bar.get("high", 0)
    low_price = current_bar.get("low", 0)
    
    # 计算 K 线特征
    body = abs(close_price - open_price)
    total_range = high_price - low_price
    
    if total_range == 0:
        return {
            "follow_through_quality": "weak",
            "recommendation": "hold",
            "reasoning": "Doji bar - market indecision",
            "confidence": 0.6,
            "key_observations": ["Doji pattern"]
        }
    
    body_ratio = body / total_range
    
    # 做多分析
    if side == "long":
        is_bullish = close_price > open_price
        close_position = (close_price - low_price) / total_range if total_range > 0 else 0.5
        
        if is_bullish and body_ratio > 0.6 and close_position > 0.7:
            # 强跟随：大阳线，收盘靠近高点
            return {
                "follow_through_quality": "strong",
                "recommendation": "hold",
                "reasoning": f"Strong bullish bar. Body ratio: {body_ratio:.2f}, close near high",
                "confidence": 0.85,
                "key_observations": [
                    "Large bullish body",
                    "Close near highs",
                    "Strong momentum"
                ]
            }
        
        elif not is_bullish or body_ratio < 0.3:
            # 失望：阴线或小实体
            return {
                "follow_through_quality": "disappointing",
                "recommendation": "exit_market",
                "reasoning": f"Disappointing bar after long entry. Body ratio: {body_ratio:.2f}",
                "confidence": 0.75,
                "key_observations": [
                    "Bearish or weak bar after long entry",
                    "Market not supporting the move",
                    "Consider exit"
                ]
            }
        
        else:
            # 弱但可接受
            return {
                "follow_through_quality": "weak",
                "recommendation": "hold",
                "reasoning": "Weak but acceptable follow-through",
                "confidence": 0.6,
                "key_observations": ["Modest follow-through", "Monitor closely"]
            }
    
    # 做空分析
    else:  # short
        is_bearish = close_price < open_price
        close_position = (high_price - close_price) / total_range if total_range > 0 else 0.5
        
        if is_bearish and body_ratio > 0.6 and close_position > 0.7:
            return {
                "follow_through_quality": "strong",
                "recommendation": "hold",
                "reasoning": f"Strong bearish bar. Body ratio: {body_ratio:.2f}, close near low",
                "confidence": 0.85,
                "key_observations": [
                    "Large bearish body",
                    "Close near lows",
                    "Strong downside momentum"
                ]
            }
        
        elif not is_bearish or body_ratio < 0.3:
            return {
                "follow_through_quality": "disappointing",
                "recommendation": "exit_market",
                "reasoning": f"Disappointing bar after short entry. Body ratio: {body_ratio:.2f}",
                "confidence": 0.75,
                "key_observations": [
                    "Bullish or weak bar after short entry",
                    "Market not supporting the move",
                    "Consider exit"
                ]
            }
        
        else:
            return {
                "follow_through_quality": "weak",
                "recommendation": "hold",
                "reasoning": "Weak but acceptable follow-through",
                "confidence": 0.6,
                "key_observations": ["Modest follow-through", "Monitor closely"]
            }


def calculate_tighter_stop(state: dict) -> float | None:
    """
    计算更紧的止损位
    
    当 Follow-through 弱时，收紧止损以减少风险
    """
    position = state.get("position")
    current_bar = state.get("current_bar")
    
    if not position or not current_bar:
        return None
    
    side = position.get("side")
    current_stop = state.get("stop_loss")
    bars = state.get("bars", [])
    atr = calculate_atr(bars) if bars else 0.0
    min_atr_mult = float(os.getenv("FOLLOWTHROUGH_TIGHTEN_MIN_ATR_MULTIPLIER", "1.0"))
    current_close = current_bar.get("close")

    if side == "long":
        # 收紧到当前 K 线低点
        new_stop = current_bar.get("low")
        if atr > 0 and current_close:
            # Keep stop at least N*ATR away from current price to avoid noise exits.
            floor_stop = current_close - atr * min_atr_mult
            new_stop = min(new_stop, floor_stop) if new_stop else floor_stop
        if new_stop and (current_stop is None or new_stop > current_stop):
            return new_stop
    elif side != "long":
        # 收紧到当前 K 线高点
        new_stop = current_bar.get("high")
        if atr > 0 and current_close:
            ceil_stop = current_close + atr * min_atr_mult
            new_stop = max(new_stop, ceil_stop) if new_stop else ceil_stop
        if new_stop and (current_stop is None or new_stop < current_stop):
            return new_stop
    
    return None


def analyze_followthrough_with_vl(
    state: dict,
    chart_image_path: str
) -> dict:
    """
    Use VL model to analyze follow-through quality
    
    Args:
        state: Current state
        chart_image_path: Path to chart image
        
    Returns:
        Analysis result as dict
    """
    position = state.get("position", {})
    
    # Build prompt
    prompt_text = get_followthrough_prompt(
        side=position.get("side", "long"),
        entry_price=position.get("entry_price", 0),
        entry_bar_index=state.get("entry_bar_index", 0),
        current_bar_index=state.get("current_bar_index", 0),
        stop_loss=state.get("stop_loss", 0)
    )
    
    # Encode image to base64
    with open(chart_image_path, "rb") as image_file:
        image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    
    # Create message with image
    content_parts: Any = [
        {"type": "text", "text": prompt_text},
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{image_base64}",
            }
        }
    ]
    
    messages = [HumanMessage(content=content_parts)]
    
    # Get LLM with structured output
    llm = get_llm()
    structured_llm = llm.with_structured_output(FollowThroughAnalysis)
    
    # Invoke VL model
    analysis = structured_llm.invoke(messages)
    
    if not analysis:
        logger.error("VL model returned None for follow-through analysis")
        raise ValueError("VL model analysis failed")
    
    # Convert to dict - handle both dict and Pydantic model
    if isinstance(analysis, dict):
        return analysis
    return analysis.model_dump()
