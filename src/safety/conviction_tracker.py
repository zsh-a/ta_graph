"""
信念追踪器 - Conviction Tracker

防止 AI 幻觉导致的频繁交易
"""

from typing import Literal
from collections import deque
from ..logger import get_logger

logger = get_logger(__name__)


class ConvictionTracker:
    """
    信念分追踪器
    
    Brooks 惯性原则：
    只有当连续多个信号一致时才行动，防止因噪音而频繁交易
    """
    
    def __init__(self, history_size: int = 3, min_consecutive: int = 2):
        """
        初始化信念追踪器
        
        Args:
            history_size: 保存的历史信号数量
            min_consecutive: 需要连续一致的信号数量
        """
        self.history_size = history_size
        self.min_consecutive = min_consecutive
        self.recent_signals = deque(maxlen=history_size)
    
    def add_signal(
        self,
        action: Literal["buy", "sell", "hold", "exit", "reverse"],
        confidence: float,
        reasoning: str = ""
    ):
        """
        添加新信号
        
        Args:
            action: 建议的操作
            confidence: 置信度 (0.0-1.0)
            reasoning: 推理依据
        """
        signal = {
            "action": action,
            "confidence": confidence,
            "reasoning": reasoning
        }
        
        self.recent_signals.append(signal)
        logger.debug(f"Signal added: {action} (confidence: {confidence:.2f})")
    
    def evaluate_conviction(self, required_action: str | None = None) -> bool:
        """
        评估信念强度
        
        Args:
            required_action: 需要评估的特定操作（可选）
            
        Returns:
            True 如果信念足够强，False 否则
        """
        if len(self.recent_signals) < self.min_consecutive:
            logger.debug(
                f"Not enough signals: {len(self.recent_signals)}/{self.min_consecutive}"
            )
            return False
        
        # 获取最近的 N 个信号
        recent = list(self.recent_signals)[-self.min_consecutive:]
        
        # 检查一致性
        actions = [s["action"] for s in recent]
        confidences = [s["confidence"] for s in recent]
        
        # 如果指定了特定操作，检查是否匹配
        if required_action:
            if not all(a == required_action for a in actions):
                logger.debug(f"Actions not consistent for {required_action}: {actions}")
                return False
        else:
            # 检查所有信号是否一致
            if len(set(actions)) != 1:
                logger.debug(f"Mixed actions: {actions}")
                return False
        
        # 检查置信度
        min_confidence = 0.7
        if not all(c >= min_confidence for c in confidences):
            logger.debug(
                f"Confidence too low: {confidences} (require >= {min_confidence})"
            )
            return False
        
        logger.info(
            f"✅ Conviction confirmed: {actions[0]} "
            f"(consecutive: {len(recent)}, avg confidence: {sum(confidences)/len(confidences):.2f})"
        )
        return True
    
    def clear(self):
        """清空历史信号"""
        self.recent_signals.clear()
        logger.debug("Signal history cleared")
    
    def get_latest_signal(self) -> dict | None:
        """获取最新信号"""
        if self.recent_signals:
            return self.recent_signals[-1]
        return None


def check_hallucination_guard(state: dict, decision: dict) -> bool:
    """
    幻觉防护检查
    
    防止因 VL 模型幻觉导致的错误操作
    
    Args:
        state: 当前状态
        decision: AI 的决策
        
    Returns:
        True 如果允许操作，False 如果应该阻止
    """
    action = decision.get("action")
    
    # Rule 1: 不允许在 TTR（窄幅震荡）中频繁开仓
    if is_tight_trading_range(state):
        if action in ["buy", "sell"]:
            logger.warning("🛑 Blocked: No trading in Tight Trading Range")
            return False
    
    # Rule 2: 禁止无理由反手
    if state.get("status") == "managing_position":
        current_side = state.get("position", {}).get("side")
        
        if action == "reverse":
            # 需要极强的反转信号
            reversal_strength = decision.get("reversal_strength", "weak")
            if reversal_strength != "very_strong":
                logger.warning(
                    f"🛑 Blocked: Reversal signal not strong enough ({reversal_strength})"
                )
                return False
        
        # 防止做多后立即做空（或反之）
        if (current_side == "long" and action == "sell") or \
           (current_side == "short" and action == "buy"):
            logger.warning("🛑 Blocked: Cannot reverse without explicit reversal signal")
            return False
    
    # Rule 3: 使用 Conviction Tracker
    tracker = state.get("conviction_tracker")
    if tracker:
        if not tracker.evaluate_conviction(action):
            logger.info("⏳ Waiting for conviction. Signal ignored.")
            return False
    
    # 通过所有检查
    return True


def is_tight_trading_range(state: dict) -> bool:
    """
    检测是否在窄幅震荡（TTR）中
    
    Brooks 定义：至少 20 根 K 线，每根 K 线高低点重叠，且没有明显方向性
    
    改进：区分趋势市场和震荡市场
    - 趋势市场：价格有明显方向性移动
    - TTR：价格在窄幅范围内来回波动
    
    Args:
        state: 当前状态
        
    Returns:
        True 如果在 TTR 中
    """
    bars = state.get("bars", [])
    
    if len(bars) < 20:
        return False
    
    recent_bars = bars[-20:]
    
    # 计算整体波动范围
    overall_high = max(bar.get("high", 0) for bar in recent_bars)
    overall_low = min(bar.get("low", 0) for bar in recent_bars)
    overall_range = overall_high - overall_low
    
    if overall_range == 0:
        return True
    
    # 1. 检查价格方向性（趋势检测）
    closes = [bar.get("close", 0) for bar in recent_bars]
    first_close = closes[0]
    last_close = closes[-1]
    
    # 计算价格变化百分比
    if first_close > 0:
        price_change_pct = abs(last_close - first_close) / first_close * 100
        
        # 如果价格有明显移动（上涨或下跌超过2%），则不是TTR
        if price_change_pct > 2.0:
            logger.debug(f"Not TTR: Price moved {price_change_pct:.2f}% (trending market)")
            return False
    
    # 2. 检查趋势连续性（连续相同方向的K线）
    bullish_count = sum(1 for bar in recent_bars if bar.get("close", 0) > bar.get("open", 0))
    bearish_count = sum(1 for bar in recent_bars if bar.get("close", 0) < bar.get("open", 0))
    
    # 如果超过70%的K线方向一致，且价格确实有移动(>0.5%)，说明是趋势
    # 如果方向一致但价格没动，不算趋势（比如所有K线都是小阳线但在同一水平）
    if first_close > 0:
        price_change_pct_directional = abs(last_close - first_close) / first_close * 100
        if (bullish_count > 14 or bearish_count > 14) and price_change_pct_directional > 0.5:
            logger.debug(f"Not TTR: Directional bias detected (bull:{bullish_count}, bear:{bearish_count}) with price movement")
            return False
    
    # 3. 计算平均 K 线实体大小相对于整体范围
    avg_body = sum(
        abs(bar.get("close", 0) - bar.get("open", 0))
        for bar in recent_bars
    ) / len(recent_bars)
    
    body_to_range_ratio = avg_body / overall_range
    
    # TTR 特征：小实体相对于整体范围
    # 如果实体很小（<=25%的范围），很可能是TTR
    if body_to_range_ratio <= 0.25:
        logger.debug(f"TTR detected: Small bodies ({body_to_range_ratio:.2%}) relative to range")
        return True
    
    # 4. 检查波动范围相对于价格
    if first_close > 0:
        range_to_price_ratio = overall_range / first_close * 100
        
        # 如果波动范围相对于价格很小（<=0.25%），一定是TTR
        # 或者如果实体已经很小并且range也不大（<1%），也算TTR
        if range_to_price_ratio <= 0.25 or (body_to_range_ratio <= 0.3 and range_to_price_ratio < 1.0):
            logger.debug(f"TTR detected: Narrow range ({range_to_price_ratio:.2f}%) relative to price")
            return True
    
    return False




