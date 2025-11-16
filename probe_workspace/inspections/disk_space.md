# 磁盘空间巡检

## 巡检目标

监控系统磁盘使用率，防止磁盘空间耗尽导致服务故障。

## 检查方法

### 使用的工具

- `tools/check_disk.py` - 检查所有挂载点的磁盘使用率

### 执行步骤

1. 运行 `python3 tools/check_disk.py`
2. 获取所有挂载点的使用率
3. 对照配置的阈值判断
4. 识别可清理的目录

## 阈值定义

从 `/etc/cortex/config.yaml` 读取 `probe.threshold_disk_percent`，默认值：

| 指标 | 正常 | 警告 | 严重 |
|------|------|------|------|
| 磁盘使用率 | < 80% | 80-90% | > 90% |

## 问题分级

### L1 - 可自动修复

**触发条件**：
- 磁盘使用率 80-90%
- 存在可安全清理的临时文件

**修复方法**：
```bash
# 清理 /tmp 目录（7天前的文件）
find /tmp -type f -atime +7 -delete

# 清理旧日志（30天前的 .gz 文件）
find /var/log -name "*.gz" -mtime +30 -delete

# 清理包管理器缓存
apt-get clean  # Debian/Ubuntu
yum clean all  # RHEL/CentOS
```

**验证方法**：
```bash
# 再次检查磁盘使用率
df -h
```

**执行工具**：
- `tools/cleanup_disk.py --safe` - 安全清理脚本

### L2 - 需要决策

**触发条件**：
- 磁盘使用率 > 90%
- L1 清理后仍超过 85%
- 需要删除应用数据或日志

**建议修复**：
1. **清理应用日志**（风险：低）
   - 删除 30 天前的应用日志
   - 需要确认应用不再需要这些日志

2. **压缩归档**（风险：低）
   - 将旧数据压缩归档到其他存储
   - 需要额外的存储空间

3. **扩容磁盘**（风险：中）
   - 增加磁盘容量
   - 需要停机或在线扩容

**风险评估**：
- 清理日志可能影响问题排查
- 压缩归档需要 I/O 资源
- 扩容可能需要重启服务

**上报信息**：
```json
{
  "disk_usage_percent": 92.5,
  "largest_directories": [
    {"/var/log": "15GB"},
    {"/tmp": "8GB"},
    {"/opt/app/data": "45GB"}
  ],
  "available_space_gb": 5.2,
  "l1_cleanup_freed_gb": 2.3
}
```

### L3 - 严重问题

**触发条件**：
- 磁盘使用率 > 95%
- 可用空间 < 1GB
- L1 清理失败或无法清理

**上报信息**：
```json
{
  "severity": "critical",
  "disk_usage_percent": 97.8,
  "available_space_mb": 512,
  "filesystem": "/dev/sda1",
  "mount_point": "/",
  "largest_files": [
    "/var/log/app.log: 25GB",
    "/tmp/dump.sql: 18GB"
  ],
  "error_message": "L1 cleanup failed or insufficient",
  "recommendation": "Immediate manual intervention required"
}
```

## 示例输出

### 正常情况
```json
{
  "status": "ok",
  "disk_usage_percent": 65.3,
  "available_space_gb": 125.7,
  "message": "Disk space is healthy"
}
```

### L1 问题（已修复）
```json
{
  "status": "fixed",
  "level": "L1",
  "disk_usage_before": 85.2,
  "disk_usage_after": 72.1,
  "freed_space_gb": 15.8,
  "actions": [
    "Cleaned /tmp: 8.5GB",
    "Cleaned old logs: 5.2GB",
    "Cleaned apt cache: 2.1GB"
  ]
}
```

### L2 问题（需要决策）
```json
{
  "status": "warning",
  "level": "L2",
  "type": "disk_space_high",
  "severity": "high",
  "disk_usage_percent": 91.5,
  "available_space_gb": 8.2,
  "description": "Disk usage at 91.5%, L1 cleanup only freed 3GB",
  "proposed_fix": "Archive or delete old application logs (30+ days)",
  "risk_assessment": "Low risk - logs older than 30 days rarely needed",
  "details": {
    "filesystem": "/dev/sda1",
    "mount_point": "/",
    "total_gb": 100,
    "used_gb": 91.5,
    "l1_cleanup_freed_gb": 3.0,
    "large_log_files": {
      "/var/log/app/app.log": "12GB",
      "/var/log/nginx/access.log": "8GB"
    }
  }
}
```

## 相关文档

- `system_health.md` - 总体系统健康检查
- `log_rotation.md` - 日志轮转巡检
