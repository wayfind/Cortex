# 关键服务状态巡检

## 巡检目标

监控系统关键服务的运行状态，确保核心功能可用。

## 检查方法

### 使用的工具

- `tools/check_services.py` - 检查 systemd 服务状态

### 执行步骤

1. 运行 `python3 tools/check_services.py`
2. 读取配置文件获取需要监控的服务列表
3. 检查每个服务的状态（active/inactive/failed）
4. 检查服务的重启次数和最近日志

## 服务配置

从 `/etc/cortex/config.yaml` 读取 `probe.critical_services` 列表，例如：

```yaml
probe:
  critical_services:
    - nginx
    - mysql
    - redis
    - cortex-monitor  # Cortex Monitor 服务本身
```

## 问题分级

### L1 - 可自动修复

**触发条件**：
- 服务处于 failed 状态
- 服务在配置中标记为 `auto_restart: true`
- 最近 1 小时重启次数 < 3

**修复方法**：
```bash
# 重启服务
systemctl restart <service_name>

# 验证启动成功
systemctl is-active <service_name>
```

**验证方法**：
```bash
# 检查服务状态
systemctl status <service_name>

# 检查服务日志
journalctl -u <service_name> -n 50 --no-pager
```

**执行工具**：
- `tools/manage_service.py --restart <service>` - 安全重启服务

### L2 - 需要决策

**触发条件**：
- 服务频繁重启（1 小时内 >= 3 次）
- 服务处于 failed 状态且未配置自动重启
- 服务依赖的其他服务失败

**建议修复**：
1. **重启服务**（风险：中）
   - 尝试重启已失败的服务
   - 可能需要修复配置或依赖
   - 评估服务中断影响

2. **重启依赖服务链**（风险：高）
   - 如果是依赖问题，重启整个服务链
   - 影响范围较大

3. **回滚配置**（风险：中）
   - 如果是配置变更导致，回滚到之前的版本
   - 需要确认配置备份可用

**风险评估**：
- 重启可能导致数据丢失（如未持久化的缓存）
- 服务链重启影响多个服务
- 回滚配置需要重新应用

**上报信息**：
```json
{
  "failed_service": "mysql",
  "status": "failed",
  "restart_count_1h": 5,
  "last_error": "Job for mysql.service failed",
  "recent_logs": [
    "2025-11-16 10:15:23 [ERROR] Can't open privilege tables",
    "2025-11-16 10:15:24 [ERROR] Fatal error: Can't open and lock privilege tables"
  ],
  "dependencies": ["nginx", "app-server"]
}
```

### L3 - 严重问题

**触发条件**：
- 多个关键服务同时失败
- 服务无法启动（配置错误、依赖缺失）
- 核心服务（如数据库）数据损坏
- 重启多次仍失败

**上报信息**：
```json
{
  "severity": "critical",
  "failed_services": ["mysql", "redis", "nginx"],
  "error_summary": "Multiple critical services down, possible system-wide issue",
  "details": {
    "mysql": {
      "status": "failed",
      "restart_attempts": 5,
      "error": "Cannot start: data directory corruption detected",
      "last_log": "[ERROR] InnoDB: Corruption of an index tree"
    },
    "redis": {
      "status": "failed",
      "restart_attempts": 3,
      "error": "Cannot allocate memory"
    },
    "nginx": {
      "status": "inactive",
      "error": "Dependency mysql.service failed"
    }
  },
  "recommendation": "Immediate manual intervention - data corruption or resource exhaustion"
}
```

## 示例输出

### 正常情况
```json
{
  "status": "ok",
  "services_checked": ["nginx", "mysql", "redis", "cortex-monitor"],
  "all_active": true,
  "message": "All critical services are running"
}
```

### L1 问题（已修复）
```json
{
  "status": "fixed",
  "level": "L1",
  "service": "nginx",
  "action": "restarted",
  "result": "success",
  "details": {
    "status_before": "failed",
    "status_after": "active",
    "restart_time": "2025-11-16T10:15:30Z",
    "verification": "Service responded to health check"
  }
}
```

### L2 问题（需要决策）
```json
{
  "status": "warning",
  "level": "L2",
  "type": "service_failed",
  "severity": "high",
  "service": "mysql",
  "description": "MySQL service failed, restarted 3 times in last hour",
  "proposed_fix": "Investigate root cause and restart with configuration check",
  "risk_assessment": "Medium risk - restart may cause brief downtime",
  "details": {
    "status": "failed",
    "restart_count_1h": 3,
    "restart_count_24h": 8,
    "last_restart": "2025-11-16T10:10:00Z",
    "exit_code": 1,
    "recent_logs": [
      "2025-11-16 10:15:23 [ERROR] Can't connect to MySQL server",
      "2025-11-16 10:15:24 [ERROR] Aborting"
    ],
    "dependent_services": {
      "nginx": "active (degraded - no db backend)",
      "app-server": "active (degraded - read-only mode)"
    }
  }
}
```

## 高级检查

除了基本的服务状态，还可以执行：

### 健康检查端点
对于 web 服务，检查健康检查端点：
```bash
curl -f http://localhost/health || echo "Health check failed"
```

### 端口监听检查
验证服务是否在正确的端口上监听：
```bash
ss -tlnp | grep :<port>
```

### 进程检查
验证服务进程是否存在且正常：
```bash
pgrep -f <service_name>
```

## 相关文档

- `system_health.md` - 总体系统健康检查
- `network.md` - 网络连接巡检
