"""
Follow-through 分析节点 - Follow-through Analyzer

实现 Al Brooks 的核心理念：
"入场后的一两根 K 线决定了交易的质量"
"""

from typing import Literal
from ..logger import get_logger
from ..notification.alerts import notify_trade_event

logger = get_logger(__name__)


# Follow-through Prompt for VL Model
FOLLOWTHROUGH_PROMPT = """你是 Al Brooks 交易系统的持仓管理助手。

# 当前状态
- 持仓方向: {side}
- 入场价格: {entry_price}
- 入场 Bar Index: {entry_bar_index}
- 当前 Bar Index: {current_bar_index}
- 止损位: {stop_loss}

# 任务
分析入场后的 Follow-through（跟随性）质量。Al Brooks 强调：入场后 1-2 根 K 线的表现最重要。

## 评估标准

### 强跟随 (Good Follow-through)
- **做多**: 大阳线，实体饱满，收盘靠近高点，上影线短
- **做空**: 大阴线，实体饱满，收盘靠近低点，下影线短
- **建议**: Hold（持有）或 Add（加仓）

### 失望 (Disappointment)
- **做多后**: 出现十字星、阴线、或阳线实体很小
- **做空后**: 出现十字星、阳线、或阴线实体很小
- **特征**: K 线实体小，上下影线长，犹豫不决
- **建议**: Tighten Stop（收紧止损）或 Exit at Market（市价离场）

### 弱但可接受 (Weak but Acceptable)
- 方向正确，但力度不强
- **建议**: Hold（持有），保持观察

## 输出格式（JSON）
{{
  "follow_through_quality": "strong" | "weak" | "disappointing",
  "recommendation": "hold" | "exit_market" | "tighten_stop" | "add_position",
  "reasoning": "详细描述 K 线形态和市场反馈...",
  "confidence": 0.0-1.0,
  "key_observations": ["观察1", "观察2", ...]
}}

请基于图表进行分析。"""


def analyze_followthrough(state: dict) -> dict:
    """
    分析 Follow-through 并决定持仓策略
    
    Brooks 原则：只关注入场后的 1-2 根 K 线
    
    Args:
        state: 当前 Agent 状态
        
    Returns:
        更新后的状态
    """
    if state.get("status") != "managing_position":
        return state
    
    entry_bar_index = state.get("entry_bar_index")
    current_bar_index = state.get("current_bar_index")
    
    if entry_bar_index is None or current_bar_index is None:
        return state
    
    # 计算入场后经过了几根 K 线
    bars_since_entry = current_bar_index - entry_bar_index
    
    # Brooks: 只在入场后的 1-2 根 K 线做 Follow-through 检查
    if bars_since_entry > 2:
        logger.debug("Beyond follow-through window (>2 bars). Skipping analysis.")
        return state
    
    if bars_since_entry < 1:
        logger.debug("Still on entry bar. Waiting for next bar.")
        return state
    
    logger.info(f"📊 Analyzing Follow-through: Bar {bars_since_entry} after entry")
    
    # 准备图表数据
    position = state.get("position", {})
    
    # 调用 VL 模型分析（这里先用简化版本）
    analysis = analyze_followthrough_simple(state)
    
    # 根据分析结果采取行动
    if analysis["recommendation"] == "exit_market":
        if analysis["confidence"] > 0.7:
            logger.warning(
                f"⚠️ Disappointing follow-through detected. "
                f"Confidence: {analysis['confidence']:.2f}. Exiting at market."
            )
            
            # 记录退出原因
            state["exit_reason"] = "disappointing_followthrough"
            state["followthrough_analysis"] = analysis
            
            # 实际的平仓操作会在 risk_manager 中处理
            # 这里只更新状态标记
            state["should_exit"] = True
    
    elif analysis["recommendation"] == "tighten_stop":
        logger.info("🔒 Weak follow-through. Tightening stop loss.")
        
        # 计算更紧的止损
        new_stop = calculate_tighter_stop(state)
        if new_stop:
            state["stop_loss"] = new_stop
            state["stop_tightened"] = True
    
    elif analysis["recommendation"] == "add_position":
        if analysis["confidence"] > 0.8:
            logger.info("💪 Strong follow-through! Consider adding position.")
            # 加仓逻辑可以在这里实现
            state["add_signal"] = True
    
    # 保存分析结果
    state["last_followthrough_analysis"] = analysis
    state["followthrough_checked"] = True
    
    return state


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
    if len(bars) < 2:
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
    entry_price = position.get("entry_price")
    current_stop = state.get("stop_loss")
    
    if side == "long":
        # 收紧到当前 K 线低点
        new_stop = current_bar.get("low")
        if new_stop and new_stop > current_stop:
            return new_stop
    else:
        # 收紧到当前 K 线高点
        new_stop = current_bar.get("high")
        if new_stop and new_stop < current_stop:
            return new_stop
    
    return None


def integrate_vl_model_analysis(state: dict, chart_image: bytes) -> dict:
    """
    集成 VL 模型进行 Follow-through 分析
    
    TODO: 实现真实的 VL 模型调用
    
    Args:
        state: 当前状态
        chart_image: 图表截图
        
    Returns:
        VL 模型的分析结果
    """
    # 这里是占位符，实际应该调用 VL 模型
    # 例如使用 Qwen-VL 或 GPT-4V
    
    position = state.get("position", {})
    
    prompt = FOLLOWTHROUGH_PROMPT.format(
        side=position.get("side", "N/A"),
        entry_price=position.get("entry_price", 0),
        entry_bar_index=state.get("entry_bar_index", 0),
        current_bar_index=state.get("current_bar_index", 0),
        stop_loss=state.get("stop_loss", "N/A")
    )
    
    # TODO: 实际的 VL 模型调用
    # response = vl_model.chat(
    #     messages=[
    #         {"role": "user", "content": [
    #             {"type": "text", "text": prompt},
    #             {"type": "image", "image": chart_image}
    #         ]}
    #     ]
    # )
    # 
    # return parse_json(response.message.content)
    
    # 暂时返回简化分析
    return analyze_followthrough_simple(state)
