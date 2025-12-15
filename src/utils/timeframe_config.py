"""
Timeframe Configuration Manager
统一的时间周期配置管理
"""

import os
from typing import Optional, Literal
from dotenv import load_dotenv

load_dotenv()

# 支持的时间周期
TimeframeType = Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w"]

class TimeframeConfig:
    """时间周期配置类"""
    
    # 时间周期名称映射（用于显示）
    TIMEFRAME_LABELS = {
        "1m": "1分钟",
        "3m": "3分钟", 
        "5m": "5分钟",
        "15m": "15分钟",
        "30m": "30分钟",
        "1h": "1小时",
        "2h": "2小时",
        "4h": "4小时",
        "6h": "6小时",
        "12h": "12小时",
        "1d": "1日",
        "1w": "1周"
    }
    
    # 时间周期对应的K线数量建议
    TIMEFRAME_LIMITS = {
        "1m": 500,   # 1分钟：约8小时
        "3m": 400,   # 3分钟：约20小时
        "5m": 300,   # 5分钟：约25小时
        "15m": 200,  # 15分钟：约2天
        "30m": 150,  # 30分钟：约3天
        "1h": 150,   # 1小时：约6天
        "2h": 150,   # 2小时：约12天
        "4h": 150,   # 4小时：约25天
        "6h": 120,   # 6小时：约1个月
        "12h": 100,  # 12小时：约2个月
        "1d": 200,   # 1日：约6个月
        "1w": 100    # 1周：约2年
    }
    
    def __init__(self, primary: TimeframeType = "1h"):
        self.primary = primary
        
    @classmethod
    def from_env(cls) -> "TimeframeConfig":
        """从环境变量加载配置"""
        primary = os.getenv("PRIMARY_TIMEFRAME", "1h")
        
        # 验证timeframe是否支持
        if primary not in cls.TIMEFRAME_LABELS:
            print(f"⚠️ Warning: Unsupported timeframe '{primary}', using default '1h'")
            primary = "1h"
            
        return cls(primary=primary)
    
    def get_label(self) -> str:
        """获取时间周期的中文标签"""
        return self.TIMEFRAME_LABELS.get(self.primary, self.primary)
    
    def get_limit(self) -> int:
        """获取建议的K线数量"""
        return self.TIMEFRAME_LIMITS.get(self.primary, 150)
    
    def get_chart_bars(self) -> int:
        """获取图表显示的K线数量（通常是limit的全部或一部分）"""
        return self.get_limit()
    
    def to_dict(self):
        """转换为字典"""
        return {
            "primary": self.primary,
            "label": self.get_label(),
            "limit": self.get_limit(),
            "chart_bars": self.get_chart_bars()
        }
    
    def display(self):
        """显示配置信息"""
        print(f"\n=== Timeframe Configuration ===")
        print(f"Primary: {self.primary} ({self.get_label()})")
        print(f"Data Limit: {self.get_limit()} bars")
        print(f"Chart Bars: {self.get_chart_bars()} bars")
        print(f"================================\n")


class TimeframeManager:
    """时间周期管理器"""
    
    def __init__(self, config: Optional[TimeframeConfig] = None):
        self.config = config or TimeframeConfig.from_env()
    
    def get_config(self) -> TimeframeConfig:
        """获取当前配置"""
        return self.config
    
    def get_primary(self) -> str:
        """获取主时间周期"""
        return self.config.primary
    
    def get_limit(self) -> int:
        """获取数据量"""
        return self.config.get_limit()
    
    def set_timeframe(self, timeframe: TimeframeType):
        """设置时间周期"""
        self.config = TimeframeConfig(primary=timeframe)
        print(f"✓ Timeframe set to: {timeframe} ({self.config.get_label()})")
    
    def display_config(self):
        """显示配置"""
        self.config.display()


# 全局单例
_timeframe_manager: Optional[TimeframeManager] = None

def get_timeframe_manager() -> TimeframeManager:
    """获取全局时间周期管理器"""
    global _timeframe_manager
    if _timeframe_manager is None:
        _timeframe_manager = TimeframeManager()
    return _timeframe_manager

def get_primary_timeframe() -> str:
    """快捷函数：获取主时间周期"""
    return get_timeframe_manager().get_primary()

def get_data_limit() -> int:
    """快捷函数：获取数据量限制"""
    return get_timeframe_manager().get_limit()
