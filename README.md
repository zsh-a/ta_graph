# ta_graph - AI Trading Agent

Python-based trading agent using LangGraph, migrated from Super-nof1.ai.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Using uv (recommended - fast!)
uv pip install -r requirements.txt

# Or using pip
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your settings
```

### 3. Initialize Database

```bash
python scripts/init_database.py
```

### 4. Run Trading Agent

```bash
python main.py
```

## 📁 Project Structure

```
ta_graph/
├── src/
│   ├── database/          # 数据库模型和管理
│   │   ├── models.py      # SQLAlchemy models
│   │   ├── account_manager.py
│   │   └── trading_history.py
│   ├── nodes/             # LangGraph节点
│   │   ├── market_data.py
│   │   ├── analysis.py
│   │   ├── strategy.py
│   │   ├── risk.py
│   │   └── execution.py
│   ├── utils/             # 工具模块
│   │   ├── model_manager.py
│   │   ├── timeframe_config.py
│   │   └── price_calculator.py
│   ├── state.py           # LangGraph状态定义
│   ├── prompts.py         # AI提示词
│   ├── graph.py           # LangGraph工作流
│   └── logger.py          # 日志配置
├── scripts/               # 脚本
│   ├── init_database.py
│   └── test_database.py
├── main.py                # 主程序入口
├── requirements.txt       # 依赖列表
└── .env.example           # 配置模板
```

## 📚 Documentation

- [README_DATABASE.md](README_DATABASE.md) - 数据库和账户管理指南
- [walkthrough.md](.gemini/antigravity/brain/.../walkthrough.md) - 完整迁移过程文档

## ⚙️ Configuration

### Database
```bash
# SQLite (开发)
DATABASE_URL=sqlite:///./trading.db

# PostgreSQL (生产)
DATABASE_URL=postgresql://user:password@localhost:5432/trading_db
```

### AI Model
```bash
# 使用本地模型
MODEL_PROVIDER=local
LOCAL_API_URL=http://localhost:8080/v1

# 使用ModelScope
MODEL_PROVIDER=modelscope
MODELSCOPE_API_KEY=your_key
```

### Trading
```bash
PRIMARY_TIMEFRAME=1h
DEFAULT_MODEL=Qwen
TRADING_MODE=dry-run
```

## 🧪 Testing

```bash
# Test database
python scripts/test_database.py

# Test model manager
python test_model_switch.py

# Test timeframe config
python test_timeframe.py
```

## 🔑 Key Features

- ✅ **LangGraph Workflow** - 清晰的交易决策流程
- ✅ **Multi-Provider LLM** - 支持本地/ModelScope/OpenAI
- ✅ **Database Management** - SQLAlchemy + PostgreSQL/SQLite
- ✅ **Account Tracking** - 多模型独立账户管理
- ✅ **Risk Management** - 完整的风险控制系统
- ✅ **Price Action Trading** - 基于Al Brooks理论
- ✅ **Performance Tracking** - 交易历史和性能快照

## 🛠️ Tech Stack

- **Framework**: LangGraph
- **LLM**: LangChain + OpenAI/ModelScope
- **Database**: SQLAlchemy
- **Trading**: CCXT
- **Observability**: Langfuse
- **Package Manager**: uv

## 📝 License

MIT
