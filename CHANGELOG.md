# Changelog

All notable changes to Cortex will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Phase 5.3 测试与验证 (2025-11-17)
- **E2E Integration Tests**: 端到端集成测试框架
  - `test_e2e_probe_monitor.py`: Probe-Monitor 完整通信流程测试（5个场景）
    - L1 自主修复流程（disk cleanup）
    - L2 决策批准流程（memory restart approval）
    - L2 决策拒绝流程（high-risk operation rejection）
    - L3 告警触发流程（database failure alerts）
    - 混合问题处理（L1+L2+L3 in single report）
  - `test_e2e_intent_engine.py`: Intent-Engine 生命周期测试（5个场景）
    - 完整意图生命周期（create → query → update status）
    - Intent 查询和过滤（by agent_id, type, level）
    - Intent 统计聚合（by type, level, agent）
    - 便捷方法测试（record_decision, record_blocker, record_milestone）
    - Intent-Engine 禁用行为验证
  - `tests/E2E_TEST_DESIGN.md`: 综合 E2E 测试设计文档
- **IntentRecorder 新功能**:
  - `update_intent_status()`: 意图状态更新方法
  - 支持状态转换：pending → approved → executed → completed
- **Test Coverage 大幅提升**: 30% → **61%** (+31 percentage points)
  - `cortex/common/intent_recorder.py`: 39% → 90%
  - `cortex/monitor/services/decision_engine.py`: 35% → 98%
  - `cortex/monitor/services/alert_aggregator.py`: 32% → 90%
  - `cortex/monitor/routers/reports.py`: 20% → 40%
- **Total Tests**: 191 → 196 passing tests (+5 E2E tests)

### Fixed - Phase 4.2 集成问题修复 (已验证)
- 所有 6 个集成 bug 已修复并通过测试：
  1. ✅ 循环导入错误 - dependencies.py 模块
  2. ✅ ProbeConfig 验证错误 - 扁平字段结构
  3. ✅ API 路径错误 - /api/v1/reports
  4. ✅ AsyncSession 依赖注入
  5. ✅ JSON 序列化 - datetime 对象
  6. ✅ ClaudeConfig.temperature 字段

## [1.0.0] - 2024-01-XX (Pending Release)

### 🎉 首个正式版本发布

Cortex v1.0.0 是第一个生产就绪版本，包含完整的核心功能和生产环境支持。

### ✨ Added - 新增功能

#### Phase 1: 基础框架
- **Monitor 服务**: 基于 FastAPI 的 RESTful API 服务
- **Probe 服务**: 持久化 Web 服务，内置 APScheduler 调度
- **Intent Engine 集成**: 所有操作的意图追踪和审计
- **集群模式**: 支持一主多从的分级架构
- **节点注册与心跳**: 自动节点发现和健康监控

#### Phase 1.5: Probe 架构重设计
- **FastAPI Web 服务**: Probe 从 cron 任务重构为常驻服务
- **APScheduler 调度**: 内置调度器，支持 Cron 表达式
- **Claude 执行器**: 异步执行 `claude -p` 文档驱动巡检
- **WebSocket 管理器**: 实时推送巡检状态和结果
- **REST API**: 完整的巡检管理 API
- **systemd 支持**: 生产环境服务部署

#### Phase 2: 集群功能
- **节点注册 API**: 自动注册到上级 Monitor
- **心跳机制**: 5 分钟超时检测，自动故障转移
- **L2 决策引擎**: Claude 驱动的风险分析和决策支持
- **L3 告警聚合**: 智能告警去重和关联分析
- **Telegram 通知**: L3 告警通过 Telegram Bot 推送
- **多层级架构**: 支持 3+ 层嵌套集群
- **集群拓扑发现**: 自动识别集群结构

#### Phase 3: Web UI
- **React + TypeScript 前端**: 基于 Vite 构建
- **全局仪表盘**: 集群状态统计、实时告警、拓扑预览
- **节点详情页**: 详细的节点信息、告警、报告、指标
- **告警中心**: 告警列表、筛选、排序
- **设置页**: API 配置、应用信息
- **WebSocket 实时更新**: 4 种事件类型广播（report/alert/decision/status）
- **自动重连机制**: 网络中断自动恢复

#### Phase 4: 增强与优化
- **JWT 认证**: API Key 和 Token 认证
- **RBAC 权限控制**: admin/operator/viewer 角色
- **数据库索引优化**: 高频查询性能提升
- **API 响应缓存**: 15x-50x 性能提升（TTL 内存缓存）
- **心跳超时检测**: 5 分钟超时自动标记离线
- **日志标准化**: 统一使用 loguru，支持多种格式
- **日志轮转和压缩**: 自动日志管理
- **模块级别日志配置**: 细粒度日志控制

#### Phase 5: 生产化准备
- **Docker 部署**:
  - 多阶段构建 Dockerfile（后端 + 前端）
  - docker-compose.yml 一键部署
  - 健康检查和资源限制
  - 持久化卷管理
- **一键安装脚本**: 支持 Ubuntu/Debian/CentOS/RHEL
- **多 Probe 配置**:
  - 支持不同 workspace 挂载
  - 不同巡检频率和阈值
  - 独立日志和监控
- **完整文档**:
  - 安装指南
  - Docker 部署指南
  - 多 Probe 配置指南
  - 配置参考
  - 故障排查指南
  - API 文档（自动生成）

### 🔧 Changed - 变更

- **Probe 架构**: 从 cron 任务改为持久化 Web 服务
- **日志系统**: 从 logging 迁移到 loguru
- **配置管理**: 支持环境变量优先级配置

### 🐛 Fixed - 修复

- 修复心跳超时后节点状态不更新问题
- 修复 WebSocket 连接不稳定问题
- 修复数据库并发访问死锁
- 修复前端路由刷新 404 问题
- 修复缓存失效不及时问题

### 🔒 Security - 安全

- 添加 JWT 认证机制
- 添加 API Key 管理
- 添加 RBAC 权限控制
- 密钥强度验证（≥32 字符）
- Docker 容器非 root 用户运行
- 敏感信息环境变量化

### 📚 Documentation - 文档

- 完整的安装和部署文档
- Docker Compose 快速开始指南
- 多 Probe 不同巡检方案配置
- 配置参数详细说明
- 故障排查指南
- API 参考文档（自动生成）
- WebSocket 实现文档
- 日志配置文档
- API 缓存策略文档

### 🏗️ Infrastructure - 基础设施

- GitHub Actions CI/CD（计划中）
- Docker Hub 镜像发布（计划中）
- 单元测试框架（进行中）
- 集成测试（计划中）

### 📈 Performance - 性能

- API 响应缓存：15x-50x 提升
- 数据库查询优化：添加索引
- 日志异步写入
- 前端代码分割和懒加载

### 🎨 UI/UX - 用户界面

- 响应式设计支持
- 深色/浅色主题（部分）
- Toast 通知
- Loading 状态
- 错误边界处理

## [0.1.0] - 2024-XX-XX

### Added
- 初始项目结构
- 基础 Monitor 和 Probe 功能
- 集群模式原型

---

## 发布说明

### v1.0.0 生产就绪标准

Cortex v1.0.0 满足以下生产环境标准：

#### 功能完整性
- ✅ 独立模式可运行
- ✅ 集群模式可运行（一主多从）
- ✅ L1 自动修复（Probe 本地）
- ✅ L2 决策流程（LLM 分析）
- ✅ L3 告警通知（Telegram）
- ✅ Web UI 核心功能
- ✅ Intent Engine 集成

#### 质量标准
- ✅ 核心功能测试覆盖
- ✅ API 响应时间 < 200ms (P95)
- ✅ 支持 50+ 节点
- ✅ 无已知严重 Bug

#### 文档标准
- ✅ 安装部署文档完整
- ✅ API 文档完整
- ✅ 故障排查指南可用
- ✅ 配置参考完整

#### 部署标准
- ✅ Docker 镜像可用
- ✅ Docker Compose 一键启动
- ✅ 支持 Ubuntu 20.04/22.04
- ✅ 支持 Debian 11/12
- ✅ 支持 CentOS/RHEL 8+

### 升级指南

从开发版本升级到 v1.0.0：

1. **备份数据**
   ```bash
   cp cortex.db cortex.db.backup
   cp config.yaml config.yaml.backup
   ```

2. **更新代码**
   ```bash
   git pull origin main
   ```

3. **更新依赖**
   ```bash
   pip install --upgrade -r requirements.txt
   ```

4. **运行迁移**
   ```bash
   # 如有数据库迁移
   # alembic upgrade head
   ```

5. **重启服务**
   ```bash
   docker-compose restart
   # 或
   sudo systemctl restart cortex-monitor cortex-probe
   ```

### 已知限制

- SQLite 性能限制：建议 < 50 节点
- WebSocket 连接数限制：建议 < 100 并发
- 单个 Probe 巡检时间：建议 < 30 分钟
- 不支持 Windows 原生部署（使用 WSL2 或 Docker）

### 下一步计划 (v1.1.0)

- [ ] Prometheus 指标导出
- [ ] Grafana 集成
- [ ] 高级图表可视化
- [ ] 自定义巡检规则 UI
- [ ] 告警规则引擎
- [ ] 移动端告警推送

### 贡献者

感谢所有为 Cortex v1.0.0 做出贡献的开发者！

---

[Unreleased]: https://github.com/cortex-ops/cortex/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/cortex-ops/cortex/releases/tag/v1.0.0
[0.1.0]: https://github.com/cortex-ops/cortex/releases/tag/v0.1.0
