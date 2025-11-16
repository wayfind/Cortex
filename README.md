# Cortex

**去中心化、分级自治的智能运维网络**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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

### 环境要求

- Python 3.11+
- SQLite 3.40+ (或 PostgreSQL 13+)
- Claude API Key

### 安装

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

复制配置示例并修改：

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，填入必要的配置：

```yaml
agent:
  id: "node-001"
  name: "My First Node"
  mode: "standalone"  # 或 "cluster"

claude:
  api_key: "your-claude-api-key"

monitor:
  host: "0.0.0.0"
  port: 8000
```

### 运行

**独立模式**（单节点）：

```bash
# 启动 Monitor（Web 服务）
cortex-monitor

# 启动 Probe（定时巡检，另一个终端）
cortex-probe
```

访问 Web UI：http://localhost:8000

**集群模式**：

参见 [部署文档](docs/deployment.md)

## 架构设计

### 系统组成

```
┌─────────────────────────────────────┐
│      Cortex Agent (统一组件)         │
│                                     │
│  ┌──────────────────────────────┐  │
│  │  Probe (探测功能)             │  │
│  │  - Cron 定时触发              │  │
│  │  - LLM 巡检                   │  │
│  │  - L1 自主修复                │  │
│  │  - L2/L3 问题上报             │  │
│  └──────────────────────────────┘  │
│                                     │
│  ┌──────────────────────────────┐  │
│  │  Monitor (监控功能)           │  │
│  │  - 数据聚合中心               │  │
│  │  - L2 决策引擎 (LLM)          │  │
│  │  - L3 告警聚合                │  │
│  │  - Web UI                     │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

### 问题分级

- **L1**：Probe 可本地自动修复（如磁盘清理、日志轮转）
- **L2**：需要 Monitor 决策批准（如服务重启、配置变更）
- **L3**：严重/未知错误，需要人类介入

### 运行模式

- **独立模式**：单节点自治，直接向人类汇报
- **集群模式**：多节点协同，形成"一主多从"或多层嵌套结构

## 文档

- [架构设计](docs/architecture.md)
- [模块设计](docs/modules.md)
- [API 参考](docs/api.md)
- [开发路线图](docs/roadmap.md)
- [部署指南](docs/deployment.md)（待完成）
- [故障排查](docs/troubleshooting.md)（待完成）

## 开发

### 项目结构

```
cortex/
├── cortex/              # 主代码包
│   ├── probe/          # Probe 模块
│   ├── monitor/        # Monitor 模块
│   ├── common/         # 共享代码
│   └── config/         # 配置管理
├── tests/              # 测试代码
├── frontend/           # Web UI（React + TypeScript）
├── scripts/            # 部署和工具脚本
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
- [ ] Phase 1: 基础框架（Probe + Monitor + Intent-Engine）
- [ ] Phase 2: 集群功能（L2 决策 + L3 告警）
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
