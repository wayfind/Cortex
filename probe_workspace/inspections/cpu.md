# CPU 使用率巡检

## 巡检目标

监控系统 CPU 负载，及时发现性能瓶颈和异常进程。

## 检查方法

### 使用的工具

- `tools/check_cpu.py` - 检查 CPU 使用率和负载

### 执行步骤

1. 运行 `python3 tools/check_cpu.py`
2. 获取 CPU 使用率、负载平均值
3. 识别 CPU 占用最高的进程
4. 对照配置的阈值判断

## 阈值定义

从 `/etc/cortex/config.yaml` 读取 `probe.threshold_cpu_percent`，默认值：

| 指标 | 正常 | 警告 | 严重 |
|------|------|------|------|
| CPU 使用率 | < 70% | 70-85% | > 85% |
| 负载平均 (1min) | < CPU核心数 | CPU核心数 - 1.5倍 | > 1.5倍 |
| 负载平均 (5min) | < CPU核心数 | CPU核心数 - 1.5倍 | > 1.5倍 |

## 问题分级

### L1 - 可自动修复

**触发条件**：
- CPU 使用率 70-85%
- 存在已知的临时高负载任务（如备份、索引）
- 可以安全终止的后台任务

**修复方法**：
```bash
# 降低后台任务优先级
renice +10 -p <PID>

# 终止已知的临时任务
pkill -f "backup_script" || true
pkill -f "index_rebuild" || true

# 限制 CPU 使用（cgroup v2）
echo "50000 100000" > /sys/fs/cgroup/test_service/cpu.max
```

**验证方法**：
```bash
# 检查 CPU 使用率
top -bn1 | grep "Cpu(s)"
```

**执行工具**：
- `tools/manage_cpu.py --throttle` - CPU 限流工具

### L2 - 需要决策

**触发条件**：
- CPU 使用率 > 85%
- 负载平均持续高于 CPU 核心数 1.5 倍
- L1 操作后仍未改善
- 需要重启服务或扩容

**建议修复**：
1. **重启高负载服务**（风险：中）
   - 识别异常高负载的服务
   - 重启服务恢复正常
   - 需要评估服务中断影响

2. **限制应用 CPU 配额**（风险：低）
   - 使用 cgroup 限制 CPU 使用
   - 防止单个服务占用过多资源
   - 可能影响该服务性能

3. **扩容 CPU 资源**（风险：中）
   - 增加 CPU 核心数
   - 垂直或水平扩展
   - 需要停机或迁移

**风险评估**：
- 重启服务导致短暂不可用
- 限制 CPU 可能影响服务响应时间
- 扩容需要配置变更或迁移

**上报信息**：
```json
{
  "cpu_percent": 92.5,
  "load_avg_1min": 12.3,
  "load_avg_5min": 10.8,
  "cpu_cores": 8,
  "top_consumers": [
    {"process": "python", "pid": 1234, "cpu_percent": 350.0},
    {"process": "nginx", "pid": 5678, "cpu_percent": 125.0}
  ],
  "l1_actions_taken": ["throttled_backup_process"]
}
```

### L3 - 严重问题

**触发条件**：
- CPU 使用率 > 95%
- 负载平均 > CPU 核心数的 2 倍
- 系统响应严重迟缓
- L1 操作失败或无效

**上报信息**：
```json
{
  "severity": "critical",
  "cpu_percent": 99.2,
  "load_avg_1min": 18.5,
  "load_avg_5min": 16.3,
  "load_avg_15min": 14.2,
  "cpu_cores": 8,
  "top_consumers": [
    {"process": "runaway_script", "pid": 9876, "cpu_percent": 780.0},
    {"process": "java", "pid": 2345, "cpu_percent": 250.0}
  ],
  "iowait_percent": 5.2,
  "steal_percent": 0.8,
  "error_message": "CPU at capacity, system severely degraded",
  "recommendation": "Immediate intervention - kill runaway processes or add CPU"
}
```

## 示例输出

### 正常情况
```json
{
  "status": "ok",
  "cpu_percent": 45.3,
  "load_avg_1min": 3.2,
  "load_avg_5min": 2.8,
  "cpu_cores": 8,
  "message": "CPU usage is healthy"
}
```

### L1 问题（已修复）
```json
{
  "status": "fixed",
  "level": "L1",
  "cpu_before": 78.5,
  "cpu_after": 52.3,
  "actions": [
    "Throttled backup process (PID 1234)",
    "Killed idle index rebuild (PID 5678)"
  ]
}
```

### L2 问题（需要决策）
```json
{
  "status": "warning",
  "level": "L2",
  "type": "cpu_high",
  "severity": "high",
  "cpu_percent": 88.5,
  "load_avg_1min": 10.2,
  "load_avg_5min": 9.8,
  "cpu_cores": 8,
  "description": "CPU at 88.5%, python process consuming 350% CPU",
  "proposed_fix": "Restart python worker service (PID 1234) or apply CPU quota",
  "risk_assessment": "Medium risk - worker restart causes 30s request queue",
  "details": {
    "user_percent": 75.2,
    "system_percent": 13.3,
    "iowait_percent": 2.1,
    "l1_actions_taken": ["throttled_backup"],
    "suspected_issue": {
      "process": "python",
      "pid": 1234,
      "cpu_percent": 350.0,
      "runtime_hours": 12.5,
      "cmdline": "/usr/bin/python3 /opt/app/worker.py"
    }
  }
}
```

## 相关文档

- `system_health.md` - 总体系统健康检查
- `memory.md` - 内存使用率巡检
- `services.md` - 服务状态巡检
