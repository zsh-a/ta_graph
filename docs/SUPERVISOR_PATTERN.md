# Supervisor Pattern 架构说明

## 🎯 重构动机

原始的while循环架构存在以下问题：

1. **状态易丢失**：程序崩溃或重启后，持仓、止损位等关键信息丢失
2. **逻辑分散**：复杂的if/elif嵌套，难以理解和维护
3. **难以扩展**：添加新状态需要修改主循环结构
4. **难以调试**：无法可视化执行路径
5. **时间控制混乱**：sleep逻辑分散在各处

## ✨ Supervisor Pattern优势

### 1. 声明式图结构

**Before (Procedural)**:
```python
while True:
    if not equity_protector.can_trade():
        time.sleep(60)
        continue
    
    if status == "looking_for_trade":
        # 20行代码...
        if有订单:
            status = "order_pending"
    elif status == "order_pending":
        # 30行代码...
        if成交:
            status = "managing_position"
    # ...更多嵌套
```

**After (Declarative)**:
```python
def supervisor_router(state):
    if not state.get("is_trading_enabled"):
        return "cooldown"
    if state.get("position"):
        return "manager"
    return "scanner"

builder.add_conditional_edges("risk_guard", supervisor_router, {...})
```

### 2. 状态持久化

```python
# 使用SQLite自动保存状态
memory = SqliteSaver.from_conn_string("trading_state.db")
app = builder.compile(checkpointer=memory)

# 程序崩溃重启后，自动从DB恢复：
result = app.invoke({}, config={"thread_id": "btc_strategy"})
# ✓ 持仓信息完整恢复
# ✓ 止损位不丢失
# ✓ 订单状态保留
```

### 3. 清晰的职责分离

| 组件 | 职责 |
|------|------|
| `main.py` | 定时器（每30-60秒踢一次图） |
| `supervisor_graph.py` | 路由逻辑（去哪个节点？） |
| `market_scanner_node` | 调用analysis graph |
| `position_manager_node` | 调用position management |
| `risk_guard_node` | 风控检查 |

### 4. 易于扩展

添加新状态（如"等待用户确认"）：

```python
# 1. 添加节点
def approval_node(state):
    logger.info("Waiting for approval...")
    return {}

builder.add_node("approval", approval_node)

# 2. 修改路由
def router(state):
    if state.get("needs_approval"):
        return "approval"
    # ...

# 3. 设置中断点
app = builder.compile(interrupt_before=["approval"])
```

**无需修改main.py！**

### 5. LangSmith可视化

在LangSmith仪表盘可以看到：
```
Start → risk_guard → scanner → END
                  ↓
              manager → END
                  ↓
              cooldown → END
```

每次trade的完整执行路径都可追溯。

## 📊 架构对比

### 🔴 Before: Procedural Loop

```
┌─────────────────┐
│   while True:   │
│  ┌───────────┐  │
│  │ if 风控   │  │
│  │   continue │  │
│  └───────────┘  │
│  ┌───────────┐  │
│  │ if hunting│──┼──> analysis_graph
│  │   if订单  │  │
│  │     status│  │
│  └───────────┘  │
│  ┌───────────┐  │
│  │ if managing│──┼──> position_workflow
│  │   if退出  │  │
│  └───────────┘  │
│  sleep(?)       │
└─────────────────┘
```

- ❌ 状态在内存中，易丢失
- ❌ 逻辑嵌套深
- ❌ 时间控制混乱
- ❌ 难以测试

### 🟢 After: Supervisor Graph

```
┌──────────────────────────────────┐
│       Supervisor Graph           │
│  ┌────┐    ┌──────────┐          │
│  │init│───→│risk_guard│──┐       │
│  └────┘    └──────────┘  │       │
│                ┌──────────▼─────┐ │
│                │   router()     │ │
│                └┬────┬────┬────┘ │
│     ┌───────────┘    │    └─────┐│
│     ▼                ▼          ▼│
│  ┌──────┐       ┌────────┐  ┌──┐│
│  │scanner│       │manager │  │❄️││
│  └───┬──┘       └───┬────┘  └──┘│
│      │              │            │
│      ▼              ▼            │
│     END            END           │
└──────────────────────────────────┘
         ↓
    SQLite DB
```

- ✅ 状态持久化
- ✅ 声明式路由
- ✅ 职责清晰
- ✅ 易于测试

## 🚀 使用指南

### 基本使用

```bash
# 正常运行
python main.py

# 程序崩溃后重启
python main.py  # ✓ 自动从DB恢复状态
```

### 查看状态

```python
# 在SQLite中查看当前状态
import sqlite3
conn = sqlite3.connect("data/trading_state.db")
cursor = conn.execute("SELECT * FROM checkpoints ORDER BY checkpoint_id DESC LIMIT 1")
# 可以看到完整的state JSON
```

### 手动恢复

```python
# 如果需要手动修改状态
from src.supervisor_graph import build_trading_supervisor

app = build_trading_supervisor()
config = {"configurable": {"thread_id": "BTC_USDT_1h"}}

# 注入新数据
app.invoke({"status": "hunting", "position": None}, config=config)
```

### Human-in-the-Loop

```python
# 启用HITL模式
from src.supervisor_graph import build_trading_supervisor_with_hitl

app = build_trading_supervisor_with_hitl()

# 第一次运行会在下单前暂停
result = app.invoke(initial_state, config)
# → 暂停，等待审批

# 通过Telegram发送"approved"后：
from langgraph.pregel import Command
result = app.invoke(Command(resume="approved"), config)
# → 继续执行下单
```

## 📝 最佳实践

### 1. Thread ID命名

```python
# 好的命名：包含品种和策略信息
thread_id = f"{symbol}_{timeframe}_{strategy_version}"
# 例如: "BTC_USDT_1h_brooks_v2"

# 允许你同时运行多个策略而不冲突
```

### 2. 错误处理

```python
# 在节点内捕获异常，不要让图崩溃
def scanner_node(state):
    try:
        # ... 逻辑
        return updates
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        return {
            "errors": state.get("errors", []) + [str(e)],
            "next_action": "scan"  # 下次重试
        }
```

### 3. 逐步迁移

如果你担心一次性重构风险大，可以：

1. **Phase 1**: 保留原main.py，新建`main_supervisor.py`并行测试
2. **Phase 2**: 在测试网同时运行两个版本一周，对比结果
3. **Phase 3**: 确认supervisor版本稳定后，替换main.py

### 4. 监控和告警

```python
# 在每个节点添加性能监控
from src.dashboard import get_dashboard

def scanner_node(state):
    start = time.time()
    # ... 执行逻辑
    duration = (time.time() - start) * 1000
    
    get_dashboard().record_execution_time("scanner", duration)
    
    if duration > 5000:  # 超过5秒
        logger.warning(f"Scanner slow: {duration}ms")
```

## 🎯 总结

Supervisor Pattern带来的核心价值：

1. **可靠性** ⬆️ - 状态持久化，崩溃可恢复
2. **可维护性** ⬆️ - 声明式逻辑，易于理解
3. **可扩展性** ⬆️ - 添加节点无需改主循环
4. **可观测性** ⬆️ - LangSmith可视化执行路径
5. **可测试性** ⬆️ - 每个节点可独立测试

从"脚本"升级为"系统架构"！🚀
