"""
K线时间管理器 - Candle Timer

提供K线收盘时间对齐和交易所时间同步功能
"""

import time
from datetime import datetime
from typing import Optional
from ..logger import get_logger

logger = get_logger(__name__)


class ExchangeTimeSynchronizer:
    """
    交易所时间同步器
    
    功能:
    - 定期获取交易所服务器时间
    - 计算本地时钟与交易所的偏移量
    - 修正candle timer的时间计算
    """
    
    def __init__(self, exchange, sync_interval_minutes: int = 60):
        """
        Args:
            exchange: ccxt交易所实例
            sync_interval_minutes: 同步间隔（分钟）
        """
        self.exchange = exchange
        self.sync_interval = sync_interval_minutes * 60
        self.time_offset_ms = 0  # 本地时间 - 交易所时间（毫秒）
        self.last_sync_time = 0
        self.sync_count = 0
        
    def sync_time(self) -> dict:
        """
        同步交易所时间
        
        Returns:
            {
                "local_time": datetime,
                "exchange_time": datetime,
                "offset_ms": float,
                "latency_ms": float
            }
        """
        # 发送请求前记录本地时间
        request_start = time.time()
        
        # 获取交易所服务器时间
        # ccxt统一接口: exchange.fetch_time()
        exchange_timestamp_ms = self.exchange.fetch_time()
        
        # 请求完成后记录本地时间
        request_end = time.time()
        
        # 估算网络延迟
        network_latency_ms = (request_end - request_start) * 1000
        
        # 使用请求中点作为本地参考时间
        local_timestamp_ms = ((request_start + request_end) / 2) * 1000
        
        # 计算偏移量（本地 - 交易所）
        self.time_offset_ms = local_timestamp_ms - exchange_timestamp_ms
        self.last_sync_time = time.time()
        self.sync_count += 1
        
        return {
            "local_time": datetime.fromtimestamp(local_timestamp_ms / 1000),
            "exchange_time": datetime.fromtimestamp(exchange_timestamp_ms / 1000),
            "offset_ms": self.time_offset_ms,
            "latency_ms": network_latency_ms
        }
    
    def get_exchange_time(self) -> datetime:
        """
        获取当前的交易所时间（基于偏移量修正）
        
        Returns:
            修正后的交易所时间
        """
        local_now_ms = time.time() * 1000
        exchange_now_ms = local_now_ms - self.time_offset_ms
        return datetime.fromtimestamp(exchange_now_ms / 1000)
    
    def should_sync(self) -> bool:
        """检查是否需要重新同步"""
        elapsed = time.time() - self.last_sync_time
        return elapsed >= self.sync_interval or self.sync_count == 0


class CandleTimer:
    """
    K线时间管理器
    
    功能:
    - 计算下一个K线收盘时间
    - 睡眠到K线收盘前
    - 处理时间同步和边界情况
    """
    
    def __init__(
        self,
        timeframe_minutes: int,
        time_sync: Optional[ExchangeTimeSynchronizer] = None,
        execution_buffer_ms: int = 500
    ):
        """
        Args:
            timeframe_minutes: K线周期（分钟），如 15, 60, 240
            time_sync: 时间同步器（可选）
            execution_buffer_ms: 提前唤醒时间（毫秒），默认500ms
        """
        self.timeframe_minutes = timeframe_minutes
        self.timeframe_seconds = timeframe_minutes * 60
        self.execution_buffer_seconds = execution_buffer_ms / 1000.0
        self.time_sync = time_sync
        
    def get_current_time(self) -> datetime:
        """
        获取当前时间（如果有时间同步器，使用交易所时间）
        """
        if self.time_sync:
            # 定期重新同步
            if self.time_sync.should_sync():
                sync_result = self.time_sync.sync_time()
                logger.info(
                    f"🕐 Time synced with exchange: "
                    f"offset={sync_result['offset_ms']:.0f}ms, "
                    f"latency={sync_result['latency_ms']:.0f}ms"
                )
            return self.time_sync.get_exchange_time()
        else:
            return datetime.now()
    
    def get_next_candle_close(self, current_time: Optional[datetime] = None) -> datetime:
        """
        计算下一个K线收盘时间
        
        算法:
        1. 获取当前时间戳
        2. 向上取整到下一个timeframe边界
        3. 返回对齐后的时间
        
        Example:
            timeframe = 60min
            current = 2025-12-17 14:37:22
            next_close = 2025-12-17 15:00:00
        
        Args:
            current_time: 当前时间，None则自动获取
            
        Returns:
            下一个K线收盘时间
        """
        if current_time is None:
            current_time = self.get_current_time()
        
        # 转换为Unix时间戳（秒）
        current_timestamp = current_time.timestamp()
        
        # 计算下一个K线边界
        # 向上取整: ceil(current / period) * period
        next_close_timestamp = (
            (int(current_timestamp) // self.timeframe_seconds + 1) * self.timeframe_seconds
        )
        
        return datetime.fromtimestamp(next_close_timestamp)
    
    def sleep_until_next_candle(self, extra_sleep: float = 0) -> dict:
        """
        睡眠到下一个K线收盘前
        
        Args:
            extra_sleep: 额外睡眠时间（秒），用于特殊情况
        
        Returns:
            {
                "next_close": datetime,
                "sleep_duration": float,
                "wakeup_time": datetime,
                "latency_ms": float
            }
        """
        now = self.get_current_time()
        next_close = self.get_next_candle_close(now)
        
        # 计算需要睡眠的时间（提前execution_buffer唤醒）
        time_until_close = (next_close - now).total_seconds()
        sleep_duration = max(
            0,
            time_until_close - self.execution_buffer_seconds + extra_sleep
        )
        
        # 睡眠
        if sleep_duration > 0:
            time.sleep(sleep_duration)
        
        wakeup_time = self.get_current_time()
        
        return {
            "next_close": next_close,
            "sleep_duration": sleep_duration,
            "wakeup_time": wakeup_time,
            "latency_ms": (wakeup_time - next_close).total_seconds() * 1000
        }
    
    def wait_until_next_candle(self) -> dict:
        """
        等待到K线收盘，带实时延迟监控
        
        Note: 如果当前时间已经处于执行窗口（buffer内），则自动等待下一个周期，
        避免在处理完成后立即再次触发同一个周期的Tick。
        """
        now = self.get_current_time()
        next_close = self.get_next_candle_close(now)
        
        # 如果距离收盘时间小于 buffer，说明我们刚处理完或者错过了
        # 此时应该等待下一个周期的收盘
        time_until_close = (next_close - now).total_seconds()
        if time_until_close <= self.execution_buffer_seconds:
            logger.debug(f"ℹ️ Already in execution window for {next_close.strftime('%H:%M:%S')}, waiting for next period.")
            next_close = datetime.fromtimestamp(next_close.timestamp() + self.timeframe_seconds)
        
        # 使用指定的 next_close 进行睡眠
        # 重构一部分 sleep_until_next_candle 的逻辑
        time_until_target = (next_close - now).total_seconds()
        sleep_duration = max(
            0,
            time_until_target - self.execution_buffer_seconds
        )
        
        if sleep_duration > 0:
            time.sleep(sleep_duration)
            
        wakeup_time = self.get_current_time()
        latency_ms = (wakeup_time - next_close).total_seconds() * 1000
        
        result = {
            "next_close": next_close,
            "sleep_duration": sleep_duration,
            "wakeup_time": wakeup_time,
            "latency_ms": latency_ms
        }
        
        # 如果延迟过大，记录警告
        abs_latency = abs(latency_ms)
        if abs_latency > 2000:  # 超过2秒
            logger.warning(
                f"⚠️  High latency: {abs_latency:.0f}ms "
                f"(expected close: {result['next_close'].strftime('%H:%M:%S')}, "
                f"actual wakeup: {result['wakeup_time'].strftime('%H:%M:%S')})"
            )
        
        return result


def parse_timeframe_to_minutes(timeframe: str) -> int:
    """
    将timeframe字符串解析为分钟数
    
    支持格式:
    - "15m" -> 15
    - "1h"  -> 60
    - "4h"  -> 240
    - "1d"  -> 1440
    
    Args:
        timeframe: 时间周期字符串
    
    Returns:
        分钟数
    
    Raises:
        ValueError: 不支持的格式
    """
    timeframe = timeframe.lower().strip()
    
    if timeframe.endswith('m'):
        return int(timeframe[:-1])
    elif timeframe.endswith('h'):
        return int(timeframe[:-1]) * 60
    elif timeframe.endswith('d'):
        return int(timeframe[:-1]) * 1440
    elif timeframe.endswith('w'):
        return int(timeframe[:-1]) * 10080
    else:
        raise ValueError(
            f"Unsupported timeframe format: {timeframe}. "
            f"Expected format: '15m', '1h', '4h', '1d', etc."
        )
