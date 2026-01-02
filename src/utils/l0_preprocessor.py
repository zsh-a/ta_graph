"""
L0 Preprocessor - Pure Python Feature Extraction

Al Brooks 风格的 K 线特征提取，零 API 成本。
实现"能用代码解决的不用模型"原则。
"""

from dataclasses import dataclass, asdict
from typing import Literal, Any
import pandas as pd
import numpy as np
from ..logger import get_logger

logger = get_logger(__name__)


# ==================== Data Models ====================

@dataclass
class BarFeatures:
    """
    单根 K 线的 Al Brooks 特征编码
    """
    # 基础特征
    bar_index: int  # 相对索引 (0 = 当前, -1 = 前一根)
    bar_type: Literal["bull_trend", "bear_trend", "bull_doji", "bear_doji"]
    body_pct: int  # 实体占比 0-100
    
    # 收盘位置
    close_position: Literal["high", "mid", "low"]
    
    # EMA 关系
    ema_relation: Literal["above", "at", "below"]
    ema_distance_pct: float  # 与 EMA 的距离百分比
    
    # Brooks 计数
    h_count: int  # H1/H2 计数
    l_count: int  # L1/L2 计数
    
    # 特殊形态
    is_inside_bar: bool
    is_outside_bar: bool
    is_reversal_bar: bool  # 反转K线 (长影线)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MarketContext:
    """
    市场整体上下文 (L0 计算)
    """
    atr_14: float
    atr_pct: float  # ATR 相对于价格的百分比
    is_dead_market: bool  # 死鱼盘（低波动）
    ema20: float
    recent_high: float  # 近期高点
    recent_low: float   # 近期低点
    price_position_in_range: float  # 0-1, 价格在近期区间中的位置
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ==================== Core Functions ====================

def classify_bar_type(open_p: float, high: float, low: float, close: float) -> tuple[str, int]:
    """
    分类 K 线类型
    
    Returns:
        (bar_type, body_pct)
    """
    range_size = high - low
    body_size = abs(close - open_p)
    
    if range_size == 0:
        body_pct = 0
    else:
        body_pct = int((body_size / range_size) * 100)
    
    is_bull = close >= open_p
    is_trend = body_pct > 50
    
    if is_bull:
        bar_type = "bull_trend" if is_trend else "bull_doji"
    else:
        bar_type = "bear_trend" if is_trend else "bear_doji"
    
    return bar_type, body_pct


def classify_close_position(open_p: float, high: float, low: float, close: float) -> Literal["high", "mid", "low"]:
    """
    判断收盘价在 K 线中的位置
    """
    range_size = high - low
    if range_size == 0:
        return "mid"
    
    position = (close - low) / range_size
    
    if position >= 0.67:
        return "high"
    elif position <= 0.33:
        return "low"
    else:
        return "mid"


def classify_ema_relation(close: float, ema: float, atr: float) -> tuple[Literal["above", "at", "below"], float]:
    """
    判断与 EMA 的关系
    
    Returns:
        (relation, distance_pct)
    """
    if atr == 0:
        return "at", 0.0
    
    distance = close - ema
    distance_pct = (distance / atr) * 100
    
    # 在 0.5 ATR 内视为"接触"
    if abs(distance_pct) <= 50:
        return "at", distance_pct
    elif distance > 0:
        return "above", distance_pct
    else:
        return "below", distance_pct


def detect_bar_patterns(
    curr_open: float, curr_high: float, curr_low: float, curr_close: float,
    prev_high: float, prev_low: float
) -> tuple[bool, bool, bool]:
    """
    检测特殊形态
    
    Returns:
        (is_inside_bar, is_outside_bar, is_reversal_bar)
    """
    # Inside bar: 完全在前一根范围内
    is_inside = curr_high <= prev_high and curr_low >= prev_low
    
    # Outside bar: 完全包含前一根
    is_outside = curr_high > prev_high and curr_low < prev_low
    
    # Reversal bar: 有明显的拒绝尾巴 (影线占 > 40%)
    range_size = curr_high - curr_low
    body_size = abs(curr_close - curr_open)
    if range_size > 0:
        tail_pct = ((range_size - body_size) / range_size) * 100
        is_reversal = tail_pct > 40
    else:
        is_reversal = False
    
    return is_inside, is_outside, is_reversal


def calculate_atr(bars: list[dict[str, Any]], period: int = 14) -> float:
    """
    计算 ATR (Average True Range) using TA-Lib
    """
    if len(bars) < 2:
        return 0.0
    
    import talib
    
    # Convert bars to numpy arrays
    high = np.array([b["high"] for b in bars], dtype=np.float64)
    low = np.array([b["low"] for b in bars], dtype=np.float64)
    close = np.array([b["close"] for b in bars], dtype=np.float64)
    
    # Calculate ATR using TA-Lib (uses proper Wilder's smoothing)
    atr_values = talib.ATR(high, low, close, timeperiod=min(period, len(bars) - 1))
    
    # Get last non-NaN value
    valid_values = atr_values[~np.isnan(atr_values)]
    if len(valid_values) == 0:
        # Fallback to simple range average
        ranges = [b["high"] - b["low"] for b in bars[-period:]]
        return float(sum(ranges) / len(ranges)) if ranges else 0.0
    
    return float(valid_values[-1])


def calculate_ema(closes: list[float], period: int = 20) -> list[float]:
    """
    计算 EMA (Exponential Moving Average) using TA-Lib
    """
    if not closes:
        return []
    
    import talib
    
    close_array = np.array(closes, dtype=np.float64)
    ema_values = talib.EMA(close_array, timeperiod=min(period, len(closes)))
    
    # Replace NaN with original closes for initial values, convert to native float
    result = []
    for i, v in enumerate(ema_values):
        if np.isnan(v):
            result.append(float(closes[i]))
        else:
            result.append(float(v))
    
    return result


# ==================== Main Preprocessor ====================

class L0Preprocessor:
    """
    L0 预处理器 - 纯 Python 特征提取
    """
    
    def __init__(self, dead_market_threshold: float = 0.3):
        """
        Args:
            dead_market_threshold: ATR 百分比阈值，低于此值视为死鱼盘
        """
        self.dead_market_threshold = dead_market_threshold
        self._h_counter = 0
        self._l_counter = 0
    
    def extract_bar_features(
        self,
        bar: dict[str, Any],
        prev_bar: dict[str, Any] | None,
        ema20: float,
        atr: float,
        bar_index: int = 0
    ) -> BarFeatures:
        """
        提取单根 K 线的特征
        """
        open_p = bar["open"]
        high = bar["high"]
        low = bar["low"]
        close = bar["close"]
        
        # 基础分类
        bar_type, body_pct = classify_bar_type(open_p, high, low, close)
        close_position = classify_close_position(open_p, high, low, close)
        ema_relation, ema_distance_pct = classify_ema_relation(close, ema20, atr)
        
        # 特殊形态
        if prev_bar:
            is_inside, is_outside, is_reversal = detect_bar_patterns(
                open_p, high, low, close, prev_bar["high"], prev_bar["low"]
            )
            
            # H/L 计数更新
            if high > prev_bar["high"]:
                self._h_counter += 1
            elif "bear" in bar_type and body_pct > 60:
                self._h_counter = 0  # 重置
            
            if low < prev_bar["low"]:
                self._l_counter += 1
            elif "bull" in bar_type and body_pct > 60:
                self._l_counter = 0  # 重置
        else:
            is_inside, is_outside, is_reversal = False, False, False
        
        return BarFeatures(
            bar_index=bar_index,
            bar_type=bar_type,
            body_pct=body_pct,
            close_position=close_position,
            ema_relation=ema_relation,
            ema_distance_pct=round(ema_distance_pct, 1),
            h_count=self._h_counter,
            l_count=self._l_counter,
            is_inside_bar=is_inside,
            is_outside_bar=is_outside,
            is_reversal_bar=is_reversal
        )
    
    def process_bars(
        self,
        bars: list[dict[str, Any]],
        ema_values: list[float] | None = None
    ) -> list[BarFeatures]:
        """
        批量处理 K 线，提取特征
        """
        if not bars:
            return []
        
        # 计算 ATR using TA-Lib
        atr = calculate_atr(bars)
        
        # 如果没有 EMA，使用 TA-Lib 计算
        if ema_values is None or len(ema_values) == 0:
            closes = [float(b["close"]) for b in bars]
            ema_values = calculate_ema(closes, period=20)
        
        # 重置计数器
        self._h_counter = 0
        self._l_counter = 0
        
        features = []
        num_bars = len(bars)
        
        for i, bar in enumerate(bars):
            prev_bar = bars[i - 1] if i > 0 else None
            ema = ema_values[i] if i < len(ema_values) else ema_values[-1]
            bar_index = i - num_bars + 1  # 最后一根为 0，倒数第二为 -1
            
            feature = self.extract_bar_features(bar, prev_bar, ema, atr, bar_index)
            features.append(feature)
        
        return features
    
    def encode_to_brooks_notation(self, feature: BarFeatures) -> str:
        """
        将特征编码为 Al Brooks 简记法
        
        例如: "Bull Trend, Cl High, EMA+5.2%, H2"
        """
        parts = []
        
        # 1. 类型
        type_map = {
            "bull_trend": "Bull Trend",
            "bear_trend": "Bear Trend",
            "bull_doji": "Bull Doji",
            "bear_doji": "Bear Doji"
        }
        parts.append(type_map.get(feature.bar_type, feature.bar_type))
        
        # 2. 收盘位置
        parts.append(f"Cl {feature.close_position.title()}")
        
        # 3. EMA 关系
        if feature.ema_relation == "above":
            parts.append(f"EMA+{abs(feature.ema_distance_pct):.1f}%")
        elif feature.ema_relation == "below":
            parts.append(f"EMA-{abs(feature.ema_distance_pct):.1f}%")
        else:
            parts.append("EMA@")
        
        # 4. H/L 计数
        if feature.h_count > 0:
            parts.append(f"H{feature.h_count}")
        if feature.l_count > 0:
            parts.append(f"L{feature.l_count}")
        
        # 5. 特殊形态
        if feature.is_inside_bar:
            parts.append("IB")
        if feature.is_outside_bar:
            parts.append("OB")
        if feature.is_reversal_bar:
            parts.append("Rev")
        
        return ", ".join(parts)
    
    def encode_recent_bars(
        self,
        features: list[BarFeatures],
        count: int = 5
    ) -> str:
        """
        编码最近几根 K 线的简记法
        """
        recent = features[-count:] if len(features) >= count else features
        lines = []
        
        for f in recent:
            notation = self.encode_to_brooks_notation(f)
            lines.append(f"Bar {f.bar_index}: {notation}")
        
        return "\n".join(lines)
    
    def get_market_context(
        self,
        bars: list[dict[str, Any]],
        ema20: float | None = None
    ) -> MarketContext:
        """
        获取市场整体上下文
        """
        if not bars:
            return MarketContext(
                atr_14=0.0, atr_pct=0.0, is_dead_market=True,
                ema20=0.0, recent_high=0.0, recent_low=0.0, price_position_in_range=0.5
            )
        
        atr = calculate_atr(bars)
        current_price = bars[-1]["close"]
        atr_pct = (atr / current_price * 100) if current_price > 0 else 0
        
        # 死鱼盘检测
        is_dead_market = atr_pct < self.dead_market_threshold
        
        # EMA20
        if ema20 is None:
            closes = [b["close"] for b in bars]
            ema20_val = pd.Series(closes).ewm(span=20, adjust=False).mean().iloc[-1]
            # Convert numpy.float64 to native Python float
            ema20 = float(ema20_val)
        
        # 近期区间 (20 bars)
        recent_bars = bars[-20:]
        recent_high = max(b["high"] for b in recent_bars)
        recent_low = min(b["low"] for b in recent_bars)
        
        range_size = recent_high - recent_low
        if range_size > 0:
            price_position = (current_price - recent_low) / range_size
        else:
            price_position = 0.5
        
        # Ensure all values are native Python types (not numpy)
        return MarketContext(
            atr_14=float(round(atr, 4)),
            atr_pct=float(round(atr_pct, 2)),
            is_dead_market=bool(is_dead_market),
            ema20=float(round(ema20, 4)),
            recent_high=float(round(recent_high, 4)),
            recent_low=float(round(recent_low, 4)),
            price_position_in_range=float(round(price_position, 2))
        )
    
    def check_volatility_gate(
        self,
        bars: list[dict[str, Any]],
        threshold_pct: float | None = None
    ) -> bool:
        """
        波动率门控 - 检测是否应该跳过 AI 调用
        
        Returns:
            True 如果是死鱼盘（低波动），应该跳过
        """
        threshold = threshold_pct or self.dead_market_threshold
        context = self.get_market_context(bars)
        
        if context.is_dead_market:
            logger.info(f"🐟 Dead market detected: ATR {context.atr_pct:.2f}% < threshold {threshold:.2f}%")
        
        return context.is_dead_market


# ==================== Convenience Functions ====================

def extract_bar_features(
    bar: dict[str, Any],
    prev_bar: dict[str, Any] | None,
    ema20: float,
    atr: float
) -> BarFeatures:
    """
    便捷函数：提取单根 K 线特征
    """
    preprocessor = L0Preprocessor()
    return preprocessor.extract_bar_features(bar, prev_bar, ema20, atr)


def encode_bars_to_text(
    bars: list[dict[str, Any]],
    ema_values: list[float] | None = None,
    count: int = 5
) -> str:
    """
    便捷函数：将 K 线编码为 Brooks 简记法文本
    """
    preprocessor = L0Preprocessor()
    features = preprocessor.process_bars(bars, ema_values)
    return preprocessor.encode_recent_bars(features, count)


def is_dead_market(bars: list[dict[str, Any]], threshold_pct: float = 0.3) -> bool:
    """
    便捷函数：检测死鱼盘
    """
    preprocessor = L0Preprocessor(dead_market_threshold=threshold_pct)
    return preprocessor.check_volatility_gate(bars)
