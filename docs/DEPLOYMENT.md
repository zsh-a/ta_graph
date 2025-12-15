# 生产部署指南

本文档提供完整的生产部署步骤和最佳实践。

## 📋 部署前检查清单

### 必须完成

- [ ] **API密钥配置**
  - [ ] Bitget API密钥已创建
  - [ ] API密钥权限正确（交易+查询，禁用提现）
  - [ ] IP白名单已设置
  - [ ] Passphrase已保存

- [ ] **沙盒测试**
  - [ ] 在测试网完整运行至少7天
  - [ ] 验证所有功能正常
  - [ ] 无严重错误或崩溃
  - [ ] 资金保护机制生效

- [ ] **配置验证**
  - [ ] `.env`文件已正确配置
  - [ ] 杠杆设置合理（建议≤10x）
  - [ ] 仓位限制合理（建议≤5%）
  - [ ] 止损参数正确

- [ ] **通知系统**
  - [ ] Telegram或Email已配置
  - [ ] 测试通知发送成功

- [ ] **监控系统**
  - [ ] 日志目录可写
  - [ ] 仪表盘可访问
  - [ ] Langfuse追踪正常

### 建议完成

- [ ] 准

备应急联系方式
- [ ] 制定交易计划和退出策略
- [ ] 设置账户资金警报
- [ ] 配置服务器监控（CPU/内存/网络）

---

## 🚀 部署步骤

### 1. 服务器准备

#### 最低配置
```
CPU: 2核
内存: 4GB
存储: 20GB SSD
网络: 稳定的互联网连接
系统: Ubuntu 20.04+ / CentOS 8+
```

#### 推荐配置
```
CPU: 4核
内存: 8GB
存储: 50GB SSD
网络: 低延迟专线
系统: Ubuntu 22.04 LTS
```

### 2. 环境安装

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Python 3.11+
sudo apt install python3.11 python3.11-venv python3-pip -y

# 安装uv（包管理器）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装Git
sudo apt install git -y

# 安装系统依赖
sudo apt install build-essential libssl-dev libffi-dev -y
```

### 3. 克隆项目

```bash
# 克隆代码
git clone <your-repo-url> /opt/trading
cd /opt/trading

# 创建虚拟环境
uv sync
```

### 4. 配置环境变量

```bash
# 复制模板
cp .env.example .env

# 编辑配置（使用你喜欢的编辑器）
nano .env
```

**关键配置项：**

```ini
# ========== 交易所配置 ==========
EXCHANGE_NAME=bitget
BITGET_API_KEY=<your_api_key>
BITGET_API_SECRET=<your_api_secret>
BITGET_API_PASSPHRASE=<your_passphrase>

# ⚠️ 生产环境设置
BITGET_SANDBOX=false
TRADING_MODE=live

# ========== 风险控制 ==========
# 建议从小仓位开始
MAX_POSITION_SIZE_PERCENT=5.0
DEFAULT_LEVERAGE=10
MAX_DAILY_LOSS_PERCENT=2.0
MAX_CONSECUTIVE_LOSSES=3

# ========== 通知 ==========
TELEGRAM_BOT_TOKEN=<your_telegram_token>
TELEGRAM_CHAT_ID=<your_chat_id>

# ========== 日志 ==========
LOG_LEVEL=INFO
STRUCTURED_LOGGING=true
LOG_DIR=/var/log/trading
```

### 5. 创建日志目录

```bash
sudo mkdir -p /var/log/trading
sudo chown $USER:$USER /var/log/trading

# 创建数据目录
mkdir -p /opt/trading/data
mkdir -p /opt/trading/checkpoints
```

### 6. 验证配置

```bash
# 测试配置加载
python -c "from src.config import load_config; config = load_config(); print('Config OK')"

# 测试Exchange连接
python -c "from src.trading.exchange_client import get_client; client = get_client('bitget'); print(client.get_account_info())"
```

### 7. 系统服务配置（Systemd）

创建服务文件：

```bash
sudo nano /etc/systemd/system/trading-bot.service
```

内容：

```ini
[Unit]
Description=Al Brooks Trading Bot
After=network.target

[Service]
Type=simple
User=<your_user>
WorkingDirectory=/opt/trading
Environment="PATH=/opt/trading/.venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/opt/trading/.venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/trading/stdout.log
StandardError=append:/var/log/trading/stderr.log

# 安全设置
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
```

### 8. 监控服务

```bash
# 查看状态
sudo systemctl status trading-bot

# 查看日志
sudo journalctl -u trading-bot -f

# 查看应用日志
tail -f /var/log/trading/trading_*.log
```

---

## 📊 监控和维护

### 实时监控

#### 1. 仪表盘

访问 `http://your-server:8000` 查看实时仪表盘（如果启用）

#### 2. 日志监控

```bash
# 实时查看日志
tail -f /var/log/trading/trading_$(date +%Y%m%d).log

# 查看错误日志
tail -f /var/log/trading/errors.log

# 查看交易日志
tail -f /var/log/trading/trades/trades_$(date +%Y%m%d).jsonl
```

#### 3. Langfuse追踪

访问 https://cloud.langfuse.com 查看：
- AI模型调用记录
- 决策路径分析
- 性能指标

### 日常维护

#### 每日检查

```bash
# 检查服务状态
sudo systemctl status trading-bot

# 查看今日交易
grep "ENTRY\|EXIT" /var/log/trading/trades/trades_$(date +%Y%m%d).jsonl

# 检查资金保护器状态
grep "Equity Protector" /var/log/trading/trading_$(date +%Y%m%d).log | tail -5
```

#### 每周检查

- 审查交易记录和P&L
- 检查系统资源使用（CPU/内存/磁盘）
- 更新依赖包（如有安全更新）
- 备份配置和日志

#### 每月检查

- 分析策略表现
- 调整参数（如需要）
- 审查错误日志
- 更新文档

### 日志轮转

配置logrotate：

```bash
sudo nano /etc/logrotate.d/trading-bot
```

内容：

```
/var/log/trading/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 <your_user> <your_user>
    sharedscripts
    postrotate
        systemctl reload trading-bot > /dev/null 2>&1 || true
    endscript
}
```

---

## 🚨 故障排查

### 常见问题

#### 1. 服务无法启动

```bash
# 查看详细错误
sudo journalctl -u trading-bot -n 50 --no-pager

# 检查配置
python -c "from src.config import load_config; load_config()"

# 检查权限
ls -la /var/log/trading
```

#### 2. API连接失败

```bash
# 测试网络
ping api.bitget.com

# 检查API密钥
python -c "from src.trading.exchange_client import get_client; get_client('bitget').get_account_info()"

# 检查IP白名单
curl https://api.ipify.org
```

#### 3. 交易未执行

- 检查资金保护器是否触发
- 检查Conviction Tracker
- 检查TTR检测
-查看决策日志

#### 4. 内存泄漏

```bash
# 监控内存
watch -n 5 'free -h && ps aux | grep python | grep -v grep'

# 重启服务
sudo systemctl restart trading-bot
```

### 紧急停止

```bash
# 立即停止
sudo systemctl stop trading-bot

# 取消所有订单（手动）
# 登录交易所网页平台操作
```

---

## 🔐 安全最佳实践

### API安全

1. **最小权限原则**
   - ✅ 启用：交易、查询
   - ❌ 禁用：提现、转账

2. **IP白名单**
   - 仅允许服务器IP访问
   - 定期审查IP列表

3. **密钥管理**
   - 使用环境变量，不要硬编码
   - 定期轮换密钥（建议每3个月）
   - 将`.env`加入`.gitignore`

### 服务器安全

1. **防火墙**
```bash
sudo ufw allow ssh
sudo ufw allow 8000/tcp  # 仪表盘（可选）
sudo ufw enable
```

2. **SSH密钥认证**
```bash
# 禁用密码登录
sudo nano /etc/ssh/sshd_config
# PasswordAuthentication no
sudo systemctl restart sshd
```

3. **自动更新**
```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 资金安全

1. **分离账户**
   - 使用独立交易账户
   - 不要在主账户运行机器人

2. **限制资金**
   - 初始资金≤总资产的20%
   - 设置严格的止损

3. **监控异常**
   - 配置余额警报
   - 监控异常交易

---

## 📈 性能优化

### 1. 数据库优化（如使用）

```bash
# 定期清理旧数据
find /opt/trading/data -name "*.db" -mtime +90 -delete
```

### 2. 日志优化

```ini
# .env 设置
LOG_LEVEL=INFO  # 避免DEBUG级别
STRUCTURED_LOGGING=true  # JSON格式更高效
```

### 3. 网络优化

- 使用低延迟VPS
- 选择靠近交易所服务器的地区
- 考虑使用专线

---

## 🔄 升级流程

```bash
# 1. 备份
cp -r /opt/trading /opt/trading.backup.$(date +%Y%m%d)

# 2. 停止服务
sudo systemctl stop trading-bot

# 3. 拉取更新
cd /opt/trading
git pull origin main

# 4. 更新依赖
uv sync

# 5. 运行测试
PYTHONPATH=. uv run pytest tests/ -v

# 6. 启动服务
sudo systemctl start trading-bot

# 7. 验证
sudo systemctl status trading-bot
tail -f /var/log/trading/trading_$(date +%Y%m%d).log
```

---

## 📞 支持和资源

### 文档
- [README.md](../README.md) - 快速开始
- [Implementation Plan](../brain/position_management_plan.md) - 实施计划
- [Testing Report](../brain/testing_report.md) - 测试报告

### 社区
- GitHub Issues: 报告问题
- Discussions: 提问和讨论

### 应急联系
- 保持Telegram通知开启
- 准备好交易所客服联系方式

---

## ⚠️ 免责声明

本系统仅供学习和研究使用。量化交易存在风险，可能导致资金损失。

- 用户需自行承担所有交易风险
- 建议从小仓位开始测试
- 充分了解市场风险后再使用
- 定期审查和调整策略

**投资有风险，入市需谨慎！**
