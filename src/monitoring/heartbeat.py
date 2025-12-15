"""
心跳监控 - Heartbeat Monitor

确保系统持续运行，检测死锁和冻结
"""

import threading
import time
from datetime import datetime
from ..logger import get_logger
from ..notification.alerts import send_alert

logger = get_logger(__name__)


class HeartbeatMonitor:
    """
    心跳监控器
    
    定期检查系统是否还在运行
    如果长时间没有心跳，发送警报
    """
    
    def __init__(self, interval_seconds: int = 60, timeout_seconds: int = 300):
        """
        初始化心跳监控器
        
        Args:
            interval_seconds: 检查间隔（秒）
            timeout_seconds: 超时时间（秒）无心跳则报警
        """
        self.interval = interval_seconds
        self.timeout = timeout_seconds
        self.last_heartbeat = time.time()
        self.running = False
        self.thread = None
        self.heartbeat_count = 0
    
    def start(self):
        """启动心跳监控"""
        if self.running:
            logger.warning("Heartbeat monitor already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("💓 Heartbeat monitor started")
    
    def beat(self):
        """记录一次心跳"""
        self.last_heartbeat = time.time()
        self.heartbeat_count += 1
        
        if self.heartbeat_count % 10 == 0:
            logger.debug(f"💓 Heartbeat #{self.heartbeat_count}")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            time.sleep(self.interval)
            
            elapsed = time.time() - self.last_heartbeat
            
            if elapsed > self.timeout:
                logger.critical(
                    f"🔴 No heartbeat for {elapsed:.0f}s (timeout: {self.timeout}s). "
                    f"System may be frozen!"
                )
                
                send_alert(
                    title="Heartbeat Lost - System May Be Frozen",
                    message=f"""
Last heartbeat: {datetime.fromtimestamp(self.last_heartbeat).strftime('%Y-%m-%d %H:%M:%S')}
Elapsed time: {elapsed:.0f} seconds
Timeout threshold: {self.timeout} seconds

Possible issues:
- Network connection lost
- Process deadlock
- API rate limit hit
- System crash

Please check the system status immediately.
                    """,
                    severity="critical"
                )
                
                # 可选：尝试重启系统
                # self._attempt_recovery()
    
    def stop(self):
        """停止监控"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Heartbeat monitor stopped")
    
    def get_status(self) -> dict:
        """获取状态"""
        elapsed = time.time() - self.last_heartbeat
        return {
            "running": self.running,
            "heartbeat_count": self.heartbeat_count,
            "last_heartbeat": datetime.fromtimestamp(self.last_heartbeat).isoformat(),
            "seconds_since_last_beat": elapsed,
            "is_healthy": elapsed < self.timeout
        }


# 全局单例
_heartbeat_monitor = None


def get_heartbeat_monitor(**kwargs) -> HeartbeatMonitor:
    """获取全局心跳监控器实例"""
    global _heartbeat_monitor
    if _heartbeat_monitor is None:
        _heartbeat_monitor = HeartbeatMonitor(**kwargs)
    return _heartbeat_monitor
