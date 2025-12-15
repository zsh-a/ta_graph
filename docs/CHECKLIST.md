# 生产部署清单

本文档提供完整的生产部署检查清单，确保系统安全、稳定地运行。

---

## ✅ 部署检查清单

### 📦 1. 环境变量配置

- [ ] **基础配置**
  - [ ] `.env`文件已创建（从`.env.example`复制）
  - [ ] 所有必填字段已填写
  - [ ] 敏感信息未提交到版本控制

- [ ] **交易所配置**
  ```ini
  EXCHANGE_NAME=bitget
  BITGET_API_KEY=<your_key>
  BITGET_API_SECRET=<your_secret>
  BITGET_API_PASSPHRASE=<your_passphrase>
  ```
  - [ ] API密钥权限正确（交易+查询，禁用提现）
  - [ ] IP白名单已设置
  - [ ] Passphrase已保存

- [ ] **模式设置**
  ```ini
  # ⚠️ 生产环境设置
  BITGET_SANDBOX=false
  TRADING_MODE=live
  ```
  - [ ] 沙盒测试完成后才设置为`false`
  - [ ] 确认使用真实资金

- [ ] **风险参数**
  ```ini
  MAX_POSITION_SIZE_PERCENT=5.0  # 建议≤5%
  DEFAULT_LEVERAGE=10            # 建议≤10x
  MAX_DAILY_LOSS_PERCENT=2.0
  MAX_CONSECUTIVE_LOSSES=3
  ```
  - [ ] 从保守参数开始
  - [ ] 根据回测结果调整

- [ ] **通知配置**
  ```ini
  TELEGRAM_BOT_TOKEN=<your_token>
  TELEGRAM_CHAT_ID=<your_chat_id>
  ```
  - [ ] Telegram bot已创建
  - [ ] 测试消息发送成功
  - [ ] 邮件通知已配置（可选）

- [ ] **日志配置**
  ```ini
  LOG_LEVEL=INFO
  STRUCTURED_LOGGING=true
  LOG_DIR=/var/log/trading
  ```
  - [ ] 日志目录存在且可写
  - [ ] 日志轮转已配置

### 🧪 2. 测试验证

- [ ] **功能测试**
  - [ ] 所有单元测试通过（`./run_tests.sh`）
  - [ ] 集成测试通过
  - [ ] 配置加载正常（`python -c "from src.config import load_config; load_config()"`）

- [ ] **沙盒测试**
  - [ ] 在测试网运行>=7天
  - [ ] 验证订单执行
  - [ ] 验证持仓管理
  - [ ] 验证风险控制
  - [ ] 验证资金保护器

- [ ] **API连接测试**
  ```bash
  python -c "from src.trading.exchange_client import get_client; \
             client = get_client('bitget'); \
             print(client.get_account_info())"
  ```
  - [ ] 连接成功
  - [ ] 获取账户信息
  - [ ] 获取市场数据

### 🔐 3. 安全检查

- [ ] **API安全**
  - [ ] 使用子账户（不是主账户）
  - [ ] API权限最小化
  - [ ] IP白名单启用
  - [ ] 定期更换密钥计划

- [ ] **服务器安全**
  - [ ] SSH密钥认证
  - [ ] 防火墙已配置
  - [ ] 自动更新已启用
  - [ ] 只开放必要端口

- [ ] **代码安全**
  - [ ] `.env`在`.gitignore`中
  - [ ] 无硬编码密钥
  - [ ] 依赖包已更新
  - [ ] 敏感日志已过滤

### 📊 4. 监控系统

- [ ] **日志监控**
  - [ ] 日志目录已创建
  - [ ] 日志权限正确
  - [ ] 日志轮转配置完成
  - [ ] 错误日志已测试

- [ ] **仪表盘**（可选）
  - [ ] 仪表盘可访问
  - [ ] 指标正常显示
  - [ ] 实时更新工作

- [ ] **追踪系统**
  - [ ] Langfuse已配置
  - [ ] 追踪正常记录
  - [ ] 可以查看历史

- [ ] **告警系统**
  - [ ] Telegram通知测试
  - [ ] 邮件通知测试
  - [ ] 关键事件告警启用

### 🚀 5. 部署执行

- [ ] **服务器准备**
  - [ ] 满足最低配置要求
  - [ ] Python 3.11+已安装
  - [ ] uv已安装
  - [ ] 系统依赖已安装

- [ ] **代码部署**
  - [ ] 代码已克隆/同步
  - [ ] 依赖已安装（`uv sync`）
  - [ ] 权限已设置
  - [ ] 目录结构正确

- [ ] **服务配置**
  - [ ] Systemd服务文件已创建
  - [ ] 服务已启用
  - [ ] 日志路径正确
  - [ ] 自动重启已配置

- [ ] **启动验证**
  - [ ] 服务成功启动
  - [ ] 无错误日志
  - [ ] 心跳监控正常
  - [ ] 仪表盘可访问

### 📝 6. 文档和备份

- [ ] **文档**
  - [ ] 部署文档已阅读
  - [ ] API文档已准备
  - [ ] 故障排查指南可用
  - [ ] 联系方式已记录

- [ ] **备份**
  - [ ] 配置文件已备份
  - [ ] 初始状态已记录
  - [ ] 恢复流程已测试
  - [ ] 数据备份策略制定

### 🔧 7. 运维准备

- [ ] **监控计划**
  - [ ] 每日检查清单
  - [ ] 每周审查计划
  - [ ] 每月总结流程

- [ ] **应急预案**
  - [ ] 紧急停止流程
  - [ ] 联系方式列表
  - [ ] 备用方案准备
  - [ ] 回滚步骤已知

- [ ] **维护计划**
  - [ ] 更新策略制定
  - [ ] 参数调整流程
  - [ ] 性能优化计划
  - [ ] 日志清理策略

---

## 🎯 部署后验证

### 立即检查（前5分钟）

```bash
# 1. 检查服务状态
sudo systemctl status trading-bot

# 2. 查看启动日志
tail -f /var/log/trading/trading_$(date +%Y%m%d).log

# 3. 验证心跳
grep "Heartbeat" /var/log/trading/trading_$(date +%Y%m%d).log | tail -5

# 4. 检查仪表盘
curl http://localhost:8000/api/metrics
```

- [ ] 服务running状态
- [ ] 无ERROR日志
- [ ] 心跳正常
- [ ] 仪表盘响应

### 首小时检查

```bash
# 1. 检查市场数据获取
grep "market_data" /var/log/trading/trading_$(date +%Y%m%d).log

# 2. 检查AI分析
grep "brooks_analyzer" /var/log/trading/trading_$(date +%Y%m%d).log

# 3. 检查资金保护器
grep "Equity Protector" /var/log/trading/trading_$(date +%Y%m%d).log

# 4. 监控系统资源
top -p $(pgrep -f "python main.py")
```

- [ ] 数据正常获取
- [ ] AI分析正常
- [ ] 无资金保护触发（除非应该）
- [ ] CPU/内存正常

### 首日检查

```bash
# 1. 查看交易记录
cat /var/log/trading/trades/trades_$(date +%Y%m%d).jsonl

# 2. 检查错误统计
wc -l /var/log/trading/errors.log

# 3. 查看性能指标
tail -50 /var/log/trading/metrics/metrics.jsonl

# 4. 审查所有通知
# 检查Telegram/Email
```

- [ ] 交易逻辑正确
- [ ] 错误可控
- [ ] 性能正常
- [ ] 通知及时

---

## ⚠️ 严重问题处理

### 立即停止条件

**以下任一情况出现，立即停止系统：**

1. ❌ 连续亏损超过预期
2. ❌ 异常订单（价格/数量错误）
3. ❌ API连接持续失败
4. ❌ 资金保护器失效
5. ❌ 系统频繁崩溃

**停止命令：**
```bash
sudo systemctl stop trading-bot
```

### 紧急联系

- 交易所客服
- 技术支持
- 团队成员

---

## ✨ 最佳实践

### 渐进式部署

1. **Week 1**: 最小仓位（1%）
2. **Week 2-3**: 小仓位（3%） 
3. **Month 2**: 中等仓位（5%）
4. **Month 3+**: 根据表现调整

### 持续优化

- 每周审查交易记录
- 每月分析胜率/PnL
- 季度策略回顾
- 定期参数调整

### 风险控制

- 严格止损
- 分散品种
- 控制杠杆
- 定期提现

---

## 📞 支持资源

- **文档**: [README.md](../README.md), [DEPLOYMENT.md](./DEPLOYMENT.md)
- **测试**: [Testing Report](../brain/testing_report.md)
- **规划**: [Implementation Plan](../brain/position_management_plan.md)

---

## ✍️ 签名确认

**部署负责人**: _________________  
**日期**: _________________  
**审核人**: _________________  
**日期**: _________________  

**声明**: 我确认已完成所有检查项，理解系统风险，并对部署负责。

---

**祝交易顺利！记住：小仓位起步，持续优化！** 🚀
