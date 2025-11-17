# Cortex 安装指南

本文档提供 Cortex 的详细安装步骤和配置说明。

## 安装方式选择

Cortex 提供三种安装方式：

| 方式 | 适用场景 | 难度 | 推荐度 |
|------|---------|------|--------|
| **Docker Compose** | 快速部署、生产环境 | ⭐ | ⭐⭐⭐⭐⭐ |
| **一键安装脚本** | 传统 Linux 服务器 | ⭐⭐ | ⭐⭐⭐⭐ |
| **手动安装** | 开发环境、自定义部署 | ⭐⭐⭐ | ⭐⭐⭐ |

## 方式 1: Docker Compose 部署（推荐）

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 2GB+ RAM
- 10GB+ 可用磁盘空间

### 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/cortex.git
cd cortex

# 2. 配置环境变量
cp .env.example .env
vim .env  # 编辑必需的配置项

# 3. 启动服务
docker-compose up -d

# 4. 验证部署
curl http://localhost:8000/health
curl http://localhost:8001/health
```

### 必需配置

编辑 `.env` 文件，至少配置以下项：

```bash
# Claude API Key (必需)
ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# 节点注册密钥 (必需，生成随机字符串)
CORTEX_MONITOR_REGISTRATION_TOKEN=$(openssl rand -hex 32)

# JWT 密钥 (必需，至少 32 字符)
CORTEX_AUTH_SECRET_KEY=$(openssl rand -base64 32)
```

详细配置请参考 [Docker 部署指南](./DOCKER_DEPLOYMENT.md)。

## 方式 2: 一键安装脚本

### 支持的系统

- Ubuntu 20.04 / 22.04 LTS
- Debian 11 / 12
- CentOS 7 / 8
- RHEL 8 / 9
- Rocky Linux 8 / 9
- AlmaLinux 8 / 9

### 安装步骤

```bash
# 下载并执行安装脚本
curl -fsSL https://raw.githubusercontent.com/yourusername/cortex/main/scripts/install.sh | sudo bash

# 或者先下载再执行
wget https://raw.githubusercontent.com/yourusername/cortex/main/scripts/install.sh
chmod +x install.sh
sudo ./install.sh
```

### 脚本功能

安装脚本会自动完成以下操作：

1. ✅ 检测操作系统
2. ✅ 安装依赖（Python 3.11, Git, curl）
3. ✅ 可选安装 Docker
4. ✅ 创建系统用户 `cortex`
5. ✅ 克隆代码仓库
6. ✅ 安装 Python 应用
7. ✅ 创建必要目录
8. ✅ 交互式配置向导
9. ✅ 安装 systemd 服务
10. ✅ 启动并验证服务

### 安装后验证

```bash
# 检查服务状态
sudo systemctl status cortex-monitor
sudo systemctl status cortex-probe

# 查看日志
sudo journalctl -u cortex-monitor -f

# 测试 API
curl http://localhost:8000/health
```

## 方式 3: 手动安装

### 前置要求

- Python 3.11+
- Git
- pip / Poetry
- systemd（可选）

### 步骤 1: 安装系统依赖

**Ubuntu / Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    curl
```

**CentOS / RHEL:**
```bash
sudo yum install -y \
    python3.11 \
    python3-pip \
    git \
    curl
```

### 步骤 2: 克隆代码

```bash
# 创建安装目录
sudo mkdir -p /opt/cortex
sudo chown $USER:$USER /opt/cortex

# 克隆仓库
git clone https://github.com/yourusername/cortex.git /opt/cortex
cd /opt/cortex
```

### 步骤 3: 创建虚拟环境

```bash
# 创建虚拟环境
python3.11 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 升级 pip
pip install --upgrade pip
```

### 步骤 4: 安装依赖

```bash
# 方式 A: 使用 pip (推荐)
pip install -e .

# 方式 B: 使用 requirements.txt
pip install -r requirements.txt
```

### 步骤 5: 配置应用

```bash
# 复制配置示例
cp config.example.yaml config.yaml

# 编辑配置文件
vim config.yaml
```

最小配置示例：

```yaml
agent:
  id: "agent-001"
  name: "Cortex Agent"
  mode: "standalone"

probe:
  host: "0.0.0.0"
  port: 8001
  schedule: "0 * * * *"

monitor:
  host: "0.0.0.0"
  port: 8000
  database_url: "sqlite:///./cortex.db"
  registration_token: "your-secret-token-here"

claude:
  api_key: "sk-ant-your-api-key-here"
  model: "claude-sonnet-4"

logging:
  level: "INFO"
  format: "standard"
  file: "logs/cortex.log"
```

### 步骤 6: 初始化数据库

```bash
# 创建数据库目录
mkdir -p data logs probe_workspace/output

# 运行数据库迁移（如果需要）
# alembic upgrade head
```

### 步骤 7: 启动服务

**开发模式（前台运行）：**

```bash
# 启动 Monitor
python -m cortex.monitor.cli

# 启动 Probe（另一个终端）
python -m cortex.probe.cli
```

**生产模式（systemd 服务）：**

```bash
# 复制 systemd 服务文件
sudo cp deployment/cortex-monitor.service /etc/systemd/system/
sudo cp deployment/cortex-probe.service /etc/systemd/system/

# 编辑服务文件，修改路径
sudo vim /etc/systemd/system/cortex-monitor.service

# 重新加载 systemd
sudo systemctl daemon-reload

# 启用并启动服务
sudo systemctl enable cortex-monitor cortex-probe
sudo systemctl start cortex-monitor cortex-probe

# 检查状态
sudo systemctl status cortex-monitor
sudo systemctl status cortex-probe
```

### 步骤 8: 验证安装

```bash
# 检查 Monitor 健康状态
curl http://localhost:8000/health

# 检查 Probe 健康状态
curl http://localhost:8001/health

# 查看 API 文档
xdg-open http://localhost:8000/docs

# 检查日志
tail -f logs/cortex.log
```

## 前端部署

### 开发模式

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 生产模式

```bash
cd frontend
npm install
npm run build

# 使用 nginx 或其他 Web 服务器托管 dist/ 目录
```

## 集群模式部署

### 架构

```
┌─────────────┐
│   Monitor   │ (主节点)
│  (Port 8000)│
└──────┬──────┘
       │
       ├─────────────┬─────────────┐
       │             │             │
┌──────▼──────┐ ┌───▼──────┐ ┌───▼──────┐
│   Probe 1   │ │ Probe 2  │ │ Probe 3  │
│ (Port 8001) │ │(Port 8001│ │(Port 8001│
└─────────────┘ └──────────┘ └──────────┘
```

### Monitor 节点配置

```yaml
agent:
  id: "monitor-main"
  name: "Main Monitor"
  mode: "standalone"  # 作为根节点

monitor:
  host: "0.0.0.0"
  port: 8000
  registration_token: "your-secret-token"
```

### Probe 节点配置

```yaml
agent:
  id: "probe-node-01"
  name: "Probe Node 01"
  mode: "cluster"
  upstream_monitor_url: "http://monitor.example.com:8000"

probe:
  host: "0.0.0.0"
  port: 8001
```

### 注册 Probe 到 Monitor

Probe 启动后会自动向 Monitor 注册，确保：

1. `upstream_monitor_url` 可访问
2. 使用正确的 `registration_token`
3. 网络策略允许通信

## 配置 Claude Code CLI

Probe 需要 `claude` 命令来执行巡检：

```bash
# 安装 Claude Code CLI
# 参考: https://claude.com/code

# 验证安装
claude --version

# 确保 claude 在 PATH 中
which claude
```

## 环境变量参考

所有配置项都可以通过环境变量覆盖：

```bash
# Agent 配置
export CORTEX_AGENT_ID="agent-001"
export CORTEX_AGENT_NAME="Cortex Agent"
export CORTEX_AGENT_MODE="standalone"

# Monitor 配置
export CORTEX_MONITOR_HOST="0.0.0.0"
export CORTEX_MONITOR_PORT=8000
export CORTEX_MONITOR_DATABASE_URL="sqlite:///./cortex.db"
export CORTEX_MONITOR_REGISTRATION_TOKEN="your-token"

# Probe 配置
export CORTEX_PROBE_HOST="0.0.0.0"
export CORTEX_PROBE_PORT=8001
export CORTEX_PROBE_SCHEDULE="0 * * * *"

# Claude API
export ANTHROPIC_API_KEY="sk-ant-your-key"
export ANTHROPIC_MODEL="claude-sonnet-4"

# 日志配置
export CORTEX_LOG_LEVEL="INFO"
export CORTEX_LOG_FORMAT="standard"
export CORTEX_LOG_FILE="logs/cortex.log"
```

详细配置参考：[配置文档](./CONFIGURATION.md)

## 故障排查

### 常见问题

#### 1. 端口被占用

```bash
# 检查端口占用
sudo netstat -tuln | grep -E ':(8000|8001)'

# 修改配置中的端口
vim config.yaml
```

#### 2. 数据库权限错误

```bash
# 检查文件权限
ls -la cortex.db

# 修复权限
chmod 644 cortex.db
chown cortex:cortex cortex.db
```

#### 3. Claude API Key 无效

```bash
# 测试 API Key
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-sonnet-4",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

#### 4. 服务无法启动

```bash
# 查看详细日志
journalctl -u cortex-monitor -n 50
journalctl -u cortex-probe -n 50

# 手动启动调试
/opt/cortex/venv/bin/python -m cortex.monitor.cli --log-level DEBUG
```

#### 5. 集群节点无法注册

检查：
- Monitor 服务是否运行
- 网络连接是否正常
- `registration_token` 是否正确
- 防火墙是否允许连接

更多故障排查：[故障排查指南](./TROUBLESHOOTING.md)

## 升级指南

### Docker 部署

```bash
# 停止服务
docker-compose down

# 拉取最新代码
git pull

# 重新构建并启动
docker-compose up -d --build
```

### 手动部署

```bash
# 停止服务
sudo systemctl stop cortex-monitor cortex-probe

# 拉取最新代码
cd /opt/cortex
git pull

# 更新依赖
source venv/bin/activate
pip install -e .

# 运行数据库迁移（如需要）
# alembic upgrade head

# 重启服务
sudo systemctl start cortex-monitor cortex-probe
```

## 卸载

### Docker 部署

```bash
# 停止并删除容器
docker-compose down

# 删除卷（⚠️ 会删除所有数据）
docker-compose down -v

# 删除镜像
docker rmi cortex-monitor cortex-probe cortex-frontend
```

### 手动部署

```bash
# 停止服务
sudo systemctl stop cortex-monitor cortex-probe
sudo systemctl disable cortex-monitor cortex-probe

# 删除 systemd 服务文件
sudo rm /etc/systemd/system/cortex-*.service
sudo systemctl daemon-reload

# 删除应用文件
sudo rm -rf /opt/cortex

# 删除配置文件
sudo rm -rf /etc/cortex

# 删除用户（可选）
sudo userdel cortex
```

## 下一步

- 📖 [配置参考](./CONFIGURATION.md) - 详细配置说明
- 📖 [用户手册](./USER_GUIDE.md) - 使用指南
- 📖 [API 文档](http://localhost:8000/docs) - REST API 参考
- 📖 [架构文档](./ARCHITECTURE.md) - 系统架构说明
- 📖 [开发指南](./CONTRIBUTING.md) - 参与开发

## 获取帮助

- 🐛 [GitHub Issues](https://github.com/yourusername/cortex/issues)
- 💬 [Discussions](https://github.com/yourusername/cortex/discussions)
- 📧 Email: support@example.com
