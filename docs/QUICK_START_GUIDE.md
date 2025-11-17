# Cortex 快速开始指南

**版本**: v1.0.0-rc1
**更新日期**: 2025-11-17

---

## 📋 目录

1. [系统要求](#系统要求)
2. [Docker 快速部署（推荐）](#docker-快速部署推荐)
3. [传统安装方式](#传统安装方式)
4. [验证安装](#验证安装)
5. [基本使用](#基本使用)
6. [常见问题](#常见问题)

---

## 系统要求

### 最低配置
- **操作系统**: Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+) 或 macOS
- **CPU**: 2 核心
- **内存**: 4GB RAM
- **磁盘**: 20GB 可用空间
- **网络**: 可访问互联网（需要调用 Claude API）

### 推荐配置
- **CPU**: 4 核心
- **内存**: 8GB RAM
- **磁盘**: 50GB 可用空间

### 必需软件
- **Docker 部署**: Docker 20.10+, Docker Compose 2.0+
- **传统安装**: Python 3.10+, Node.js 20+

---

## Docker 快速部署（推荐）

### 步骤 1: 安装 Docker

**Ubuntu/Debian**:
```bash
# 更新包索引
sudo apt-get update

# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装 Docker Compose
sudo apt-get install docker-compose-plugin

# 验证安装
docker --version
docker compose version
```

**macOS**:
```bash
# 使用 Homebrew 安装
brew install --cask docker

# 启动 Docker Desktop
open -a Docker
```

### 步骤 2: 获取 Cortex

```bash
# 克隆仓库
git clone https://github.com/wayfind/Cortex.git
cd Cortex

# 切换到 v1.0.0-rc1 版本
git checkout v1.0.0-rc1
```

### 步骤 3: 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
nano .env
```

**必须配置的环境变量**:
```bash
# Claude API 配置（必需）
ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# Monitor 配置
MONITOR_HOST=0.0.0.0
MONITOR_PORT=8000

# Probe 配置
PROBE_HOST=0.0.0.0
PROBE_PORT=8001

# 数据库配置（可选，默认使用 SQLite）
DATABASE_URL=sqlite:///./cortex.db

# Telegram 通知（可选）
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

### 步骤 4: 启动服务

**独立模式** (单节点):
```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看服务状态
docker-compose ps
```

**集群模式** (多 Probe 节点):
```bash
# 启动集群模式
docker-compose -f docker-compose.multi-probe.yml up -d

# 查看所有容器
docker ps
```

### 步骤 5: 访问服务

打开浏览器访问：

- **Web Dashboard**: http://localhost:3000
- **Monitor API**: http://localhost:8000/docs
- **Probe API**: http://localhost:8001/docs

---

## 传统安装方式

### 步骤 1: 安装 Python 依赖

```bash
# 克隆仓库
git clone https://github.com/wayfind/Cortex.git
cd Cortex
git checkout v1.0.0-rc1

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
.\venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### 步骤 2: 配置环境变量

```bash
# 快速设置（自动生成安全密钥）
python scripts/setup_env.py

# 或手动复制
cp .env.example .env

# 编辑配置
nano .env
```

**必须配置的环境变量**:
```bash
# Agent 配置
CORTEX_AGENT_ID=probe-001
CORTEX_AGENT_NAME=My Probe Node
CORTEX_AGENT_MODE=standalone

# Claude API（必需）
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
ANTHROPIC_MODEL=claude-sonnet-4

# Monitor 配置
CORTEX_MONITOR_HOST=0.0.0.0
CORTEX_MONITOR_PORT=8000
CORTEX_MONITOR_DATABASE_URL=sqlite:///./cortex.db

# Probe 配置
CORTEX_PROBE_HOST=0.0.0.0
CORTEX_PROBE_PORT=8001
CORTEX_PROBE_SCHEDULE=0 */6 * * *
CORTEX_PROBE_WORKSPACE=./probe_workspace

# 阈值配置
CORTEX_PROBE_THRESHOLD_CPU_PERCENT=80.0
CORTEX_PROBE_THRESHOLD_MEMORY_PERCENT=85.0
CORTEX_PROBE_THRESHOLD_DISK_PERCENT=90.0

# Intent Engine
CORTEX_INTENT_ENABLED=true
CORTEX_INTENT_DATABASE_URL=sqlite:///./cortex_intents.db

# Telegram 通知（可选）
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

> **提示**: 完整的配置选项请查看 `.env.example` 文件。

### 步骤 3: 安装前端依赖

```bash
cd frontend
npm install
npm run build
cd ..
```

### 步骤 4: 启动服务

**启动 Monitor**:
```bash
# 终端 1
python -m uvicorn cortex.monitor.app:app --host 0.0.0.0 --port 8000
```

**启动 Probe**:
```bash
# 终端 2
python -m uvicorn cortex.probe.app:app --host 0.0.0.0 --port 8001
```

**启动前端**:
```bash
# 终端 3
cd frontend
npm run dev
```

### 步骤 5: 使用 systemd（生产环境推荐）

```bash
# 复制 systemd 服务文件
sudo cp deployment/cortex-monitor.service /etc/systemd/system/
sudo cp deployment/cortex-probe.service /etc/systemd/system/

# 编辑服务文件，修改路径和用户
sudo nano /etc/systemd/system/cortex-monitor.service
sudo nano /etc/systemd/system/cortex-probe.service

# 重新加载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start cortex-monitor
sudo systemctl start cortex-probe

# 设置开机自启
sudo systemctl enable cortex-monitor
sudo systemctl enable cortex-probe

# 查看状态
sudo systemctl status cortex-monitor
sudo systemctl status cortex-probe
```

---

## 验证安装

### 1. 检查服务状态

**Docker 部署**:
```bash
# 查看容器状态
docker-compose ps

# 预期输出：
# cortex-monitor    running
# cortex-probe      running
# cortex-frontend   running
```

**传统部署**:
```bash
# 检查 Monitor
curl http://localhost:8000/health

# 检查 Probe
curl http://localhost:8001/health

# 预期返回：{"status": "healthy"}
```

### 2. 访问 Web 界面

打开浏览器访问 http://localhost:3000

**预期看到**:
- Dashboard 页面加载
- 显示节点状态（如果有注册的 Probe）
- 无明显错误信息

### 3. 查看 API 文档

- Monitor API: http://localhost:8000/docs
- Probe API: http://localhost:8001/docs

### 4. 测试手动巡检

```bash
# 通过 API 触发 Probe 巡检
curl -X POST http://localhost:8001/api/v1/probe/inspect \
  -H "Content-Type: application/json"

# 查看巡检结果
curl http://localhost:8001/api/v1/probe/reports
```

---

## 基本使用

### 1. 独立模式使用

独立模式下，Probe 和 Monitor 在同一节点运行，适合单机部署。

**查看节点状态**:
```bash
curl http://localhost:8000/api/v1/cluster/agents
```

**查看巡检报告**:
```bash
curl http://localhost:8000/api/v1/reports
```

**查看告警**:
```bash
curl http://localhost:8000/api/v1/alerts
```

### 2. 集群模式配置

**在子节点上配置 Probe**:

编辑 `.env`:
```bash
# Agent 配置
CORTEX_AGENT_ID=probe-child-001
CORTEX_AGENT_NAME=Child Probe Node
CORTEX_AGENT_MODE=cluster
CORTEX_AGENT_UPSTREAM_MONITOR_URL=http://parent-monitor-ip:8000
```

**子节点启动后会自动**:
1. 注册到父 Monitor
2. 开始定期心跳
3. 上报巡检结果

**在父节点查看集群拓扑**:
```bash
curl http://localhost:8000/api/v1/cluster/topology
```

### 3. 配置定时巡检

编辑 `.env`:
```bash
# 巡检调度配置
CORTEX_PROBE_SCHEDULE=0 */6 * * *   # 每6小时
# CORTEX_PROBE_SCHEDULE=0 0 * * *   # 每天午夜
# CORTEX_PROBE_SCHEDULE=0 */1 * * * # 每小时
```

重启 Probe 服务使配置生效：
```bash
# Docker 部署
docker-compose restart cortex-probe

# 传统部署
sudo systemctl restart cortex-probe
```

### 4. 配置告警通知

**Telegram Bot 设置**:

1. 与 @BotFather 创建 Bot 并获取 Token
2. 获取你的 Chat ID (使用 @userinfobot)
3. 编辑 `.env`:

```bash
# Telegram 通知配置
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

4. 重启 Monitor 服务：
```bash
# Docker 部署
docker-compose restart cortex-monitor

# 传统部署
sudo systemctl restart cortex-monitor
```

**测试通知**:
```bash
# 创建测试告警
curl -X POST http://localhost:8000/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "severity": "critical",
    "title": "Test Alert",
    "description": "This is a test alert",
    "agent_id": "test-agent"
  }'
```

### 5. 使用 Web Dashboard

访问 http://localhost:3000

**主要功能**:
- **Dashboard**: 查看集群概览、告警统计
- **Nodes**: 管理所有 Agent 节点
- **Alerts**: 查看和处理告警
- **Settings**: 配置 API 连接

---

## 常见问题

### Q1: Docker 容器无法启动

**检查日志**:
```bash
docker-compose logs cortex-monitor
docker-compose logs cortex-probe
```

**常见原因**:
1. 端口被占用：修改 `.env` 中的端口配置
2. API Key 未配置：检查 `ANTHROPIC_API_KEY`
3. 权限问题：使用 `sudo docker-compose up -d`

### Q2: Probe 无法连接到 Monitor

**检查网络**:
```bash
# 在 Probe 节点测试连接
curl http://monitor-host:8000/health
```

**解决方法**:
1. 检查防火墙设置
2. 验证 `monitor_url` 配置是否正确
3. 检查 Monitor 是否监听 0.0.0.0

### Q3: 巡检没有自动执行

**检查调度器状态**:
```bash
curl http://localhost:8001/api/v1/probe/schedule/status
```

**解决方法**:
1. 验证 cron 表达式格式
2. 查看 Probe 日志: `docker-compose logs cortex-probe`
3. 手动触发测试: `curl -X POST http://localhost:8001/api/v1/probe/inspect`

### Q4: Web Dashboard 无法访问

**检查前端容器**:
```bash
docker-compose logs cortex-frontend
```

**解决方法**:
1. 验证 3000 端口未被占用
2. 检查 `frontend/.env.development` 中的 API 地址
3. 清除浏览器缓存

### Q5: Claude API 调用失败

**检查 API Key**:
```bash
# 测试 API Key
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-sonnet-4",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "test"}]
  }'
```

**解决方法**:
1. 验证 API Key 有效性
2. 检查账户余额
3. 确认网络可以访问 api.anthropic.com

### Q6: 数据库错误

**SQLite 权限问题**:
```bash
# 检查数据库文件权限
ls -la cortex.db cortex_intents.db

# 修复权限
chmod 666 cortex.db cortex_intents.db
```

**迁移到 PostgreSQL**:

编辑 `.env`:
```bash
# 数据库配置
CORTEX_MONITOR_DATABASE_URL=postgresql://user:password@localhost:5432/cortex
CORTEX_INTENT_DATABASE_URL=postgresql://user:password@localhost:5432/cortex_intents
```

---

## 升级指南

### 从开发版本升级到 v1.0.0-rc1

```bash
# 1. 备份数据
cp cortex.db cortex.db.backup
cp cortex_intents.db cortex_intents.db.backup
cp .env .env.backup

# 2. 停止服务
docker-compose down
# 或
sudo systemctl stop cortex-monitor cortex-probe

# 3. 更新代码
git fetch --tags
git checkout v1.0.0-rc1

# 4. 更新依赖
docker-compose pull
# 或
pip install --upgrade -r requirements.txt
cd frontend && npm install && cd ..

# 5. 更新配置（检查 .env.example 的新配置项）
# 手动合并新配置项到 .env
# 或使用：python scripts/setup_env.py

# 6. 重启服务
docker-compose up -d
# 或
sudo systemctl start cortex-monitor cortex-probe
```

---

## 生产环境部署建议

### 1. 使用 PostgreSQL

生产环境建议使用 PostgreSQL 替代 SQLite。

编辑 `.env`:
```bash
# 数据库配置 - PostgreSQL
CORTEX_MONITOR_DATABASE_URL=postgresql://cortex:password@localhost:5432/cortex_prod
CORTEX_INTENT_DATABASE_URL=postgresql://cortex:password@localhost:5432/cortex_intents_prod
```

### 2. 配置反向代理

使用 Nginx 作为反向代理：

```nginx
# /etc/nginx/sites-available/cortex
server {
    listen 80;
    server_name cortex.example.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Monitor API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 3. 配置 HTTPS

```bash
# 使用 Let's Encrypt
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d cortex.example.com
```

### 4. 监控和日志

```bash
# 配置日志轮转
sudo cp deployment/logrotate.d/cortex /etc/logrotate.d/

# 设置监控告警（Prometheus + Grafana）
# 参考 v1.1.0 版本的监控功能
```

---

## 获取帮助

- **文档**: [docs/](../docs/)
- **GitHub Issues**: https://github.com/wayfind/Cortex/issues
- **API 文档**: http://localhost:8000/docs

---

## 下一步

- 阅读 [架构文档](./ARCHITECTURE_UPDATE.md) 了解系统设计
- 查看 [配置参考](./CONFIGURATION.md) 了解所有配置选项
- 参考 [故障排查指南](./TROUBLESHOOTING.md) 解决常见问题

---

**祝使用愉快！** 🎉

*Cortex Team - 2025-11-17*
