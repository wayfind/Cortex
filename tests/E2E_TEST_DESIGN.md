# 端到端集成测试设计

## 现有集成测试覆盖分析

### 1. test_cluster_integration.py (13个测试)
**覆盖场景**：
- ✅ 集群节点注册和层级管理（L0 → L1 → L2）
- ✅ 心跳检测和状态更新
- ✅ 上级转发器（UpstreamForwarder）
- ✅ 决策反馈机制
- ✅ 集群拓扑查询
- ✅ 端到端集群工作流

### 2. test_monitor_integration.py (20个测试)
**覆盖场景**：
- ✅ 依赖注入和循环导入修复
- ✅ ProbeConfig 配置验证
- ✅ API 路径正确性
- ✅ AsyncSession 依赖注入
- ✅ JSON 序列化（datetime处理）
- ✅ ClaudeConfig.temperature 字段

### 3. test_probe_service.py (12个测试)
**覆盖场景**：
- ✅ Probe API 端点（health, status, schedule, reports）
- ✅ Claude Executor 初始化和状态跟踪
- ✅ WebSocket Manager 连接管理
- ✅ Scheduler Service 启动停止
- ✅ 完整启动流程

## 缺失的关键集成测试场景

### 高优先级（影响核心功能）

#### 1. Probe ↔ Monitor 完整通信流程 ⭐⭐⭐
**测试文件**: `test_e2e_probe_monitor.py`

**场景 1.1**: L1 问题本地自主修复
- Probe 检测到 L1 问题（如 /tmp 磁盘使用率 80%）
- Probe 自主执行清理操作
- 生成包含 actions_taken 的报告
- 上报 Monitor（记录但不需决策）
- Monitor 存储报告并记录 Intent
- **预期结果**: 报告中 issues=[], actions_taken=[清理操作]

**场景 1.2**: L2 问题决策批准流程
- Probe 检测到 L2 问题（如内存使用率 88%）
- 生成包含 proposed_fix 的 L2 IssueReport
- 上报 Monitor 请求决策
- Monitor 调用 DecisionEngine（Mock LLM）分析风险
- Monitor 返回 "approved" 决策
- Probe 接收决策并执行操作（Mock）
- 回传执行结果
- **预期结果**: Decision 表有记录，status="approved", executed_at 有值

**场景 1.3**: L2 问题决策拒绝流程
- Probe 检测到高风险 L2 问题（如 kill 关键进程）
- Monitor LLM 分析后返回 "rejected"
- Probe 不执行操作，记录拒绝原因
- **预期结果**: Decision 表有记录，status="rejected", executed_at=NULL

**场景 1.4**: L3 问题告警流程
- Probe 检测到 L3 严重问题（如数据库连接失败）
- 上报 Monitor
- Monitor 创建 Alert 记录
- 触发 Telegram 通知（Mock）
- **预期结果**: Alert 表有记录，severity="critical", Telegram 通知被调用

**场景 1.5**: 混合问题报告（L1+L2+L3）
- 单次探测发现多个层级的问题
- L1: 已自主处理（actions_taken）
- L2: 等待决策（issues）
- L3: 触发告警（issues + alerts）
- **预期结果**: 一份报告，多个 issues，部分 actions_taken，创建 L3 alert

**覆盖模块**：
- `cortex/monitor/routers/reports.py` (20% → 70%+)
- `cortex/monitor/services/decision_engine.py` (98% → 100%)
- `cortex/monitor/services/alert_aggregator.py` (90% → 95%+)

---

#### 2. Intent-Engine 端到端测试 ⭐⭐⭐
**测试文件**: `test_e2e_intent_engine.py`

**场景 2.1**: 完整意图生命周期
- 创建 intent（type=decision, level=L2）
- 状态转换: pending → approved → executed
- 查询单个 intent 详情
- 统计 intent 数据（by type, by level, by agent）
- **预期结果**: Intent 状态正确转换，统计数据准确

**场景 2.2**: Intent 查询和过滤
- 按 agent_id 过滤
- 按 intent_type 过滤
- 按 level 过滤
- 按时间范围过滤
- 分页查询
- **预期结果**: 过滤和分页正确工作

**场景 2.3**: Intent 统计聚合
- 按类型统计（decision, blocker, milestone）
- 按层级统计（L1, L2, L3）
- 按 Agent 统计
- 时间范围统计（最近24小时）
- **预期结果**: 统计数据准确

**覆盖模块**：
- `cortex/monitor/routers/intents.py` (87% → 95%+)
- `cortex/common/intent_recorder.py` (93% → 98%+)

---

#### 3. WebSocket 实时通信测试 ⭐⭐
**测试文件**: `test_e2e_websocket.py`

**场景 3.1**: Monitor WebSocket 实时推送
- 客户端连接 Monitor WebSocket (`/ws`)
- Probe 上报包含 L2 问题的报告
- Monitor 处理后推送事件:
  - `report_received`
  - `decision_made`
- 客户端接收事件
- **预期结果**: 客户端收到正确的事件消息

**场景 3.2**: Probe WebSocket 实时状态
- 客户端连接 Probe WebSocket
- Probe 开始执行探测任务
- 推送状态事件:
  - `inspection_started`
  - `inspection_progress`
  - `inspection_completed`
- **预期结果**: 客户端收到探测状态更新

**场景 3.3**: 多客户端广播
- 多个客户端连接同一个 WebSocket
- 触发事件
- 所有客户端都收到广播消息
- **预期结果**: 广播机制正常工作

**覆盖模块**：
- `cortex/monitor/websocket_manager.py` (36% → 80%+)
- `cortex/probe/websocket_manager.py` (53% → 85%+)

---

### 中优先级（提升健壮性）

#### 4. 认证和授权测试 ⭐
**测试文件**: `test_e2e_auth.py`

**场景 4.1**: Agent API Key 认证
- 注册 Agent 获取 API Key
- 使用 API Key 访问受保护端点
- 无效 API Key 被拒绝
- **预期结果**: 认证机制正常工作

**场景 4.2**: JWT Token 认证
- 用户登录获取 JWT Token
- 使用 Token 访问 API
- Token 过期后被拒绝
- 刷新 Token
- **预期结果**: JWT 认证流程完整

**覆盖模块**：
- `cortex/monitor/auth.py` (71% → 90%+)
- `cortex/monitor/routers/auth.py` (63% → 85%+)

---

#### 5. 集群模式跨节点通信 ⭐
**测试文件**: `test_e2e_cluster_communication.py`

**场景 5.1**: 子节点 → 父节点 L2 决策转发
- 子节点 Probe 检测到 L2 问题
- 上报给子节点 Monitor
- 子节点 Monitor 转发给父节点 Monitor
- 父节点 LLM 分析并返回决策
- 决策沿路径回传
- **预期结果**: 跨节点决策流程完整

**场景 5.2**: 多层级集群（L0 → L1 → L2）
- 三层集群结构
- L2 节点问题逐级上报到 L0
- L0 做出决策后逐级下发
- **预期结果**: 多层级通信正常

**覆盖模块**：
- `cortex/monitor/services/upstream_forwarder.py` (93% → 98%+)
- `cortex/monitor/routers/cluster.py` (33% → 60%+)

---

### 低优先级（增强功能）

#### 6. Telegram 通知集成 ⭐
**测试文件**: `test_integration_telegram.py`

**场景 6.1**: L3 告警触发 Telegram 通知
- Mock Telegram Bot API
- 触发 L3 告警
- 验证通知内容格式
- **预期结果**: Telegram API 被正确调用

**覆盖模块**：
- `cortex/monitor/services/telegram_notifier.py` (18% → 60%+)

---

## 测试实现优先级

### 第一批（核心功能）
1. ✅ `test_e2e_probe_monitor.py` - Probe-Monitor 通信
2. ✅ `test_e2e_intent_engine.py` - Intent Engine
3. ✅ `test_e2e_websocket.py` - WebSocket 实时通信

### 第二批（健壮性）
4. `test_e2e_auth.py` - 认证授权
5. `test_e2e_cluster_communication.py` - 集群通信

### 第三批（增强功能）
6. `test_integration_telegram.py` - Telegram 通知

---

## 预期代码覆盖率提升

**当前**: 60%

**目标**: 75%+

**关键提升模块**:
- `cortex/monitor/routers/reports.py`: 20% → 70%
- `cortex/monitor/routers/cluster.py`: 33% → 60%
- `cortex/monitor/websocket_manager.py`: 36% → 80%
- `cortex/monitor/services/telegram_notifier.py`: 18% → 60%
- `cortex/probe/websocket_manager.py`: 53% → 85%
- `cortex/monitor/auth.py`: 71% → 90%
- `cortex/monitor/routers/auth.py`: 63% → 85%

---

## 测试工具和策略

### Mock 策略
- **LLM API**: Mock Anthropic Claude API 调用
- **HTTP 请求**: Mock httpx.AsyncClient
- **Telegram Bot**: Mock telegram.Bot
- **时间**: 使用固定时间戳避免时间依赖

### 数据库策略
- 使用内存 SQLite (`sqlite:///:memory:`)
- 每个测试独立事务，自动回滚
- Fixture 提供干净的数据库会话

### 异步测试
- 使用 `@pytest.mark.asyncio`
- AsyncClient 进行 API 调用
- 正确处理 async context manager

---

## 执行计划

1. **阶段1**: 实现 test_e2e_probe_monitor.py（预计2-3小时）
2. **阶段2**: 实现 test_e2e_intent_engine.py（预计1小时）
3. **阶段3**: 实现 test_e2e_websocket.py（预计2小时）
4. **阶段4**: 验证覆盖率是否达到75%+
5. **阶段5**: 根据覆盖率报告补充缺失测试
