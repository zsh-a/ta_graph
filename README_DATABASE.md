# 数据库和账户管理使用指南

## 概述

ta_graph 已集成完整的数据库和账户管理功能，迁移自 Super-nof1.ai 的 Prisma 架构，使用 SQLAlchemy ORM。

## 功能特性

### 1. **数据库模型**
- ✅ **ModelAccount** - AI模型账户管理（支持多模型独立账户）
- ✅ **Trading** - 交易记录（决策和执行）
- ✅ **TradingLesson** - 交易学习反馈（完成的交易结果）
- ✅ **ModelPerformanceSnapshot** - 性能快照（历史追踪）
- ✅ **Chat** - AI对话记录

### 2. **核心功能模块**
- `src/database/models.py` - SQLAlchemy 数据库模型
- `src/database/session.py` - 数据库连接管理
- `src/database/account_manager.py` - 模型账户管理
- `src/database/trading_history.py` - 交易历史管理

## 快速开始

### 1. 配置数据库

编辑 `.env` 文件：

```bash
# 使用 SQLite（开发环境）
DATABASE_URL=sqlite:///./trading.db

# 或使用 PostgreSQL（生产环境）
# DATABASE_URL=postgresql://user:password@localhost:5432/trading_db

# 默认AI模型
DEFAULT_MODEL=Qwen
```

### 2. 初始化数据库

```bash
python scripts/init_database.py
```

这将创建所有必需的表格。

### 3. 测试数据库功能

```bash
python scripts/test_database.py
```

## 使用示例

### 创建模型账户

```python
from src.database import get_session, ModelType
from src.database.account_manager import get_or_create_model_account

db = get_session()
try:
    account = get_or_create_model_account(
        model=ModelType.Qwen,
        name="Qwen Trading Model",
        api_key="your_bitget_api_key",
        api_secret="your_bitget_api_secret",
        passphrase="your_passphrase",  # 可选
        db=db
    )
    print(f"Account created: {account.name}")
finally:
    db.close()
```

### 同步账户信息

```python
from src.database.account_manager import sync_model_account_from_exchange

account_info = sync_model_account_from_exchange(ModelType.Qwen)
print(f"Balance: ${account_info.currentBalance:.2f}")
print(f"Total PnL: ${account_info.totalPnL:.2f}")
```

### 获取账户表现

```python
from src.database.trading_history import get_account_performance

performance = get_account_performance(model=ModelType.Qwen)
print(f"Return: {performance.currentTotalReturn*100:.2f}%")
print(f"Positions: {len(performance.positions)}")
```

### 创建交易记录

```python
from src.database.trading_history import create_trading_record
from src.database.models import SymbolType, OperationType

trade = create_trading_record(
    symbol=SymbolType.BTC,
    operation=OperationType.Buy,
    amount=100,
    pricing=95000,
    risk_amount=100.0,
    prediction={"short_term_trend": "bullish"},
    model_account_id=account.id
)
```

### 获取近期交易

```python
from src.database.trading_history import get_recent_trades_raw

trades = get_recent_trades_raw(limit=10)
for trade in trades:
    print(f"{trade['operation']} {trade['symbol']} - {trade['type']}")
```

## 在LangGraph节点中集成

### 在 Strategy 节点中使用

```python
# src/nodes/strategy.py
from ..database.trading_history import get_recent_trades_raw

def generate_strategy(state: AgentState) -> dict:
    # 获取历史交易用于RAG
    recent_trades = get_recent_trades_raw(limit=10)
    
    # 将历史交易添加到prompt
    # ...
```

### 在 Risk 节点中使用

```python
# src/nodes/risk.py
from ..database.trading_history import get_account_performance

def assess_risk(state: AgentState) -> dict:
    # 获取账户信息
    performance = get_account_performance()
    available_cash = performance.availableCash
    
    # 检查资金是否足够
    # ...
```

### 在 Execution 节点中使用

```python
# src/nodes/execution.py
from ..database.trading_history import create_trading_record
from ..database.account_manager import update_model_trade_stats

def execute_trade(state: AgentState) -> dict:
    # 执行交易后记录
    trade = create_trading_record(
        symbol=SymbolType.BTC,
        operation=OperationType.Buy,
        # ...
    )
    
    # 更新统计
    update_model_trade_stats(
        model=ModelType.Qwen,
        is_win=True,
        pnl=150.0
    )
```

## 数据库迁移

### 创建迁移脚本（使用 Alembic）

```bash
# 初始化 Alembic（仅首次）
alembic init alembic

# 创建迁移
alembic revision --autogenerate -m "Add new column"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

## 模型账户说明

### 多模型独立账户

每个AI模型可以有独立的交易所账户：

```python
# 为不同模型配置不同账户
accounts = [
    get_or_create_model_account(
        model=ModelType.Qwen,
        api_key="qwen_api_key",
        api_secret="qwen_secret"
    ),
    get_or_create_model_account(
        model=ModelType.QwenVLSFT,
        api_key="qwen_sft_api_key",
        api_secret="qwen_sft_secret"
    )
]
```

### 性能追踪

创建定期快照：

```python
from src.database.account_manager import create_performance_snapshot

# 每天创建一次
create_performance_snapshot(ModelType.Qwen)
```

查询历史表现：

```python
from src.database.account_manager import get_model_performance_history

history = get_model_performance_history(ModelType.Qwen, days=30)
for snapshot in history:
    print(f"{snapshot.snapshotDate}: ${snapshot.balance:.2f}")
```

## 架构对比

### Prisma (TypeScript) → SQLAlchemy (Python)

| Prisma | SQLAlchemy |
|--------|-----------|
| `prisma.modelAccount.findUnique()` | `db.query(ModelAccount).filter_by().first()` |
| `prisma.modelAccount.create()` | `db.add(ModelAccount(...))` |
| `prisma.trading.findMany()` | `db.query(Trading).all()` |
| `@relation` | `relationship()` |
| `Json` type | `Column(JSON)` |

## 最佳实践

1. **使用上下文管理器**
   ```python
   from src.database import get_db
   
   with get_db() as db:
       account = db.query(ModelAccount).first()
       # 自动提交和关闭
   ```

2. **事务处理**
   ```python
   try:
       db.add(trade)
       db.add(lesson)
       db.commit()
   except Exception as e:
       db.rollback()
       raise
   ```

3. **懒加载关系**
   ```python
   # 访问关联数据时自动加载
   account = db.query(ModelAccount).first()
   trades = account.tradings  # 自动查询关联的交易
   ```

## 故障排查

### 问题1: 数据库连接失败

```bash
# 检查 DATABASE_URL 是否正确
echo $DATABASE_URL

# 测试 PostgreSQL 连接
psql $DATABASE_URL
```

### 问题2: 表不存在

```bash
# 重新初始化数据库
python scripts/init_database.py
```

### 问题3: SQLAlchemy 版本冲突

```bash
# 使用 uv 重新安装
uv pip install --upgrade sqlalchemy
```

## 下一步

- [ ] 集成真实的交易所API同步（ccxt）
- [ ] 实现自动性能快照（定时任务）
- [ ] 添加数据备份和恢复功能
- [ ] 实现交易学习反馈（TradingLesson）自动生成
