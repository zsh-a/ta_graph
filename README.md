# Complete Trading System

完整的Al Brooks风格量化交易系统，集成市场分析、策略生成、风险管理和持仓管理。

## 🎯 系统架构

### 双循环设计

```
┌─────────────────────────────────────────────────────┐
│                   Main Loop                         │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Loop A: HUNTING MODE                        │  │
│  │  (looking_for_trade)                        │  │
│  │                                              │  │
│  │  1. Market Data Fetch                       │  │
│  │  2. Brooks Analysis (VL Model)              │  │
│  │  3. Strategy Generation                     │  │
│  │  4. Risk Assessment                         │  │
│  │  5. Order Execution                         │  │
│  │         │                                    │  │
│  │         ├─ Order Placed ──────────────────┐  │  │
│  │         └─ No Signal → Wait next bar      │  │  │
│  └──────────────────────────────────────────────┘  │
│                    │                                │
│                    ▼                                │
│  ┌──────────────────────────────────────────────┐  │
│  │  Loop B: MANAGING MODE                       │  │
│  │  (order_pending / managing_position)         │  │
│  │                                              │  │
│  │  1. Order Monitor (Setup timeliness)        │  │
│  │  2. Position Sync (Exchange reconciliation) │  │
│  │  3. Follow-through Analysis                 │  │
│  │  4. Risk Management (Breakeven/Trailing)    │  │
│  │  5. Stop Loss Check                         │  │
│  │         │                                    │  │
│  │         ├─ Exit → Back to Loop A            │  │
│  │         └─ Continue → Next check            │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 1. 环境配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 填入你的API密钥
# 必填项：
# - BITGET_API_KEY
# - BITGET_API_SECRET  
# - BITGET_API_PASSPHRASE
# - MODELSCOPE_API_KEY
```

### 2. 安装依赖

```bash
uv sync
```

### 3. 沙盒测试

```bash
# 确保 .env 中设置
BITGET_SANDBOX=true
TRADING_MODE=dry-run

# 运行主程序
python main.py
```

### 4. 生产环境

⚠️ **谨慎操作！确保充分测试后再上线**

```bash
# .env 设置
BITGET_SANDBOX=false
TRADING_MODE=live
MAX_POSITION_SIZE_PERCENT=5.0  # 从小仓位开始

# 运行
python main.py
```

## 📋 核心功能

### ✅ 市场分析

- **K线数据获取** (`fetch_market_data`)
- **Al Brooks分析** (`brooks_analyzer`)
  - 使用VL模型分析价格行为
  - 识别Setup、Entry Bar、Follow-through
  - TTR检测与趋势判断

### ✅ 策略与风险

- **策略生成** (`generate_strategy`)
  - 基于Brooks分析生成交易信号
  - Conviction Tracker防止幻觉
- **风险评估** (`assess_risk`)
  - 止损/止盈计算
  - 仓位大小控制

### ✅ 持仓管理

- **订单监控** (`order_monitor`)
  - Setup时效性检查
  - 超时自动取消
- **状态对账** (`position_sync`)
  - 与交易所强制同步
  - 处理异常情况
- **Follow-through分析** (`followthrough_analyzer`)
  - 入场后1-2根K线质量评估
  - 决定持有/退出/收紧
- **动态风险管理** (`risk_manager`)
  - Breakeven移动
  - Bar-by-Bar Trailing Stop
  - Measured Move目标

### ✅ 安全机制

- **Equity Protector**
  - 每日亏损熔断 (默认2%)
  - 连败暂停 (默认3连败)
  - 冷却期机制
- **Conviction Tracker**
  - 多信号确认
  - 防止AI幻觉
- **Heartbeat Monitor**
  - 系统存活检测
  - 死锁警报

### ✅ 通知系统

- Telegram推送
- 邮件通知
- 关键事件日志

## 📁 项目结构

```
ta_graph/
├── main.py                          # 主程序入口
├── src/
│   ├── graph.py                     # Loop A: 市场分析workflow
│   ├── position_management_workflow.py  # Loop B: 持仓管理workflow
│   ├── nodes/                       # 各个节点
│   │   ├── market_data.py
│   │   ├── brooks_analyzer.py
│   │   ├── strategy_enhanced.py
│   │   ├── risk.py
│   │   ├── execution.py
│   │   ├── order_monitor.py
│   │   ├── position_sync.py
│   │   ├── followthrough_analyzer.py
│   │   └── risk_manager.py
│   ├── safety/                      # 安全机制
│   │   ├── equity_protector.py
│   │   └── conviction_tracker.py
│   ├── monitoring/                  # 系统监控
│   │   └── heartbeat.py
│   ├── notification/                # 通知系统
│   │   └── alerts.py
│   └── trading/                     # 交易接口
│       └── exchange_client.py
├── tests/                           # 测试套件
└── .env.example                     # 环境变量模板
```

## 🔧 配置说明

### 关键参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `MAX_POSITION_SIZE_PERCENT` | 最大仓位% | 10% |
| `DEFAULT_LEVERAGE` | 杠杆倍数 | 10x |
| `MAX_DAILY_LOSS_PERCENT` | 每日最大亏损% | 2% |
| `MAX_CONSECUTIVE_LOSSES` | 最大连败数 | 3 |
| `PRIMARY_TIMEFRAME` | 主时间周期 | 1h |

### Brooks原则配置

系统深度集成Al Brooks原则，无需额外配置：

- ✅ Setup时效性（订单超时取消）
- ✅ Follow-through优先（入场后立即分析）
- ✅ 动态止损（Breakeven, Trailing）
- ✅ Measured Move目标
- ✅ TTR避让（窄幅震荡不交易）

## 📊 监控与日志

### 日志级别

```bash
# .env 设置
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### 关键日志

- `🔍 HUNTING MODE` - 寻找交易机会
- `📊 MANAGING MODE` - 持仓管理中
- `✅ Order placed` - 订单已下
- `💓 Heartbeat` - 系统存活
- `🛑 Blocked` - 安全机制阻止
- `⏸️ Trading disabled` - 资金保护触发

### Langfuse追踪

访问 https://cloud.langfuse.com 查看：
- AI模型调用
- 决策路径
- 性能指标

## 🧪 测试

```bash
# 运行所有测试
./run_tests.sh

# 或单独运行
PYTHONPATH=. uv run pytest tests/ -v

# 测试覆盖率
PYTHONPATH=. uv run pytest tests/ --cov=src --cov-report=html
```

## 🚨 重要提示

### ⚠️ 风险警告

1. **量化交易有风险**，可能导致资金损失
2. **从小仓位开始**（建议≤5%）
3. **充分沙盒测试**后再上真实环境
4. **持续监控**系统运行状态
5. **设置合理的止损**和资金保护

### 🔐 安全建议

- ✅ 使用API **只读+交易权限**（禁用提现）
- ✅ 启用**IP白名单**
- ✅ 定期更换API密钥
- ✅ 使用**沙盒环境**测试
- ✅ 设置**每日亏损限制**

### 📈 最佳实践

1. **渐进式部署**
   - 沙盒测试 → 小仓位真实 → 逐步增加
2. **持续优化**
   - 记录所有交易
   - 分析成功/失败案例
   - 调整参数
3. **定期review**
   - 每周检查equity protector状态
   - 每月分析交易日志
   - 季度策略回顾

## 📚 相关文档

- [Implementation Plan](./brain/position_management_plan.md) - 实施计划
- [Testing Report](./brain/testing_report.md) - 测试报告
- [Bitget Symbol Format](./docs/bitget_symbol_format.md) - 交易对格式

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 License

MIT
