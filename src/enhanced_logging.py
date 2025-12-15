"""
增强的日志系统

特性：
1. 结构化日志（JSON格式）
2. 日志轮转
3. 多级别输出（控制台+文件）
4. 交易日志独立记录
5. 性能指标记录
"""

import logging
import logging.handlers
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any


class StructuredFormatter(logging.Formatter):
    """结构化JSON日志格式"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 添加额外字段
        if hasattr(record, 'trade_id'):
            log_data['trade_id'] = record.trade_id
        if hasattr(record, 'symbol'):
            log_data['symbol'] = record.symbol
        if hasattr(record, 'pnl'):
            log_data['pnl'] = record.pnl
        
        # 异常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """彩色控制台日志格式"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_enhanced_logging(
    log_dir: str = "./logs",
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    structured: bool = True
) -> logging.Logger:
    """
    设置增强的日志系统
    
    Args:
        log_dir: 日志目录
        console_level: 控制台日志级别
        file_level: 文件日志级别
        structured: 是否使用结构化JSON格式
        
    Returns:
        配置好的logger
    """
    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # 获取root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # 清除现有handlers
    logger.handlers.clear()
    
    # ===== 控制台Handler =====
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, console_level.upper()))
    
    console_formatter = ColoredFormatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # ===== 文件Handler（通用日志）=====
    if structured:
        general_file = log_path / f"trading_{datetime.now().strftime('%Y%m%d')}.jsonl"
        general_handler = logging.handlers.TimedRotatingFileHandler(
            general_file,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        general_handler.setFormatter(StructuredFormatter())
    else:
        general_file = log_path / f"trading_{datetime.now().strftime('%Y%m%d')}.log"
        general_handler = logging.handlers.TimedRotatingFileHandler(
            general_file,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        general_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        general_handler.setFormatter(general_formatter)
    
    general_handler.setLevel(getattr(logging, file_level.upper()))
    logger.addHandler(general_handler)
    
    # ===== 错误日志（单独文件）=====
    error_file = log_path / "errors.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s\n'
        'Location: %(pathname)s:%(lineno)d\n'
        '%(exc_info)s\n' + '-'*80,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    error_handler.setFormatter(error_formatter)
    logger.addHandler(error_handler)
    
    logger.info(f"Enhanced logging initialized: {log_dir}")
    
    return logger


class TradeLogger:
    """
    交易专用日志记录器
    
    记录所有交易相关的关键事件和数据
    """
    
    def __init__(self, log_dir: str = "./logs/trades"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.trade_file = self.log_dir / f"trades_{datetime.now().strftime('%Y%m%d')}.jsonl"
        self.performance_file = self.log_dir / "performance.jsonl"
    
    def log_entry(self, trade_data: dict):
        """记录入场"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "ENTRY",
            **trade_data
        }
        self._append_to_file(self.trade_file, entry)
    
    def log_exit(self, trade_data: dict):
        """记录退出"""
        exit_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "EXIT",
            **trade_data
        }
        self._append_to_file(self.trade_file, exit_entry)
        
        # 计算交易统计
        self._update_performance(trade_data)
    
    def log_stop_moved(self, trade_id: str, old_stop: float, new_stop: float, reason: str):
        """记录止损移动"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "STOP_MOVED",
            "trade_id": trade_id,
            "old_stop": old_stop,
            "new_stop": new_stop,
            "reason": reason
        }
        self._append_to_file(self.trade_file, entry)
    
    def log_partial_exit(self, trade_id: str, size_closed: float, pnl: float):
        """记录部分平仓"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "PARTIAL_EXIT",
            "trade_id": trade_id,
            "size_closed": size_closed,
            "pnl": pnl
        }
        self._append_to_file(self.trade_file, entry)
    
    def _append_to_file(self, filepath: Path, data: dict):
        """追加JSON数据到文件"""
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')
    
    def _update_performance(self, exit_data: dict):
        """更新性能统计"""
        pnl = exit_data.get('pnl', 0)
        
        perf = {
            "timestamp": datetime.now().isoformat(),
            "pnl": pnl,
            "win": pnl > 0,
            "symbol": exit_data.get('symbol'),
            "exit_reason": exit_data.get('exit_reason')
        }
        
        self._append_to_file(self.performance_file, perf)


class MetricsLogger:
    """
    性能指标记录器
    
    记录系统性能指标和统计数据
    """
    
    def __init__(self, log_dir: str = "./logs/metrics"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics_file = self.log_dir / "metrics.jsonl"
    
    def log_execution_time(self, component: str, duration_ms: float):
        """记录执行时间"""
        metric = {
            "timestamp": datetime.now().isoformat(),
            "type": "execution_time",
            "component": component,
            "duration_ms": duration_ms
        }
        self._append(metric)
    
    def log_api_call(self, endpoint: str, status_code: int, duration_ms: float):
        """记录API调用"""
        metric = {
            "timestamp": datetime.now().isoformat(),
            "type": "api_call",
            "endpoint": endpoint,
            "status_code": status_code,
            "duration_ms": duration_ms
        }
        self._append(metric)
    
    def log_memory_usage(self, usage_mb: float):
        """记录内存使用"""
        metric = {
            "timestamp": datetime.now().isoformat(),
            "type": "memory_usage",
            "usage_mb": usage_mb
        }
        self._append(metric)
    
    def _append(self, data: dict):
        """追加指标"""
        with open(self.metrics_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')


# 全局实例
_trade_logger = None
_metrics_logger = None


def get_trade_logger() -> TradeLogger:
    """获取交易日志记录器"""
    global _trade_logger
    if _trade_logger is None:
        _trade_logger = TradeLogger()
    return _trade_logger


def get_metrics_logger() -> MetricsLogger:
    """获取性能指标记录器"""
    global _metrics_logger
    if _metrics_logger is None:
        _metrics_logger = MetricsLogger()
    return _metrics_logger
