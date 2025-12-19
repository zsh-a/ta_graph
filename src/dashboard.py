"""
监控仪表盘 (FastAPI版)

提供实时 WebSockets 接口和 REST API，支持专业前端监控面板。
"""

import asyncio
from datetime import datetime
from typing import Any
from collections import deque
import threading

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .utils.event_bus import get_event_bus
from .logger import get_logger

logger = get_logger(__name__)

class DashboardMetrics:
    """仪表盘指标收集器 - 扩展支持事件发送"""
    
    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self.bus = get_event_bus()
        
        # 实时指标
        self.heartbeat_count = 0
        self.last_heartbeat = datetime.now()
        
        # 交易统计
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        
        # 历史记录
        self.pnl_history = deque(maxlen=history_size)
        self.execution_times = deque(maxlen=history_size)
        self.event_history = deque(maxlen=500)  # 存储最近500条执行日志以便重连时回放
        
        # 系统状态
        self.current_status = "initializing"
        self.current_position = None
        self.equity_protector_status = {}
        
        # 错误统计
        self.error_count = 0
        self.last_error = None

    def _emit_sync(self, event_type: str, data: Any):
        """同步发送事件 (直接使用 bus.emit_sync)"""
        self.bus.emit_sync(event_type, data)

    def update_heartbeat(self):
        self.heartbeat_count += 1
        self.last_heartbeat = datetime.now()
        self._emit_sync("system_update", {"heartbeat": self.heartbeat_count})
    
    def record_trade(self, pnl: float, win: bool):
        self.total_trades += 1
        if win:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        self.total_pnl += pnl
        entry = {
            "timestamp": datetime.now().isoformat(),
            "pnl": pnl,
            "cumulative_pnl": self.total_pnl
        }
        self.pnl_history.append(entry)
        self._emit_sync("trade_update", entry)
    
    def record_execution_time(self, component: str, duration_ms: float):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "duration_ms": duration_ms
        }
        self.execution_times.append(entry)
        self._emit_sync("performance_update", entry)
    
    def update_status(self, status: str):
        if self.current_status != status:
            self.current_status = status
            self._emit_sync("status_change", {"status": status})
    
    def update_position(self, position: dict | None):
        self.current_position = position
        self._emit_sync("position_update", position)
    
    def update_equity_protector(self, status: dict):
        self.equity_protector_status = status
        self._emit_sync("safety_update", status)
    
    def record_error(self, error: str):
        self.error_count += 1
        self.last_error = {
            "timestamp": datetime.now().isoformat(),
            "error": error
        }
        self._emit_sync("error_added", self.last_error)
    
    def get_dashboard_data(self) -> dict:
        return {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "status": self.current_status,
                "heartbeat_count": self.heartbeat_count,
                "last_heartbeat": self.last_heartbeat.isoformat()
            },
            "trading": {
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades,
                "total_pnl": round(self.total_pnl, 2),
                "current_position": self.current_position
            },
            "performance": {
                "recent_pnl": list(self.pnl_history),
                "execution_times": list(self.execution_times)
            },
            "safety": {
                "equity_protector": self.equity_protector_status,
                "error_count": self.error_count,
                "last_error": self.last_error
            },
            "history": list(self.event_history)
        }

# 全局单例
_dashboard = DashboardMetrics()

def get_dashboard() -> DashboardMetrics:
    return _dashboard

# FastAPI 应用
app = FastAPI(title="ta_graph Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "ok", "message": "ta_graph Dashboard API is running"}

@app.get("/metrics")
async def get_metrics():
    logger.info("📊 Metrics requested via REST API")
    return get_dashboard().get_dashboard_data()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_host = websocket.client.host if websocket.client else "unknown"
    logger.info(f"🔌 New WebSocket connection attempt from {client_host}")
    try:
        await websocket.accept()
        logger.info(f"✅ WebSocket connection accepted from {client_host}")
    except Exception as e:
        logger.error(f"❌ WebSocket acceptance failed: {e}")
        return

    bus = get_event_bus()
    
    # 定义订阅回调
    async def on_event(event):
        try:
            await websocket.send_json(event)
        except Exception:
            # 连接可能已断开
            pass

    # 订阅所有事件
    bus.subscribe("*", on_event)
    
    try:
        # 发送初始状态
        await websocket.send_json({
            "type": "initial_state",
            "data": get_dashboard().get_dashboard_data(),
            "timestamp": datetime.now().isoformat()
        })
        
        while True:
            # 保持连接，并接收前端心跳或指令
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info(f"🔌 Dashboard WebSocket disconnected from {client_host}")
    except Exception as e:
        logger.error(f"🔌 WebSocket error for {client_host}: {e}")
    finally:
        # 必须取消订阅，否则会造成内存泄漏和性能问题
        bus.unsubscribe("*", on_event)

@app.on_event("startup")
async def startup_event():
    """FastAPI 启动时初始化"""
    bus = get_event_bus()
    bus.start()
    
    # 开始缓冲历史事件
    dashboard = get_dashboard()
    async def buffer_history(event):
        dashboard.event_history.append(event)
    bus.subscribe("*", buffer_history)
    
    logger.info("✓ Dashboard EventBus started (FastAPI startup)")

def start_dashboard_server(port: int = 8000):
    """启动仪表盘服务器"""
    
    def serve():
        logger.info(f"🚀 Starting uvicorn server on port {port}...")
        try:
            # 改用 info 级别查看更多启动详情
            uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
        except Exception as e:
            logger.error(f"❌ Uvicorn failed to start: {e}")
    
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

# 兼容旧代码
def generate_dashboard_html(data: dict) -> str:
    return "Use the React frontend for the professional dashboard."
