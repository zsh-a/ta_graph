"""
监控仪表盘

提供实时系统监控和性能指标展示
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
from collections import deque


class DashboardMetrics:
    """仪表盘指标收集器"""
    
    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        
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
        
        # 系统状态
        self.current_status = "initializing"
        self.current_position = None
        self.equity_protector_status = {}
        
        # 错误统计
        self.error_count = 0
        self.last_error = None
    
    def update_heartbeat(self):
        """更新心跳"""
        self.heartbeat_count += 1
        self.last_heartbeat = datetime.now()
    
    def record_trade(self, pnl: float, win: bool):
        """记录交易"""
        self.total_trades += 1
        if win:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        self.total_pnl += pnl
        self.pnl_history.append({
            "timestamp": datetime.now().isoformat(),
            "pnl": pnl,
            "cumulative_pnl": self.total_pnl
        })
    
    def record_execution_time(self, component: str, duration_ms: float):
        """记录执行时间"""
        self.execution_times.append({
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "duration_ms": duration_ms
        })
    
    def update_status(self, status: str):
        """更新系统状态"""
        self.current_status = status
    
    def update_position(self, position: dict | None):
        """更新持仓"""
        self.current_position = position
    
    def update_equity_protector(self, status: dict):
        """更新资金保护器状态"""
        self.equity_protector_status = status
    
    def record_error(self, error: str):
        """记录错误"""
        self.error_count += 1
        self.last_error = {
            "timestamp": datetime.now().isoformat(),
            "error": error
        }
    
    def get_win_rate(self) -> float:
        """获取胜率"""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    def get_avg_execution_time(self) -> float:
        """获取平均执行时间"""
        if not self.execution_times:
            return 0.0
        return sum(e['duration_ms'] for e in self.execution_times) / len(self.execution_times)
    
    def get_dashboard_data(self) -> dict:
        """获取仪表盘数据"""
        return {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "status": self.current_status,
                "heartbeat_count": self.heartbeat_count,
                "last_heartbeat": self.last_heartbeat.isoformat(),
                "uptime_seconds": (datetime.now() - self.last_heartbeat).total_seconds() if self.heartbeat_count > 0 else 0
            },
            "trading": {
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades,
                "win_rate_percent": round(self.get_win_rate(), 2),
                "total_pnl": round(self.total_pnl, 2),
                "current_position": self.current_position
            },
            "performance": {
                "avg_execution_time_ms": round(self.get_avg_execution_time(), 2),
                "recent_pnl": list(self.pnl_history)[-10:] if self.pnl_history else []
            },
            "safety": {
                "equity_protector": self.equity_protector_status,
                "error_count": self.error_count,
                "last_error": self.last_error
            }
        }
    
    def save_snapshot(self, filepath: str = "./logs/dashboard_snapshot.json"):
        """保存仪表盘快照"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.get_dashboard_data(), f, indent=2, ensure_ascii=False)
    
    def print_dashboard(self):
        """打印仪表盘（控制台）"""
        data = self.get_dashboard_data()
        
        print("\n" + "="*80)
        print(" "*30 + "TRADING DASHBOARD")
        print("="*80)
        
        # 系统状态
        print(f"\n📊 SYSTEM STATUS")
        print(f"  Status: {data['system']['status']}")
        print(f"  Heartbeat: #{data['system']['heartbeat_count']}")
        print(f"  Last Beat: {data['system']['last_heartbeat']}")
        
        # 交易统计
        print(f"\n💼 TRADING STATISTICS")
        print(f"  Total Trades: {data['trading']['total_trades']}")
        print(f"  Win/Loss: {data['trading']['winning_trades']}/{data['trading']['losing_trades']}")
        print(f"  Win Rate: {data['trading']['win_rate_percent']}%")
        print(f"  Total PnL: ${data['trading']['total_pnl']:.2f}")
        
        # 当前持仓
        if data['trading']['current_position']:
            pos = data['trading']['current_position']
            print(f"\n📈 CURRENT POSITION")
            print(f"  Side: {pos.get('side', 'N/A')}")
            print(f"  Entry: ${pos.get('entry_price', 0):.2f}")
            print(f"  Size: {pos.get('size', 0)}")
            print(f"  Unrealized PnL: ${pos.get('unrealized_pnl', 0):.2f}")
        
        # 性能
        print(f"\n⚡ PERFORMANCE")
        print(f"  Avg Execution Time: {data['performance']['avg_execution_time_ms']:.2f}ms")
        
        # 安全
        ep = data['safety']['equity_protector']
        if ep:
            print(f"\n🛡️  EQUITY PROTECTOR")
            print(f"  Trading Enabled: {ep.get('trading_enabled', 'N/A')}")
            print(f"  Daily PnL: ${ep.get('daily_pnl', 0):.2f}")
            print(f"  Consecutive Losses: {ep.get('consecutive_losses', 0)}")
        
        print(f"\n⚠️  ERRORS: {data['safety']['error_count']}")
        
        print("="*80 + "\n")


# 全局仪表盘实例
_dashboard = None


def get_dashboard() -> DashboardMetrics:
    """获取全局仪表盘"""
    global _dashboard
    if _dashboard is None:
        _dashboard = DashboardMetrics()
    return _dashboard


def start_dashboard_server(port: int = 8000):
    """
    启动仪表盘HTTP服务器（可选）
    
    提供简单的HTTP API访问仪表盘数据
    """
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading
    
    dashboard = get_dashboard()
    
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                # 返回HTML仪表盘
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                html = generate_dashboard_html(dashboard.get_dashboard_data())
                self.wfile.write(html.encode())
            
            elif self.path == '/api/metrics':
                # 返回JSON数据
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                data = json.dumps(dashboard.get_dashboard_data(), ensure_ascii=False)
                self.wfile.write(data.encode())
            
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            # 禁用默认日志
            pass
    
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    
    def serve():
        print(f"✓ Dashboard server started at http://localhost:{port}")
        server.serve_forever()
    
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()


def generate_dashboard_html(data: dict) -> str:
    """生成HTML仪表盘"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Trading Dashboard</title>
    <meta http-equiv="refresh" content="5">
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Monaco', 'Courier New', monospace;
            background: #1a1a1a;
            color: #00ff00;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{ color: #00ff00; text-align: center; }}
        .section {{
            background: #2a2a2a;
            border: 2px solid #00ff00;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
        }}
        .metric-label {{ color: #888; }}
        .metric-value {{ color: #00ff00; font-weight: bold; }}
        .positive {{ color: #00ff00; }}
        .negative {{ color: #ff0000; }}
        .timestamp {{ text-align: center; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 TRADING DASHBOARD 🚀</h1>
        <div class="timestamp">Last Updated: {data['timestamp']}</div>
        
        <div class="section">
            <h2>📊 System Status</h2>
            <div class="metric">
                <span class="metric-label">Status:</span>
                <span class="metric-value">{data['system']['status'].upper()}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Heartbeat:</span>
                <span class="metric-value">#{data['system']['heartbeat_count']}</span>
            </div>
        </div>
        
        <div class="section">
            <h2>💼 Trading Statistics</h2>
            <div class="metric">
                <span class="metric-label">Total Trades:</span>
                <span class="metric-value">{data['trading']['total_trades']}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Win Rate:</span>
                <span class="metric-value">{data['trading']['win_rate_percent']}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Total PnL:</span>
                <span class="metric-value {'positive' if data['trading']['total_pnl'] > 0 else 'negative'}">
                    ${data['trading']['total_pnl']:.2f}
                </span>
            </div>
        </div>
        
        <div class="section">
            <h2>⚡ Performance</h2>
            <div class="metric">
                <span class="metric-label">Avg Execution Time:</span>
                <span class="metric-value">{data['performance']['avg_execution_time_ms']:.2f}ms</span>
            </div>
        </div>
        
        <div class="section">
            <h2>🛡️ Safety</h2>
            <div class="metric">
                <span class="metric-label">Error Count:</span>
                <span class="metric-value">{data['safety']['error_count']}</span>
            </div>
        </div>
    </div>
</body>
</html>
"""


if __name__ == "__main__":
    # 测试仪表盘
    dashboard = get_dashboard()
    
    # 模拟数据
    dashboard.update_status("running")
    dashboard.update_heartbeat()
    dashboard.record_trade(100.5, True)
    dashboard.record_trade(-50.2, False)
    dashboard.record_execution_time("market_data", 125.3)
    
    # 打印仪表盘
    dashboard.print_dashboard()
    
    # 启动HTTP服务器
    start_dashboard_server(8000)
    
    print("Dashboard server running. Visit http://localhost:8000")
    print("Press Ctrl+C to stop...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")
