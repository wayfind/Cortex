# Intent-Engine 工作机制详解

## 📖 概述

Intent-Engine 是 Cortex 的"记忆和审计系统"，它将每个重要操作封装为"意图"（Intent），记录从创建到完成的全生命周期，确保所有决策和操作的完整可追溯性。

---

## 🎯 核心理念

### 问题背景

传统运维系统的痛点：
- ❌ **操作不可追溯**：不知道谁在什么时候做了什么
- ❌ **决策缺乏上下文**：无法了解决策的原因和依据
- ❌ **故障难以复盘**：缺少完整的操作历史
- ❌ **跨重启信息丢失**：系统重启后上下文全部丢失

### Intent-Engine 的解决方案

✅ **全生命周期跟踪**：从创建到完成的每一步
✅ **完整审计轨迹**：所有决策都有记录和理由
✅ **持久化存储**：跨重启保存上下文
✅ **灵活查询**：按时间、类型、级别、Agent 多维度查询

---

## 🏗️ 架构设计

### 数据模型

```python
class IntentRecord:
    id: int                    # 唯一标识
    timestamp: datetime        # 创建时间
    agent_id: str             # 哪个 Agent 产生的
    intent_type: str          # 意图类型 (decision/blocker/milestone/note)
    level: str                # 问题级别 (L1/L2/L3)
    category: str             # 操作类别 (如 disk_cleanup, service_restart)
    description: str          # 详细描述
    metadata_json: str        # JSON 格式的额外信息
    status: str               # 状态 (pending/approved/rejected/executed/completed)
```

### 四种意图类型

| 类型 | 用途 | 级别 | 示例 |
|------|------|------|------|
| **decision** | 决策操作 | L1/L2 | "清理 /tmp 目录释放空间" |
| **blocker** | 严重问题 | L3 | "无法连接到主数据库" |
| **milestone** | 重要里程碑 | - | "Phase 5 完成" |
| **note** | 常规日志 | - | "定时巡检完成" |

---

## 🔄 工作流程

### 1. L1 自动修复流程

```
Probe 检测到磁盘空间 > 90%
    ↓
Intent-Engine 记录 decision (L1, status: pending)
    ↓
Probe 自动执行清理
    ↓
Intent-Engine 更新状态 (completed)
    ↓
✅ 完成，无需人工介入
```

**代码示例**：
```python
# Probe 发现问题
intent_id = await intent_recorder.record_decision(
    agent_id="probe-001",
    level="L1",
    category="disk_cleanup",
    description="Disk usage 92%, cleaning /tmp directory",
    status="pending",
    metadata={
        "disk_usage": 92,
        "path": "/tmp",
        "threshold": 90
    }
)

# 执行清理
result = cleanup_tmp_directory()

# 更新状态
await intent_recorder.update_intent_status(
    intent_id,
    "completed"
)
```

### 2. L2 决策请求流程

```
Probe 检测到服务内存占用过高
    ↓
Intent-Engine 记录 decision (L2, status: pending)
    ↓
Probe 发送决策请求到 Monitor
    ↓
Monitor LLM 分析风险
    ↓
Intent-Engine 更新状态 (approved/rejected)
    ↓
如果 approved:
    Probe 执行重启
    Intent-Engine 更新 (executed → completed)
否则:
    ❌ 不执行，记录原因
```

**代码示例**：
```python
# 1. Probe 创建 L2 决策请求
intent_id = await intent_recorder.record_decision(
    agent_id="probe-001",
    level="L2",
    category="service_restart",
    description="Service memory usage 85%, requesting restart approval",
    status="pending",
    metadata={
        "service": "worker-01",
        "memory_mb": 8500,
        "threshold_mb": 8000,
        "risk_level": "medium"
    }
)

# 2. Monitor 接收并分析
decision_response = await decision_engine.request_decision(
    agent_id="probe-001",
    issue_description="High memory usage",
    proposed_action="Restart service",
    intent_id=intent_id
)

# 3. 更新决策结果
if decision_response.approved:
    await intent_recorder.update_intent_status(intent_id, "approved")

    # 4. Probe 执行操作
    await restart_service("worker-01")
    await intent_recorder.update_intent_status(intent_id, "executed")

    # 5. 验证结果
    if verify_service_health("worker-01"):
        await intent_recorder.update_intent_status(intent_id, "completed")
else:
    await intent_recorder.update_intent_status(intent_id, "rejected")
```

### 3. L3 严重问题上报

```
Probe 发现数据库连接失败
    ↓
Intent-Engine 记录 blocker (L3)
    ↓
Monitor 收到告警
    ↓
Monitor 聚合并发送通知给人类
    ↓
人类介入处理
```

**代码示例**：
```python
# Probe 记录严重问题
intent_id = await intent_recorder.record_blocker(
    agent_id="probe-001",
    category="database_connection",
    description="Unable to connect to primary database after 5 retries",
    metadata={
        "error": "Connection timeout",
        "host": "db.example.com",
        "port": 5432,
        "retries": 5,
        "last_attempt": "2025-11-17T12:00:00Z"
    }
)

# Monitor 收到后发送告警
await alert_manager.create_alert(
    severity="critical",
    title="Database Connection Failure",
    description=f"Agent probe-001 cannot connect to database",
    agent_id="probe-001",
    intent_id=intent_id
)
```

---

## 🔍 查询和分析

### API 查询示例

```bash
# 查询所有 L2 决策
curl "http://localhost:8000/api/v1/intents?level=L2&limit=50"

# 查询特定 Agent 的所有意图
curl "http://localhost:8000/api/v1/intents?agent_id=probe-001"

# 查询所有 blocker
curl "http://localhost:8000/api/v1/intents?intent_type=blocker"

# 查询特定类别的操作
curl "http://localhost:8000/api/v1/intents?category=disk_cleanup"
```

### 统计分析

```bash
# 按类型统计
curl "http://localhost:8000/api/v1/intents/stats/by-type"

# 响应示例：
{
  "decision": 450,
  "blocker": 12,
  "milestone": 5,
  "note": 1200
}

# 按级别统计
curl "http://localhost:8000/api/v1/intents/stats/by-level"

# 响应示例：
{
  "L1": 380,
  "L2": 70,
  "L3": 12
}
```

---

## 💡 实际应用场景

### 场景 1: 故障复盘

**问题**：昨天晚上服务出现故障，需要了解发生了什么。

**使用 Intent-Engine**：
```python
# 查询昨晚的所有意图
intents = await intent_recorder.query_intents(
    time_range=("2025-11-16T20:00:00", "2025-11-17T06:00:00"),
    agent_id="probe-001"
)

# 分析时间线
for intent in intents:
    print(f"{intent.timestamp} [{intent.level}] {intent.category}: {intent.description}")
```

**输出示例**：
```
2025-11-16 21:30:00 [L1] disk_cleanup: Cleaned /tmp, freed 2GB
2025-11-16 22:15:00 [L2] service_restart: Restarted worker-01 (approved)
2025-11-16 22:20:00 [L3] database_connection: Cannot connect to DB
2025-11-16 22:25:00 [L3] service_unavailable: Service worker-01 down
```

**结论**：重启服务后数据库连接失败，导致服务不可用。

### 场景 2: 决策审计

**问题**：需要了解过去一周 Monitor 批准了哪些 L2 操作。

```python
# 查询所有已批准的 L2 决策
decisions = await intent_recorder.query_intents(
    intent_type="decision",
    level="L2",
    status="approved",
    days=7
)

# 分析批准率
total_l2 = await intent_recorder.count_intents(level="L2", days=7)
approved = len([d for d in decisions if d.status == "approved"])
approval_rate = (approved / total_l2) * 100

print(f"L2 批准率: {approval_rate:.1f}%")
```

### 场景 3: 性能分析

**问题**：哪些操作最频繁？哪些 Agent 最活跃？

```python
# 统计各类操作频率
category_stats = await intent_recorder.stats_by_category(days=30)

# 输出 Top 10
for category, count in category_stats.most_common(10):
    print(f"{category}: {count} 次")

# 统计各 Agent 活跃度
agent_stats = await intent_recorder.stats_by_agent(days=30)

for agent, count in agent_stats.items():
    print(f"{agent}: {count} 个意图")
```

---

## 🔧 配置和使用

### 1. 启用 Intent-Engine

在 `.env` 文件中配置:
```bash
# Intent Engine 配置
CORTEX_INTENT_ENABLED=true
CORTEX_INTENT_DATABASE_URL=sqlite:///./cortex_intents.db  # 或 PostgreSQL
```

**环境变量**:
```bash
CORTEX_INTENT_ENGINE_ENABLED=true
CORTEX_INTENT_ENGINE_DATABASE_URL="postgresql://user:pass@localhost:5432/cortex_intents"
```

### 2. 在代码中使用

```python
from cortex.common.intent_recorder import IntentRecorder
from cortex.config.settings import get_settings

# 初始化
settings = get_settings()
recorder = IntentRecorder(settings)
await recorder.initialize()

# 记录决策
intent_id = await recorder.record_decision(
    agent_id="my-agent",
    level="L1",
    category="auto_fix",
    description="Fixed the issue",
    status="completed"
)

# 更新状态
await recorder.update_intent_status(intent_id, "completed")

# 查询
recent = await recorder.query_recent_intents(agent_id="my-agent", limit=10)
```

### 3. Web UI 查看

访问 Monitor Web UI 的 Intents 页面：
- http://localhost:3000/intents

功能：
- 时间线视图
- 按类型/级别/Agent 筛选
- 查看详细信息和 metadata
- 导出为 CSV/JSON

---

## 📊 数据库模式

### SQLite (默认，适合小规模)

```bash
# 数据库文件
./cortex_intents.db

# 查看数据
sqlite3 cortex_intents.db
> SELECT * FROM intent_records ORDER BY timestamp DESC LIMIT 10;
```

### PostgreSQL (推荐生产环境)

```yaml
intent_engine:
  database_url: "postgresql://cortex:password@localhost:5432/cortex_intents"
```

**优势**：
- 更好的并发性能
- 支持复杂查询
- 适合大规模集群 (50+ 节点)
- 更强的数据完整性

---

## 🎯 最佳实践

### 1. 始终记录重要操作

✅ **DO**:
```python
# 任何可能影响系统的操作都应记录
intent_id = await recorder.record_decision(...)
execute_operation()
await recorder.update_intent_status(intent_id, "completed")
```

❌ **DON'T**:
```python
# 直接执行，没有记录
execute_operation()  # 不推荐！
```

### 2. 使用合适的意图类型

- **decision**: 需要决策或执行的操作
- **blocker**: 严重问题，阻止正常运行
- **milestone**: 项目或系统重要事件
- **note**: 常规日志，不影响系统

### 3. 提供丰富的 metadata

```python
# ✅ 好的示例
await recorder.record_decision(
    agent_id="probe-001",
    level="L2",
    category="service_restart",
    description="Restarting service due to high memory",
    metadata={
        "service": "worker-01",
        "memory_before": 8500,
        "memory_after": 1200,
        "threshold": 8000,
        "restart_time": "2025-11-17T12:00:00Z",
        "downtime_seconds": 15
    }
)

# ❌ 不够详细
await recorder.record_decision(
    agent_id="probe-001",
    level="L2",
    category="restart",
    description="Restarted service"
)
```

### 4. 保持状态转换的完整性

```python
# 完整的状态转换流程
intent_id = await recorder.record_decision(..., status="pending")

# 决策批准
await recorder.update_intent_status(intent_id, "approved")

# 开始执行
await recorder.update_intent_status(intent_id, "executing")

# 执行完成
await recorder.update_intent_status(intent_id, "executed")

# 验证成功
await recorder.update_intent_status(intent_id, "completed")
```

---

## 🔮 未来增强 (v1.1.0+)

### 计划中的功能

1. **可视化时间线**
   - 图形化展示意图流
   - 交互式时间轴
   - 关联关系可视化

2. **智能分析**
   - 异常模式检测
   - 趋势分析
   - 预测性告警

3. **导出和报告**
   - PDF 报告生成
   - Excel 导出
   - 自定义报表

4. **集成增强**
   - Prometheus metrics
   - Grafana dashboard
   - Webhook 通知

---

## 📚 相关文档

- [架构设计](./ARCHITECTURE_UPDATE.md) - 了解 Intent-Engine 在系统中的位置
- [API 参考](http://localhost:8000/docs) - 完整的 API 文档
- [E2E 测试](../tests/test_e2e_intent_engine.py) - 实际使用示例

---

## ❓ 常见问题

### Q1: Intent-Engine 会影响性能吗？

**A**: 影响很小。记录操作是异步的，不会阻塞主流程。在生产环境：
- 每次记录 < 10ms
- 支持高并发 (1000+ TPS)
- 使用连接池优化

### Q2: 数据库会不会无限增长？

**A**: 建议定期清理：
```python
# 删除 90 天前的 note 类型记录
await recorder.cleanup_old_intents(
    intent_type="note",
    days=90
)
```

### Q3: 可以禁用 Intent-Engine 吗？

**A**: 可以，但不推荐。如果禁用：
```yaml
intent_engine:
  enabled: false
```

所有 `record_*` 调用将直接返回 None，不会报错。

### Q4: 如何迁移到 PostgreSQL？

**A**:
1. 导出 SQLite 数据
2. 修改配置为 PostgreSQL URL
3. 重启服务（自动创建表）
4. 导入历史数据（可选）

---

**Intent-Engine** 是 Cortex 实现"可观测、可审计、可追溯"运维的核心基础设施。正确使用它，可以大大提升系统的可维护性和可靠性。

*最后更新: 2025-11-17*
