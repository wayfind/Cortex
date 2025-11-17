# Cortex 工作计划文档

## 1. 项目阶段划分

### Phase 1: 基础框架搭建（2-3 周）✅ 已完成

**目标**：建立可运行的独立模式 Cortex Agent

#### 核心任务

1. **项目初始化** ✅
   - 创建项目目录结构
   - 配置 Python 开发环境（Poetry/pip）
   - 配置 Git 仓库和分支策略
   - 编写项目文档框架
   - 设置 CI/CD 基础配置

2. **Monitor 基础框架** ✅
   - FastAPI 应用搭建
   - 数据库初始化（SQLite + SQLAlchemy）
   - 基础 API 端点实现（/api/v1/reports, /api/v1/heartbeat）
   - 数据接收与存储逻辑

3. **Intent-Engine 集成** ✅
   - MCP 工具配置
   - 意图记录集成到 Monitor

4. **集群模式基础实现** ✅
   - 节点注册与心跳机制
   - 层级结构管理
   - 跨节点通信

---

### Phase 1.5: Probe 架构重新设计（1 周）✅ 已完成

**目标**：将 Probe 重新设计为持久化 Web 服务进程

#### 背景

原有 Probe 设计问题：
- ❌ 通过 cron 触发，每次执行完退出
- ❌ 没有 Web 服务接口
- ❌ 无法实时查询状态或手动触发

新架构设计：
- ✅ 持久化 FastAPI Web 服务进程
- ✅ 内部 APScheduler 调度（无需 cron）
- ✅ 周期性调用 `claude -p` 执行文档驱动巡检
- ✅ REST API + WebSocket 实时通信

#### 核心任务

1. **FastAPI Web 服务** ✅
   - 完整的 REST API 端点
   - WebSocket 实时通信
   - 健康检查和状态查询

2. **APScheduler 调度服务** ✅
   - Cron 表达式调度
   - 执行历史管理
   - 暂停/恢复控制

3. **Claude 执行器** ✅
   - 异步执行 `claude -p`
   - 超时处理和状态跟踪
   - 报告解析

4. **WebSocket 管理器** ✅
   - 连接管理
   - 事件广播

5. **CLI 入口重构** ✅
   - uvicorn 服务器启动
   - 命令行参数解析

6. **部署支持** ✅
   - systemd 服务文件
   - 部署文档
   - 验证脚本

#### 可交付成果

- [x] Probe Web 服务可运行
- [x] 完整的 REST API
- [x] WebSocket 实时推送
- [x] systemd 服务配置
- [x] 部署和验证文档

#### 技术里程碑

- Probe 作为常驻进程运行
- 周期性自动执行 `claude -p` 巡检
- 提供完整的管理 API
- WebSocket 实时状态更新

---

### Phase 2: 集群功能开发（3-4 周）✅ 已完成

**目标**：实现完整的集群模式和决策引擎

#### 核心任务

1. **集群通信机制**
   - 节点注册与发现 API
   - 心跳机制实现
   - 上下级通信协议
   - 集群配置管理（YAML）

2. **L2 决策引擎**
   - LLM 决策分析实现
   - 决策请求 API（/api/v1/decisions/request）
   - 决策结果查询 API
   - 指令回传机制
   - 决策记录到数据库

3. **L3 告警聚合**
   - 告警去重算法
   - 关联分析逻辑
   - Telegram Bot 集成
   - 告警通知模板

4. **多层级架构支持**
   - 嵌套集群配置支持
   - 递归上报路径
   - 集群拓扑发现算法
   - 拓扑可视化数据生成

#### 可交付成果

- [ ] 集群模式可运行（一主多从）
- [ ] 完整的 L2 决策流程（请求 → 分析 → 批准/拒绝 → 执行）
- [ ] Telegram 告警通知可用
- [ ] 支持至少 3 层嵌套集群

#### 技术里程碑

- 下级 Agent 可成功注册到上级 Monitor
- L2 决策请求可由 LLM 分析并返回结果
- L3 告警可聚合并通过 Telegram 发送
- 集群拓扑可正确识别和展示

---

### Phase 3: Web UI 开发（3-4 周）✅ 已完成

**目标**：提供完整的可视化管理界面

#### 核心任务

1. **前端项目搭建** ✅
   - React + TypeScript 项目初始化（Vite）
   - UI 组件库集成（Ant Design）
   - API 客户端封装（axios）
   - 路由配置（React Router）

2. **全局仪表盘** ✅
   - 集群状态统计卡片（Total/Online/Offline/Degraded）
   - 实时告警表格
   - 集群拓扑预览（节点总数、层级数）
   - Live 连接状态指示器

3. **节点详情页** ✅
   - 节点信息展示（Basic Information 表格）
   - Tabs 框架（Alerts/Inspection Reports/Metrics）
   - Back to Nodes 导航

4. **告警中心页** ✅
   - 告警列表表格
   - 级别筛选（All/L1/L2/L3）
   - 状态筛选（All/new/acknowledged/resolved）

5. **设置页** ✅
   - API Configuration 显示
   - Application Info 显示
   - About 项目描述

6. **实时通信** ✅
   - WebSocket 集成（自定义 useWebSocket hook）
   - 4 种事件类型广播（report/alert/decision/status）
   - Auto-reconnect 机制
   - UI 自动更新 + Toast 通知

#### 可交付成果

- [x] 完整的 Web UI
- [x] 响应式设计支持（桌面）
- [x] 实时数据更新
- [x] UI 测试套件文档

#### 技术里程碑

- ✅ 仪表盘可显示集群所有节点状态
- ✅ 点击节点可下钻查看详细信息
- ✅ 告警列表可实时更新
- ✅ WebSocket 连接稳定，数据推送及时

#### 完成文档

- [x] `frontend/UI_TEST_SUITE.md` - UI 测试套件
- [x] `docs/WEBSOCKET_IMPLEMENTATION.md` - WebSocket 实现文档
- [x] `docs/PHASE3_COMPLETION_SUMMARY.md` - Phase 3 完成总结

---

### Phase 4: 增强与优化（2-3 周）

**目标**：提升稳定性、性能和可用性

#### 核心任务

1. **认证与安全**
   - API Key 生成和管理
   - API Key 认证中间件
   - JWT Token 签发和验证
   - 用户登录系统（Web UI）
   - RBAC 权限控制（admin/operator/viewer）
   - HTTPS/TLS 配置支持
   - 敏感数据加密（配置文件、API Key）

2. **性能优化**
   - 数据库查询性能分析
   - 慢查询优化（添加索引）
   - API 响应缓存（Redis 或内存缓存）
   - 前端性能优化（代码分割、懒加载）
   - 图表渲染优化

3. **容错与恢复**
   - 网络请求重试机制（指数退避）
   - 上报数据本地队列（离线时缓存）
   - 数据库备份脚本
   - 故障转移逻辑（Monitor 不可达时的行为）
   - 健康检查端点完善

4. **可观测性**
   - 日志标准化（结构化日志）
   - 日志级别配置
   - 性能指标采集（可选：Prometheus）
   - 调试工具开发（日志查看、状态检查）

#### 可交付成果

- [ ] 性能测试报告（API 响应时间、并发能力）
- [ ] 安全评估文档
- [ ] 运维手册（故障排查、备份恢复）
- [ ] 监控指标暴露（如使用 Prometheus）

#### 技术里程碑

- API 响应时间 P95 < 200ms
- 数据库查询已优化（所有慢查询 < 100ms）
- 网络请求有重试机制且测试通过
- 数据可自动备份且恢复流程已验证

---

### Phase 5: 生产化准备（1-2 周）

**目标**：完成生产环境部署准备

#### 核心任务

1. **部署工具**
   - Dockerfile 编写
   - docker-compose.yml 配置
   - 一键部署脚本（install.sh）
   - 环境变量配置示例（.env.example）
   - systemd 服务文件（可选）

2. **文档完善**
   - 安装部署文档
   - 配置参数说明（完整的配置参考）
   - API 参考文档（自动生成 + 手动补充）
   - 用户操作手册（带截图）
   - 故障排查指南（FAQ）
   - 架构文档（本文档）

3. **测试与验证**
   - 单元测试补充（覆盖率 > 80%）
   - 集成测试（端到端场景）
   - 压力测试（并发请求、大量节点）
   - 兼容性测试（不同 Linux 发行版）
   - 安全测试（漏洞扫描）

4. **发布准备**
   - 版本号规范（SemVer）
   - 变更日志（CHANGELOG.md）
   - 发布检查清单
   - GitHub Release 创建

#### 可交付成果

- [ ] v1.0.0 生产版本发布
- [ ] 完整文档集（部署、使用、API、故障排查）
- [ ] Docker 镜像（Docker Hub 或私有仓库）
- [ ] 部署工具包（一键安装）

#### 技术里程碑

- Docker 镜像可成功构建并运行
- Docker Compose 可一键启动完整环境
- 所有测试通过（单元、集成、端到端）
- 文档完整且经过审核

---

## 2. 技术栈选择建议

### 2.1 后端技术栈

#### 推荐配置

```yaml
# 核心技术栈
语言: Python 3.11+
Web 框架: FastAPI 0.104+
ORM: SQLAlchemy 2.0+
数据库: SQLite 3.40+ (生产环境可升级到 PostgreSQL)
任务调度: APScheduler 3.10+
LLM SDK: Anthropic Claude SDK 0.8+
HTTP 客户端: httpx 0.25+ (异步)
配置管理: pydantic-settings 2.0+
日志: loguru 0.7+
测试: pytest 7.4+ + pytest-asyncio

# 可选依赖
缓存: redis-py (如需 Redis 缓存)
监控: prometheus-client (如需 Prometheus 指标)
```

#### requirements.txt 示例

```txt
# Web 框架
fastapi==0.104.1
uvicorn[standard]==0.24.0

# 数据库
sqlalchemy==2.0.23
alembic==1.13.0  # 数据库迁移
aiosqlite==0.19.0  # 异步 SQLite

# 数据验证
pydantic==2.5.0
pydantic-settings==2.1.0

# LLM SDK
anthropic==0.8.1

# 任务调度
apscheduler==3.10.4

# HTTP 客户端
httpx==0.25.2

# 系统监控
psutil==5.9.6

# 日志
loguru==0.7.2

# Telegram Bot
python-telegram-bot==20.7

# 认证
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6

# 测试
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
httpx==0.25.2  # 用于测试 HTTP 请求

# 开发工具
black==23.12.1  # 代码格式化
ruff==0.1.8  # 代码检查
mypy==1.7.1  # 类型检查
```

### 2.2 前端技术栈

#### 推荐配置

```yaml
# 核心技术栈
框架: React 18.2+
语言: TypeScript 5.0+
构建工具: Vite 5.0+
UI 组件库: Ant Design 5.11+ (或 shadcn/ui)
状态管理:
  - 全局状态: Zustand 4.4+
  - 异步状态: TanStack Query 5.0+
图表库: Recharts 2.10+ (或 Apache ECharts 5.4+)
HTTP 客户端: axios 1.6+
WebSocket: socket.io-client 4.6+
路由: React Router 6.20+
表单: React Hook Form 7.48+
工具库: dayjs 1.11+
```

#### package.json 示例

```json
{
  "name": "cortex-ui",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx",
    "format": "prettier --write \"src/**/*.{ts,tsx,css}\""
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "axios": "^1.6.2",
    "socket.io-client": "^4.6.0",
    "zustand": "^4.4.7",
    "@tanstack/react-query": "^5.12.0",
    "antd": "^5.11.5",
    "recharts": "^2.10.3",
    "react-hook-form": "^7.48.2",
    "dayjs": "^1.11.10",
    "@ant-design/icons": "^5.2.6"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.3.3",
    "vite": "^5.0.7",
    "eslint": "^8.55.0",
    "@typescript-eslint/eslint-plugin": "^6.14.0",
    "@typescript-eslint/parser": "^6.14.0",
    "prettier": "^3.1.1",
    "tailwindcss": "^3.3.6"  // 如使用 shadcn/ui
  }
}
```

### 2.3 开发工具

```yaml
# 版本控制
Git: 2.40+

# 代码质量
Python:
  - 格式化: Black 23.12+
  - 检查: Ruff 0.1+
  - 类型检查: mypy 1.7+
TypeScript:
  - 格式化: Prettier 3.1+
  - 检查: ESLint 8.55+
  - 类型检查: TypeScript Compiler

# 容器化
Docker: 24.0+
Docker Compose: 2.20+

# CI/CD
GitHub Actions (或 GitLab CI)

# 文档
Python API 文档: FastAPI 自动生成
TypeScript 文档: TypeDoc (可选)
用户文档: Markdown
```

### 2.4 推荐的开发环境

```yaml
# 操作系统
推荐: Ubuntu 22.04 LTS 或 macOS
Windows: WSL2 + Ubuntu

# 编辑器/IDE
推荐:
  - VS Code (跨平台，扩展丰富)
  - PyCharm Professional (Python 开发)

# VS Code 推荐扩展
Python:
  - Python (Microsoft)
  - Pylance (类型检查)
  - Black Formatter
  - Ruff
TypeScript/React:
  - ESLint
  - Prettier
  - TypeScript and JavaScript Language Features
其他:
  - GitLens
  - Docker
  - Thunder Client (API 测试)
```

---

## 3. 开发优先级

### 高优先级 (P0) - 核心功能

这些功能是 Cortex 的核心价值，必须在 v1.0 前完成。

1. **Probe 基础巡检** ✅ Phase 1
   - 定时触发机制
   - 系统健康检查（CPU/内存/磁盘）
   - LLM 集成

2. **Monitor 数据接收** ✅ Phase 1
   - API 端点实现
   - 数据存储

3. **L2 决策引擎** ✅ Phase 2
   - 决策请求处理
   - LLM 风险分析
   - 指令回传

4. **L3 告警通知** ✅ Phase 2
   - 告警聚合
   - Telegram 通知

5. **集群通信机制** ✅ Phase 2
   - 节点注册
   - 心跳机制
   - 上下级通信

6. **Intent-Engine 集成** ✅ Phase 1
   - 意图记录
   - 历史追溯

7. **基础 Web UI（仪表盘）** ✅ Phase 3 已完成
   - 集群状态展示
   - 节点列表

### 中优先级 (P1) - 重要功能

这些功能显著提升用户体验，建议在 v1.0 或 v1.1 完成。

1. **节点详情页** ✅ Phase 3 已完成
   - 下钻分析
   - 基础框架（历史数据图表待增强）

2. **告警中心** ✅ Phase 3 已完成
   - 告警列表
   - 筛选排序

3. **WebSocket 实时更新** ✅ Phase 3 已完成
   - 实时推送
   - UI 自动刷新
   - Auto-reconnect

4. **认证与授权** ✅ Phase 4
   - API Key 管理
   - 用户登录
   - 权限控制

5. **数据归档策略** ✅ Phase 4
   - 自动归档
   - 清理旧数据

6. **Docker 部署** ✅ Phase 5
   - Dockerfile
   - Docker Compose

### 低优先级 (P2) - 增强功能

这些功能可以在 v1.x 迭代中逐步添加。

1. **高级图表可视化**
   - 集群拓扑图（交互式）
   - 更丰富的图表类型

2. **自定义巡检规则**
   - 用户自定义检查项
   - 规则配置 UI

3. **告警规则引擎**
   - 自定义告警条件
   - 告警分组和静默

4. **多租户支持**
   - 租户隔离
   - 权限细粒度控制

5. **Prometheus 指标导出**
   - 标准指标暴露
   - Grafana 集成

6. **国际化 (i18n)**
   - 多语言支持
   - 中英文切换

### 未来规划 (P3) - 长期目标

这些是长期演进目标，可能在 v2.0+ 考虑。

1. **插件系统**
   - 自定义巡检插件
   - 自定义修复策略
   - 插件市场

2. **机器学习故障预测**
   - 基于历史数据的异常检测
   - 故障提前预警

3. **自动修复策略学习**
   - 从人类决策中学习
   - 优化 L2 决策准确率

4. **移动端应用**
   - iOS/Android 应用
   - 告警推送

5. **云原生部署**
   - Kubernetes Operator
   - Helm Charts
   - 多副本高可用

6. **分布式协调**
   - 使用 etcd/Consul 替代配置文件
   - 动态服务发现

---

## 4. 项目时间线估算

### 4.1 时间表（单人开发）

| 阶段 | 任务 | 预计时间 | 累计时间 | 关键里程碑 | 状态 |
|------|------|---------|---------|----------|------|
| **Phase 1** | 项目初始化、Probe、Monitor、Intent-Engine | 2-3 周 | 3 周 | 独立模式可运行 | ✅ 已完成 |
| **Phase 2** | 集群模式、L2 决策、L3 告警 | 3-4 周 | 7 周 | 集群模式可用 | ✅ 已完成 |
| **Phase 3** | Web UI 开发 | 3-4 周 | 11 周 | 完整 UI 可用 | ✅ 已完成 |
| **Phase 4** | 安全、性能、容错优化 | 2-3 周 | 14 周 | 生产就绪 | ⏳ 待开始 |
| **Phase 5** | 部署工具、文档、测试 | 1-2 周 | 16 周 | v1.0 发布 | ⏳ 待开始 |

**总计**: 约 16 周（4 个月）

### 4.2 时间表（小团队 2-3 人）

| 阶段 | 任务 | 预计时间 | 累计时间 | 分工建议 |
|------|------|---------|---------|----------|
| **Phase 1** | 基础框架 | 1.5-2 周 | 2 周 | 后端 1人 + 基础设施 1人 |
| **Phase 2** | 集群功能 | 2-3 周 | 5 周 | 后端 2人 |
| **Phase 3** | Web UI | 2-3 周 | 8 周 | 前端 1人 + 后端 API 配合 1人 |
| **Phase 4** | 优化增强 | 1.5-2 周 | 10 周 | 全员 |
| **Phase 5** | 发布准备 | 1 周 | 11 周 | 全员 |

**总计**: 约 11 周（2.5 个月）

### 4.3 关键里程碑

- **Week 2-3**: ✅ Phase 1 完成，独立模式 Demo 可演示
- **Week 7**: ✅ Phase 2 完成，集群模式可用，核心功能完整
- **Week 11**: ✅ Phase 3 完成，完整的 Web UI，用户可操作（**当前状态**）
- **Week 14**: ⏳ Phase 4 完成，性能和安全优化，生产就绪
- **Week 16**: ⏳ Phase 5 完成，v1.0 正式发布

---

## 5. 风险与缓解策略

### 5.1 技术风险

| 风险 | 影响 | 概率 | 缓解策略 |
|------|------|------|---------|
| LLM API 稳定性 | 高 | 中 | 1. 实现重试机制<br>2. 添加降级方案（规则引擎）<br>3. 监控 API 可用性 |
| SQLite 性能瓶颈 | 中 | 低 | 1. 优化查询和索引<br>2. 预留 PostgreSQL 迁移路径<br>3. 定期性能测试 |
| WebSocket 连接不稳定 | 低 | 中 | 1. 自动重连机制<br>2. 降级到轮询<br>3. 心跳检测 |
| 数据丢失 | 高 | 低 | 1. 定期备份<br>2. 本地队列缓存<br>3. 数据完整性检查 |

### 5.2 项目风险

| 风险 | 影响 | 概率 | 缓解策略 |
|------|------|------|---------|
| 需求变更 | 中 | 中 | 1. MVP 优先，核心功能先行<br>2. 模块化设计，易扩展<br>3. 定期需求评审 |
| 时间估算不准 | 中 | 高 | 1. 预留 20% 缓冲时间<br>2. 每周进度回顾<br>3. 优先级动态调整 |
| 技术债务累积 | 中 | 中 | 1. 代码审查<br>2. 重构时间预留<br>3. 测试覆盖率要求 |
| 依赖库变更 | 低 | 低 | 1. 锁定版本号<br>2. 定期依赖更新<br>3. 兼容性测试 |

---

## 6. 成功标准

### 6.1 v1.0 发布标准

#### 功能完整性
- [ ] 独立模式可运行
- [ ] 集群模式可运行（一主多从）
- [ ] L1 自动修复可用
- [ ] L2 决策流程完整
- [ ] L3 告警通知可用
- [ ] Web UI 核心功能完整
- [ ] Intent-Engine 集成可用

#### 质量标准
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过
- [ ] API 响应时间 P95 < 200ms
- [ ] 无已知严重 Bug

#### 文档标准
- [ ] 安装部署文档完整
- [ ] API 文档完整
- [ ] 用户操作手册完整
- [ ] 故障排查指南可用

#### 部署标准
- [ ] Docker 镜像可用
- [ ] Docker Compose 一键启动
- [ ] 支持至少 Ubuntu 20.04/22.04

### 6.2 性能目标

| 指标 | 目标值 |
|------|--------|
| API 响应时间（P95） | < 200ms |
| API 响应时间（P99） | < 500ms |
| 并发请求支持 | > 100 req/s |
| 支持节点数 | > 50 个节点 |
| 数据库查询时间 | < 100ms |
| Probe 巡检时间 | < 30s |
| WebSocket 消息延迟 | < 100ms |

### 6.3 可靠性目标

| 指标 | 目标值 |
|------|--------|
| 系统可用性 | > 99.9% |
| 数据持久性 | > 99.99% |
| 自动恢复时间 | < 5 分钟 |
| 错误率 | < 0.1% |

---

## 7. 后续版本规划

### v1.1 (v1.0 后 1-2 个月)
- 高级图表可视化
- 自定义巡检规则
- 告警规则引擎
- 性能进一步优化

### v1.2 (v1.1 后 2-3 个月)
- 多租户支持
- Prometheus 指标导出
- 国际化支持
- 移动端告警推送

### v2.0 (v1.2 后 6+ 个月)
- 插件系统
- 机器学习故障预测
- 云原生部署支持
- 分布式协调

---

## 8. 总结

Cortex 项目的工作计划分为 5 个阶段，预计 16 周（约 4 个月）完成 v1.0 版本。

**核心原则**：
1. **MVP 优先**：先实现核心功能，再扩展增强功能
2. **模块化设计**：便于迭代和扩展
3. **质量保证**：测试覆盖率和文档完整性
4. **生产就绪**：部署工具和运维文档完善

**技术栈**：
- 后端：Python 3.11+ + FastAPI + SQLite
- 前端：React 18+ + TypeScript + Ant Design
- 部署：Docker + Docker Compose

**开发优先级**：
- P0（核心功能）：Probe、Monitor、L2 决策、L3 告警、集群通信
- P1（重要功能）：详情页、告警中心、认证、Docker 部署
- P2（增强功能）：高级可视化、自定义规则、多租户
- P3（长期目标）：插件系统、机器学习、云原生

遵循此计划，Cortex 将从规格设计阶段逐步演进为一个功能完整、生产就绪的智能运维系统。
