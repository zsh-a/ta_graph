"""
L1 Screener Node - Low-Cost Text Model Screening

使用低成本文本模型（qwen-turbo）进行初步筛选和状态更新。
只在 L0 预处理器检测到正常波动时触发。
"""

import json
from datetime import datetime, timezone
from langfuse import observe

from ..state import TradingState
from ..logger import get_logger
from ..models.market_state import MarketStateSnapshot, L1ScreenerResponse
from ..utils.model_manager import get_l1_model
from ..utils.event_bus import get_event_bus
from ..utils.error_handler import with_error_handling
from ..utils.timeout_decorator import with_timeout

logger = get_logger(__name__)
bus = get_event_bus()


# ==================== Prompt Template ====================

L1_SYSTEM_PROMPT = """You are an Al Brooks Price Action analyst. Your job is to:
1. Update the market state based on new bar data
2. Detect potential trading setups (H1, H2, L1, L2, Wedge, MTR, etc.)

You receive the PREVIOUS market state and NEW bar data (in Brooks notation).
Output a structured JSON assessment.

Key Concepts:
- Always In Direction: Who controls the market right now (bulls, bears, or unclear)
- Market Phase: strong_bull_trend, weak_bull_trend, strong_bear_trend, weak_bear_trend, trading_range, breakout, climax
- Setup Types: H1/H2 (Higher High breakout), L1/L2 (Lower Low breakout), Wedge, MTR (Major Trend Reversal)

Rules:
- Only signal a setup if the pattern is clear
- Be conservative - when in doubt, report no setup
- Your notes should briefly explain your reasoning
"""


def get_l1_prompt(
    prev_state: dict | None,
    brooks_notation: str,
    market_context: dict | None
) -> str:
    """
    构建 L1 模型的 prompt
    """
    state_str = json.dumps(prev_state, indent=2) if prev_state else "None (first run)"
    context_str = ""
    if market_context:
        context_str = f"""
Market Context (L0):
- ATR: {market_context.get('atr_14', 'N/A')} ({market_context.get('atr_pct', 'N/A')}%)
- EMA20: {market_context.get('ema20', 'N/A')}
- Price Position in Range: {market_context.get('price_position_in_range', 'N/A')} (0 = low, 1 = high)
"""
    
    return f"""## Previous Market State
{state_str}

## New Bar Data (Brooks Notation)
{brooks_notation}
{context_str}
## Task
1. Based on the new bar, update the market state
2. Identify if there's a potential trading setup
3. Provide brief reasoning

Respond with JSON matching this schema:
{{
    "updated_state": {{
        "timestamp": "ISO timestamp",
        "always_in_direction": "long" | "short" | "unclear",
        "market_phase": "strong_bull_trend" | "weak_bull_trend" | "strong_bear_trend" | "weak_bear_trend" | "trading_range" | "breakout" | "climax",
        "recent_pattern": "pattern name or null",
        "key_levels": {{"support": float, "resistance": float}},
        "notes": "brief reasoning"
    }},
    "setup_detected": true | false,
    "setup_type": "H1_buy" | "H2_buy" | "L1_sell" | "L2_sell" | "Wedge_top" | "Wedge_bottom" | null,
    "reasoning": "why you do or don't see a setup",
    "confidence": "high" | "medium" | "low"
}}
"""


# ==================== Fallback Function ====================

def l1_fallback(state: TradingState) -> dict:
    """
    L1 筛选超时或失败时的回退函数
    """
    logger.warning("⚠️ L1 fallback triggered - proceeding without L1 analysis")
    return {
        "l1_setup_detected": False,
        "l1_reasoning": "L1 analysis skipped (fallback)",
        "warnings": (state.get("warnings") or []) + ["L1 analysis was skipped"]
    }


# ==================== Node Function ====================

@observe()
@with_timeout(timeout_seconds=60, fallback_fn=l1_fallback, operation_name="L1 Screening")
@with_error_handling(max_retries=1, fallback_fn=l1_fallback)
def l1_screen(state: TradingState) -> dict:
    """
    L1 文本模型筛选节点
    
    输入要求:
    - brooks_notation: L0 预处理器生成的 K 线简记法
    - bar_features: L0 预处理器生成的特征列表
    - market_context: L0 预处理器生成的市场上下文
    
    输出:
    - l1_market_state: 更新后的市场状态快照
    - l1_setup_detected: 是否检测到 setup
    - l1_setup_type: setup 类型
    - l1_reasoning: 推理过程
    """
    logger.info("🔍 L1 Screener: Starting text model analysis...")
    bus.emit_sync("node_start", {"node": "l1_screener"})
    
    # 1. 读取输入
    brooks_notation = state.get("brooks_notation", "")
    market_context = state.get("market_context")
    prev_state = state.get("l1_market_state")
    
    if not brooks_notation:
        logger.warning("⚠️ No brooks_notation available, skipping L1 screening")
        return {
            "l1_setup_detected": False,
            "l1_reasoning": "No bar data available"
        }
    
    # 2. 构建 prompt
    user_prompt = get_l1_prompt(prev_state, brooks_notation, market_context)
    
    # 3. 调用 L1 模型
    try:
        llm = get_l1_model()
        
        # 尝试使用结构化输出
        try:
            structured_llm = llm.with_structured_output(L1ScreenerResponse)
            response: L1ScreenerResponse = structured_llm.invoke([
                {"role": "system", "content": L1_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ])
        except Exception as struct_err:
            # 降级：手动解析 JSON
            logger.warning(f"⚠️ Structured output failed, falling back to manual parsing: {struct_err}")
            raw_response = llm.invoke([
                {"role": "system", "content": L1_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ])
            
            # 解析 JSON
            content = raw_response.content
            if isinstance(content, str):
                # 提取 JSON
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = content[json_start:json_end]
                    parsed = json.loads(json_str)
                    response = L1ScreenerResponse(**parsed)
                else:
                    raise ValueError("No JSON found in response")
            else:
                raise ValueError(f"Unexpected response type: {type(content)}")
        
        # 4. 处理结果
        setup_detected = response.setup_detected
        setup_type = response.setup_type
        confidence = response.confidence
        
        # 更新状态快照
        updated_state = response.updated_state
        if updated_state:
            updated_state.timestamp = datetime.now(timezone.utc).isoformat()
        
        # 发送 LLM 日志事件到前端 (与 brooks_analyzer 保持一致)
        bus.emit_sync("llm_log", {
            "node": "l1_screener",
            "model": "L1 Text Model (qwen-turbo)",
            "prompt": f"[System] {L1_SYSTEM_PROMPT[:100]}...\n\n[User] {user_prompt[:500]}...",
            "response": json.dumps(response.model_dump(), indent=2, ensure_ascii=False) if hasattr(response, 'model_dump') else str(response),
            "reasoning": response.reasoning
        })
        
        # 发送事件到前端
        bus.emit_sync("l1_screening_complete", {
            "node": "l1_screener",
            "setup_detected": setup_detected,
            "setup_type": setup_type,
            "market_phase": updated_state.market_phase if updated_state else None,
            "always_in": updated_state.always_in_direction if updated_state else None,
            "confidence": confidence,
            "reasoning": response.reasoning,
            "next_step": "brooks_analyzer" if response.should_escalate_to_l2() else "strategy"
        })
        
        if setup_detected:
            logger.info(f"✅ L1 detected setup: {setup_type} (confidence: {confidence})")
        else:
            logger.info(f"📊 L1: No setup detected. Phase: {updated_state.market_phase if updated_state else 'unknown'}")
        
        return {
            "l1_market_state": updated_state.model_dump() if updated_state else None,
            "l1_setup_detected": setup_detected,
            "l1_setup_type": setup_type,
            "l1_reasoning": response.reasoning,
            "l1_confidence": confidence
        }
        
    except Exception as e:
        logger.error(f"❌ L1 Screener failed: {e}")
        
        # 发送错误事件
        bus.emit_sync("l1_screening_error", {
            "node": "l1_screener",
            "error": str(e)
        })
        
        # 安全回退：不检测 setup，但不阻塞流程
        return {
            "l1_setup_detected": False,
            "l1_reasoning": f"L1 screening failed: {e}",
            "errors": state.get("errors", []) + [f"L1 screening error: {e}"]
        }
