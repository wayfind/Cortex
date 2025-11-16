# 内存使用率巡检

## 巡检目标

监控系统内存使用率，防止内存耗尽导致 OOM 或性能下降。

## 检查方法

### 使用的工具

- `tools/check_memory.py` - 检查系统内存和 swap 使用率

### 执行步骤

1. 运行 `python3 tools/check_memory.py`
2. 获取物理内存和 swap 的使用情况
3. 对照配置的阈值判断
4. 识别内存占用最大的进程

## 阈值定义

从 `/etc/cortex/config.yaml` 读取 `probe.threshold_memory_percent`，默认值：

| 指标 | 正常 | 警告 | 严重 |
|------|------|------|------|
| 内存使用率 | < 80% | 80-90% | > 90% |
| Swap 使用率 | < 50% | 50-80% | > 80% |

## 问题分级

### L1 - 可自动修复

**触发条件**：
- 内存使用率 80-90%
- 存在可安全终止的临时进程或缓存

**修复方法**：
```bash
# 清理页面缓存（安全操作）
sync && echo 3 > /proc/sys/vm/drop_caches

# 终止已知的临时测试进程
pkill -f "test_runner" || true
```

**验证方法**：
```bash
# 再次检查内存使用率
free -h
```

**执行工具**：
- `tools/cleanup_memory.py --safe` - 安全内存清理脚本

### L2 - 需要决策

**触发条件**：
- 内存使用率 > 90%
- L1 清理后仍超过 85%
- 需要重启服务释放内存

**建议修复**：
1. **重启内存泄漏的服务**（风险：中）
   - 识别内存持续增长的服务
   - 重启该服务释放内存
   - 需要评估服务中断的影响

2. **调整应用内存限制**（风险：低）
   - 降低某些应用的内存上限
   - 需要确认不影响功能

3. **扩容内存**（风险：中）
   - 增加物理内存
   - 需要停机操作

**风险评估**：
- 重启服务会导致短暂不可用
- 调整内存限制可能影响性能
- 扩容需要停机或热插拔支持

**上报信息**：
```json
{
  "memory_percent": 92.5,
  "swap_percent": 65.3,
  "top_consumers": [
    {"process": "java", "pid": 1234, "memory_mb": 8192},
    {"process": "mysql", "pid": 5678, "memory_mb": 4096}
  ],
  "available_mb": 512,
  "l1_cleanup_freed_mb": 256
}
```

### L3 - 严重问题

**触发条件**：
- 内存使用率 > 95%
- 可用内存 < 256MB
- 出现 OOM killer 日志
- L1 清理失败或无效

**上报信息**：
```json
{
  "severity": "critical",
  "memory_percent": 97.8,
  "swap_percent": 98.5,
  "available_mb": 128,
  "oom_events": [
    {
      "timestamp": "2025-11-16T10:15:23Z",
      "killed_process": "chrome",
      "pid": 9876
    }
  ],
  "top_consumers": [
    {"process": "java", "pid": 1234, "memory_mb": 12288},
    {"process": "python", "pid": 2345, "memory_mb": 8192}
  ],
  "error_message": "System near OOM, immediate intervention required",
  "recommendation": "Manually kill non-critical processes or add memory"
}
```

## 示例输出

### 正常情况
```json
{
  "status": "ok",
  "memory_percent": 65.3,
  "swap_percent": 12.5,
  "available_mb": 4096,
  "message": "Memory usage is healthy"
}
```

### L1 问题（已修复）
```json
{
  "status": "fixed",
  "level": "L1",
  "memory_before": 85.2,
  "memory_after": 72.1,
  "freed_mb": 2048,
  "actions": [
    "Dropped page cache: 1536MB",
    "Killed test processes: 512MB"
  ]
}
```

### L2 问题（需要决策）
```json
{
  "status": "warning",
  "level": "L2",
  "type": "memory_high",
  "severity": "high",
  "memory_percent": 91.5,
  "swap_percent": 45.2,
  "available_mb": 512,
  "description": "Memory at 91.5%, likely memory leak in java process",
  "proposed_fix": "Restart java application (PID 1234)",
  "risk_assessment": "Medium risk - 30s downtime for app restart",
  "details": {
    "total_mb": 16384,
    "used_mb": 14992,
    "available_mb": 512,
    "l1_cleanup_freed_mb": 256,
    "suspected_leak": {
      "process": "java",
      "pid": 1234,
      "memory_mb": 8192,
      "memory_growth_1h": 2048
    }
  }
}
```

## 相关文档

- `system_health.md` - 总体系统健康检查
- `cpu.md` - CPU 使用率巡检
- `services.md` - 服务状态巡检
