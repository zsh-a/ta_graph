# Docker 部署指南

## 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+

## Troubleshooting

### Common Issues

**1. UV Command Not Found**

**Problem**: `/bin/sh: 1: uv: not found` during build

**Solution**: UV installs to `/root/.local/bin`, ensure PATH is set correctly:
```dockerfile
ENV PATH="/root/.local/bin:$PATH"
```

**2. Permission Denied**

### 一键启动

```bash
# 1. 编辑环境变量
cp .env.example .env
vim .env  # 填入API密钥

# 2. 启动系统
./scripts/docker-helper.sh start

# 3. 查看日志
./scripts/docker-helper.sh logs
```

## 便捷脚本使用

`scripts/docker-helper.sh` 提供了以下命令：

| 命令 | 说明 |
|------|------|
| `start` | 启动交易系统 |
| `stop` | 停止交易系统 |
| `restart` | 重启交易系统 |
| `logs` | 查看实时日志 |
| `build` | 构建Docker镜像 |
| `rebuild` | 重新构建并启动 |
| `status` | 查看容器状态 |
| `shell` | 进入容器Shell |
| `clean` | 清理容器和系统 |
| `backup` | 备份数据 |
| `health` | 健康检查 |

**示例:**

```bash
# 启动
./scripts/docker-helper.sh start

# 查看日志
./scripts/docker-helper.sh logs

# 健康检查
./scripts/docker-helper.sh health

# 停止
./scripts/docker-helper.sh stop
```

## 环境变量配置

在 `.env` 文件中配置以下变量：

```bash
# Bitget API（必需）
BITGET_API_KEY=your_api_key
BITGET_SECRET=your_secret
BITGET_PASSWORD=your_password

# ModelScope API（必需）
MODELSCOPE_API_KEY=your_key

# 交易配置（可选）
PRIMARY_TIMEFRAME=1h
TRADING_SYMBOL=BTC/USDT

# Dashboard（可选）
ENABLE_DASHBOARD_SERVER=false
DASHBOARD_PORT=8000
```

## 数据持久化

以下目录会自动映射到宿主机：

- `./data` - SQLite数据库
- `./logs` - 日志文件
- `./charts` - K线图表

**备份数据：**

```bash
# 使用脚本备份
./scripts/docker-helper.sh backup

# 手动备份
tar czf backup.tar.gz data/ logs/ charts/
```

## 健康检查

Docker自动执行健康检查：

- **间隔**: 60秒
- **超时**: 10秒
- **启动延迟**: 30秒
- **重试次数**: 3次

查看健康状态：

```bash
docker-compose ps
# 或
./scripts/docker-helper.sh health
```

## 资源限制

默认资源配置：

- **CPU限制**: 2核
- **内存限制**: 2GB
- **CPU预留**: 1核
- **内存预留**: 1GB

修改 `docker-compose.yml` 调整资源限制。

## 日志管理

### 查看日志

```bash
# 实时日志（最后100行）
./scripts/docker-helper.sh logs

# 查看所有日志
docker-compose logs trading-system

# 导出日志
docker-compose logs trading-system > system.log
```

### 日志轮转

宿主机日志文件位于 `./logs/`，建议配置logrotate：

```bash
# /etc/logrotate.d/ta-graph
/home/user/ta_graph/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

## 故障排查

### 容器无法启动

```bash
# 查看详细日志
docker-compose logs trading-system

# 检查配置语法
docker-compose config

# 重新构建
./scripts/docker-helper.sh rebuild
```

### 权限问题

```bash
# 修复数据目录权限
sudo chown -R 1000:1000 ./data ./logs ./charts
```

### 时间同步问题

```bash
# 检查容器时间
docker-compose exec trading-system date

# 如果不一致，重启Docker守护进程
sudo systemctl restart docker
```

## 高级配置

### 自定义构建

```bash
# 使用自定义Dockerfile
docker-compose build --build-arg PYTHON_VERSION=3.13

# 无缓存构建
docker-compose build --no-cache
```

### 网络配置

默认使用桥接网络 `trading_network`。需要自定义网络时，编辑 `docker-compose.yml`。

### 多实例部署

运行多个交易对实例：

```bash
# 复制配置
cp docker-compose.yml docker-compose-eth.yml

# 编辑配置文件，修改：
# - container_name
# - TRADING_SYMBOL
# - 端口映射

# 启动第二个实例
docker-compose -f docker-compose-eth.yml up -d
```

## 生产环境部署

### systemd 集成

创建 `/etc/systemd/system/ta-graph.service`:

```ini
[Unit]
Description=TA Graph Trading System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/ta_graph
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

启用开机自启：

```bash
sudo systemctl enable ta-graph
sudo systemctl start ta-graph
```

### 监控集成

添加Prometheus监控（未来扩展）：

```yaml
# 添加到 docker-compose.yml
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
```

## 安全建议

1. **使用非root用户** - 容器默认以UID 1000运行
2. **保护.env文件** - `chmod 600 .env`
3. **定期更新镜像** - `docker-compose pull && docker-compose up -d`
4. **限制网络访问** - 仅暴露必要端口
5. **定期备份数据** - 使用 `docker-helper.sh backup`

## 卸载

完全移除系统：

```bash
# 停止并删除容器、卷
./scripts/docker-helper.sh clean

# 删除镜像
docker rmi ta_graph_trading-system

# 删除数据（谨慎！）
rm -rf data/ logs/ charts/
```

## 技术细节

### UV 依赖管理

本项目使用 [uv](https://github.com/astral-sh/uv) 进行依赖管理，相比pip有以下优势：

- ⚡ **10-100x 更快**的安装速度
- 🔒 **锁定文件** (`uv.lock`) 确保可重现构建
- 📦 **更小的镜像**体积

### 多阶段构建

Dockerfile使用3个阶段优化：

1. **base** - 安装系统依赖和uv
2. **dependencies** - 使用uv安装Python依赖
3. **application** - 复制代码和依赖，创建最终镜像

这种方式可以：
- 减少最终镜像大小
- 利用Docker层缓存加速构建
- 隔离构建依赖

---

## 常见问题

**Q: 如何更新到最新代码？**

```bash
git pull
./scripts/docker-helper.sh rebuild
```

**Q: 如何查看容器内文件？**

```bash
./scripts/docker-helper.sh shell
# 或
docker-compose exec trading-system ls -la /app/data
```

**Q: Dashboard无法访问？**

确保：
1. `.env` 中设置 `ENABLE_DASHBOARD_SERVER=true`
2. `docker-compose.yml` 已映射端口
3. 重启容器: `./scripts/docker-helper.sh restart`

---

## 相关文档

- [主README](README.md)
- [数据库文档](README_DATABASE.md)
- [Docker官方文档](https://docs.docker.com/)
- [UV文档](https://github.com/astral-sh/uv)
