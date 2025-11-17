# Cortex

**去中心化、分级自治的智能运维网络**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-v1.0.0--rc1-blue)](https://github.com/cortex-ops/cortex/releases/tag/v1.0.0-rc1)
[![Tests](https://img.shields.io/badge/tests-196%20passed-brightgreen)](./tests/)
[![Coverage](https://img.shields.io/badge/coverage-61%25-yellow)](./htmlcov/)

## 概述

Cortex 是一个创新的智能运维系统，每个节点都是一个独立的 Agent，可以动态组合成具备集体智能的运维集群。系统通过 LLM 技术实现自主决策和自动修复，大幅减少人工干预。

### 核心特性

- 🤖 **混合智能**：每个 Agent 内置执行单元（Probe）和决策单元（Monitor）
- 🌐 **动态层级**：支持多层嵌套集群，形成复杂的运维网络拓扑
- 🔄 **自主闭环**：完整的"发现-分析-决策-执行-验证"自主运维循环
- 📊 **意图可追溯**：所有操作通过 Intent-Engine 记录，完整审计轨迹
- ⚡ **智能决策**：基于 Claude 的 L2 级风险分析和决策支持
- 🔔 **智能告警**：L3 级告警聚合、去重和关联分析

## 快速开始

### 🐳 方式 1: Docker Compose（推荐）

最快的部署方式，无需安装依赖：

```bash
# 1. 克隆仓库
git clone https://github.com/cortex-ops/cortex.git
cd cortex

# 2. 配置环境变量
cp .env.example .env
vim .env  # 编辑 ANTHROPIC_API_KEY 等必需配置

# 3. 启动所有服务
docker-compose up -d

# 4. 访问服务
# Web UI: http://localhost:3000
# Monitor API: http://localhost:8000
# Probe API: http://localhost:8001
```

详细说明请参考 [Docker 部署指南](./docs/DOCKER_DEPLOYMENT.md)。

### 📦 方式 2: 传统安装

#### 环境要求

**Monitor**：
- Python 3.10+
- SQLite 3.40+ (或 PostgreSQL 13+)
- Claude API Key

**Probe（新版文档驱动）**：
- Python 3.10+
- [Claude Code](https://code.claude.com) CLI
- 系统工具：bash, cron

#### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/cortex-ops/cortex.git
cd cortex

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 安装开发依赖（可选）
pip install -e ".[dev]"
```

### 配置

Cortex 使用 **环境变量** 进行配置（通过 `.env` 文件）。

```bash
# 快速设置（自动生成安全密钥）
python scripts/setup_env.py

# 或手动复制
cp .env.example .env
```

编辑 `.env` 文件，配置必要的参数：

```bash
# Agent 配置
CORTEX_AGENT_ID=node-001
CORTEX_AGENT_NAME=My First Node
CORTEX_AGENT_MODE=standalone

# Claude API（必需）
ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# Monitor 配置
CORTEX_MONITOR_HOST=0.0.0.0
CORTEX_MONITOR_PORT=8000

# 认证密钥（自动生成安全随机值）
CORTEX_AUTH_SECRET_KEY=<自动生成>
CORTEX_MONITOR_REGISTRATION_TOKEN=<自动生成>
```

**优势**：
- ✅ 敏感信息不会被提交到 Git（`.env` 已在 `.gitignore`）
- ✅ 自动生成安全的随机密钥
- ✅ 符合 12-Factor App 最佳实践
- ✅ 完美支持 Docker 和容器化部署

> **提示**: 完整的配置选项请查看 `.env.example` 文件。

#### 初始化认证系统

```bash
# 创建默认 admin 用户和 API Key
python scripts/init_auth.py
```

这将创建：
- Admin 用户（用户名: `admin`，默认密码: `admin123`）
- Admin API Key（显示一次，请妥善保存）

**⚠️ 安全提醒**：生产环境部署前，请立即修改默认密码！

### 运行

#### Monitor（Web 服务）

```bash
# 启动 Monitor
cortex-monitor

# 访问 Web UI
http://localhost:8000
```

#### Probe（Web 服务模式）⭐ 推荐

```bash
# 启动 Probe Web 服务
cortex-probe

# 或使用 systemd
sudo systemctl start cortex-probe

# 访问 API
curl http://localhost:8001/health
curl http://localhost:8001/status

# 手动触发巡检
curl -X POST http://localhost:8001/execute
```

Probe 作为常驻 Web 服务进程运行，通过内部 APScheduler 周期性执行巡检。

**部署文档**：
- [系统服务部署](deployment/DEPLOYMENT.md) - systemd 服务配置
- [验证指南](docs/probe_validation.md) - 完整验证步骤

**集群模式**：

参见 [集群实现文档](CLUSTER_IMPLEMENTATION.md)

## 架构设计

### 系统组成

```
┌─────────────────────────────────────┐
│      Cortex Agent (统一组件)         │
│                                     │
│  ┌──────────────────────────────┐  │
│  │  Probe (探测功能)             │  │
│  │  - FastAPI Web 服务           │  │
│  │  - 文档驱动 (claude -p)       │  │
│  │  - APScheduler 内部调度       │  │
│  │  - WebSocket 实时推送         │  │
│  │  - LLM 智能巡检               │  │
│  │  - L1 自主修复                │  │
│  │  - L2/L3 问题上报             │  │
│  └──────────────────────────────┘  │
│                                     │
│  ┌──────────────────────────────┐  │
│  │  Monitor (监控功能)           │  │
│  │  - FastAPI Web 服务           │  │
│  │  - 数据聚合中心               │  │
│  │  - L2 决策引擎 (LLM)          │  │
│  │  - L3 告警聚合                │  │
│  │  - Web UI                     │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

### Probe 架构

Cortex Probe 采用**文档驱动 + Web 服务**的创新架构：

```
┌────────────────────────────────────────────┐
│         Probe Web 服务 (FastAPI)            │
│                                            │
│  REST API    WebSocket    APScheduler      │
│     │            │            │            │
│     └────────────┴────────────┘            │
│                  ▼                         │
│           Claude Executor                  │
│                  │                         │
└──────────────────┼─────────────────────────┘
                   ▼
         ┌─────────────────┐
         │   claude -p     │
         │  文档驱动巡检    │
         └─────────────────┘
```

**核心特性**：
- 🌐 **Web 服务** - 持久化进程，提供 REST API 和 WebSocket
- 📄 **文档驱动** - 巡检逻辑由 Markdown 文档定义
- ⏰ **内部调度** - APScheduler 管理定时任务（无需 cron）
- 🤖 **LLM 执行** - 通过 `claude -p` 智能执行巡检
- 📊 **实时状态** - WebSocket 推送巡检进度和结果
- 🔧 **灵活控制** - API 支持手动触发、暂停/恢复

**API 示例**：
```bash
# 查询状态
GET /status

# 手动触发巡检
POST /execute

# 获取报告列表
GET /reports

# WebSocket 连接
WS /ws
```

**详细文档**：
- [Probe 工作流程详解](docs/probe_workflow.md)
- [API 验证指南](docs/probe_validation.md)
- [部署指南](deployment/DEPLOYMENT.md)

### 问题分级

- **L1**：Probe 可本地自动修复（如磁盘清理、日志轮转）
- **L2**：需要 Monitor 决策批准（如服务重启、配置变更）
- **L3**：严重/未知错误，需要人类介入

### 运行模式

- **独立模式**：单节点自治，直接向人类汇报
- **集群模式**：多节点协同，形成"一主多从"或多层嵌套结构

## 文档

### 核心文档
- [架构设计](docs/architecture.md)
- [模块设计](docs/modules.md)
- [API 参考](docs/api.md)
- [开发路线图](docs/roadmap.md)

### Probe 文档
- **[Probe 工作流程详解](docs/probe_workflow.md)** ⭐ 深入理解文档驱动模式
- [Probe 使用手册](probe_workspace/README.md)
- [巡检项模板](probe_workspace/inspections/TEMPLATE.md)

### 运维文档
- [部署指南](docs/deployment.md)（待完成）
- [故障排查](docs/troubleshooting.md)（待完成）

## 开发

### 项目结构

```
cortex/
├── cortex/              # 主代码包
│   ├── probe/          # Probe 模块 ⭐ 新架构
│   │   ├── app.py                # FastAPI 应用
│   │   ├── scheduler_service.py  # APScheduler 调度
│   │   ├── claude_executor.py    # Claude -p 执行器
│   │   ├── websocket_manager.py  # WebSocket 管理
│   │   └── cli.py                # CLI 入口
│   ├── monitor/        # Monitor 模块
│   ├── common/         # 共享代码
│   └── config/         # 配置管理
├── probe_workspace/    # 文档驱动工作区
│   ├── CLAUDE.md       # Probe Agent 角色定义
│   ├── inspections/    # 巡检要求文档（Markdown）
│   └── tools/          # 检查和修复工具（Python）
├── deployment/         # 部署文件
│   ├── cortex-probe.service  # systemd 服务
│   └── DEPLOYMENT.md         # 部署文档
├── tests/              # 测试代码
├── scripts/            # 验证和工具脚本
├── docs/               # 文档
└── .github/            # CI/CD 配置
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行测试并生成覆盖率报告
pytest --cov=cortex --cov-report=html

# 运行特定模块测试
pytest tests/probe/
```

### 代码质量

```bash
# 代码格式化
black cortex tests

# 代码检查
ruff check cortex tests

# 类型检查
mypy cortex
```

### 贡献指南

我们欢迎各种形式的贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md)（待完成）了解详情。

## 技术栈

### 后端

- **语言**：Python 3.11+
- **Web 框架**：FastAPI 0.104+
- **ORM**：SQLAlchemy 2.0+
- **数据库**：SQLite 3.40+ / PostgreSQL 13+
- **任务调度**：APScheduler 3.10+
- **LLM SDK**：Anthropic Claude SDK 0.8+

### 前端

- **框架**：React 18.2+
- **语言**：TypeScript 5.0+
- **构建工具**：Vite 5.0+
- **UI 库**：Ant Design 5.11+
- **状态管理**：Zustand + TanStack Query

## 路线图

- [x] 项目初始化
- [x] Phase 1: 基础框架（Monitor + Intent-Engine + 集群基础）
- [x] Phase 1.5: Probe 架构重新设计（Web 服务 + APScheduler + 文档驱动）
- [x] Phase 2: 集群功能完善（L2 决策 + L3 告警 + 心跳检测）
- [ ] Phase 3: Web UI
- [ ] Phase 4: 性能优化与安全加固
- [ ] Phase 5: v1.0 发布

详细路线图请参见 [docs/roadmap.md](docs/roadmap.md)

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 联系方式

- **项目主页**：https://github.com/cortex-ops/cortex
- **问题反馈**：https://github.com/cortex-ops/cortex/issues
- **文档**：https://cortex-ops.github.io/cortex

---

**⚠️ 注意**：本项目目前处于早期开发阶段（Alpha），不建议用于生产环境。
