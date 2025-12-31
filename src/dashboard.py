"""
监控仪表盘 (FastAPI版)

提供实时 WebSockets 接口和 REST API，支持专业前端监控面板。
"""

import asyncio
from datetime import datetime, timezone
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
        self.last_heartbeat = datetime.now(timezone.utc)
        
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

        # 累计指标
        self.peak_pnl: float = 0.0
        self.max_drawdown: float = 0.0

    def _emit_sync(self, event_type: str, data: Any):
        """同步发送事件 (直接使用 bus.emit_sync)"""
        self.bus.emit_sync(event_type, data)

    def update_heartbeat(self):
        self.heartbeat_count += 1
        self.last_heartbeat = datetime.now(timezone.utc)
        self._emit_sync("system_update", {"heartbeat": self.heartbeat_count})
    
    def record_trade(self, pnl: float, win: bool):
        self.total_trades += 1
        if win:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        self.total_pnl += pnl
        
        # 更新峰值和回撤
        if self.total_pnl > self.peak_pnl:
            self.peak_pnl = self.total_pnl
        
        drawdown = self.peak_pnl - self.total_pnl
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pnl": pnl,
            "cumulative_pnl": self.total_pnl,
            "peak_pnl": self.peak_pnl,
            "max_drawdown": self.max_drawdown
        }
        self.pnl_history.append(entry)
        self._emit_sync("trade_update", entry)
    
    def record_execution_time(self, component: str, duration_ms: float):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error
        }
        self._emit_sync("error_added", self.last_error)
    
    def get_dashboard_data(self) -> dict:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
                "pnl_percentage": self._calculate_pnl_percentage(),
                "max_drawdown": round(self.max_drawdown, 2),
                "drawdown_percent": self._calculate_drawdown_percent(),
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

    def _calculate_pnl_percentage(self) -> float:
        """从 account_manager 获取初始资金并计算收益率"""
        try:
            from .database.account_manager import get_account_manager
            am = get_account_manager()
            info = am.get_account_info()
            # 简单估算：当前资金 / (当前资金 - 累计收益) - 1
            # 更好的做法是记录 initial_balance
            initial = info.total_balance - self.total_pnl
            if initial > 0:
                return round((self.total_pnl / initial) * 100, 2)
        except Exception:
            pass
        return 0.0

    def _calculate_drawdown_percent(self) -> float:
        """计算百分比回撤"""
        try:
            from .database.account_manager import get_account_manager
            am = get_account_manager()
            info = am.get_account_info()
            if info.total_balance > 0:
                return round((self.max_drawdown / (info.total_balance + self.max_drawdown)) * 100, 2)
        except Exception:
            pass
        return 0.0

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


@app.get("/graph")
async def get_graph_structure():
    """Return the LangGraph supervisor structure for visualization."""
    from .supervisor_graph import build_trading_supervisor
    
    try:
        # Build the graph and get its structure with xray enabled
        graph = build_trading_supervisor()
        drawable = graph.get_graph(xray=True)
        
        # Convert to ReactFlow-compatible format
        nodes = []
        edges = []
        
        # Track subgraph membership for grouping
        subgraph_map: dict[str, str] = {}  # node_id -> subgraph_name
        
        for node_id, node in drawable.nodes.items():
            # Skip __start__ and __end__ for cleaner visualization
            if node_id in ("__start__", "__end__"):
                continue
            
            # Parse subgraph nodes (format: "subgraph:node_name")
            if ":" in node_id:
                parts = node_id.split(":", 1)
                subgraph_name = parts[0]
                node_name = parts[1]
                subgraph_map[node_id] = subgraph_name
                
                # Skip internal __start__/__end__ nodes of subgraphs
                if node_name in ("__start__", "__end__"):
                    continue
                
                label = node_name.replace("_", " ").title()
            else:
                label = node_id.replace("_", " ").title()
            
            nodes.append({
                "id": node_id,
                "label": label,
                "subgraph": subgraph_map.get(node_id),
            })
        
        for edge in drawable.edges:
            source = edge.source
            target = edge.target
            
            # Skip edges from/to __start__/__end__
            if source in ("__start__", "__end__") or target in ("__start__", "__end__"):
                # Map __start__ edges to first real node
                if source == "__start__":
                    continue
                if target == "__end__":
                    continue
            
            # Skip internal subgraph __start__/__end__ edges
            if source.endswith(":__start__") or source.endswith(":__end__"):
                continue
            if target.endswith(":__start__") or target.endswith(":__end__"):
                continue
            
            edges.append({
                "id": f"e-{source}-{target}",
                "source": source,
                "target": target,
                "conditional": edge.conditional,
                "label": edge.data if edge.data else None,
            })
        
        # Get unique subgraphs for grouping info
        subgraphs = list(set(subgraph_map.values()))
        
        return {
            "nodes": nodes,
            "edges": edges,
            "subgraphs": subgraphs,
        }
    except Exception as e:
        logger.error(f"Error getting graph structure: {e}")
        return {"error": str(e), "nodes": [], "edges": [], "subgraphs": []}

@app.get("/history/runs")
async def get_history_runs(
    start_date: str | None = None,
    end_date: str | None = None,
    symbol: str | None = None,
    limit: int = 50
):
    """Fetch historical workflow runs."""
    from .database.persistence_manager import get_persistence_manager
    
    start_dt = None
    end_dt = None
    
    try:
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError as e:
        return {"error": f"Invalid date format: {e}"}

    with get_persistence_manager() as pm:
        runs = pm.get_runs(
            start_date=start_dt,
            end_date=end_dt,
            symbol=symbol,
            limit=limit
        )
    return {"runs": runs}

@app.get("/history/runs/{run_id}")
async def get_history_run_details(run_id: str):
    """Fetch detailed data for a specific workflow run."""
    from .database.persistence_manager import get_persistence_manager
    with get_persistence_manager() as pm:
        details = pm.get_run_details(run_id)
    if not details:
        return {"error": "Run not found", "id": run_id}
    return details

@app.get("/history/orders")
async def get_history_orders(
    start_date: str | None = None,
    end_date: str | None = None,
    symbol: str | None = None,
    limit: int = 50,
    page: int = 1,
    source: str = 'local'
):
    """Fetch historical orders and statistics."""
    from .database.trading_history import get_order_history
    
    start_dt = None
    end_dt = None
    
    try:
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError as e:
        return {"error": f"Invalid date format: {e}"}

    offset = (page - 1) * limit
    return get_order_history(
        start_date=start_dt,
        end_date=end_dt,
        symbol=symbol,
        limit=limit,
        offset=offset,
        source=source
    )

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
            "timestamp": datetime.now(timezone.utc).isoformat()
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
    
    # Tryer to restore historical events from database
    try:
        from .database.persistence_manager import get_persistence_manager
        with get_persistence_manager() as pm:
            recent_events = pm.get_recent_dashboard_events(limit=100)
            logger.info(f"🔄 Rehydrating dashboard with {len(recent_events)} events from database")
            for event in recent_events:
                dashboard.event_history.append(event)
    except Exception as e:
        logger.warning(f"⚠️ Failed to rehydrate dashboard history: {e}")

    async def buffer_history(event):
        """Buffer event in memory and persist to database"""
        if 'timestamp' not in event:
            event['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        dashboard.event_history.append(event)
        
        # Persist to database for rehydration after restart
        try:
            # logger.debug(f"🔍 Attempting to persist event: type={event.get('type')}, node={(event.get('data') or {}).get('node')}")
            from .database.persistence_manager import get_persistence_manager
            with get_persistence_manager() as pm:
                pm.store_dashboard_event(event)
            # logger.debug(f"✅ Event persisted successfully")
        except Exception as e:
            logger.warning(f"⚠️ Failed to persist dashboard event: {e}")
            import traceback
            logger.warning(traceback.format_exc())
    
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
