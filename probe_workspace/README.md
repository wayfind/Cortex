# Probe Workspace - 文档驱动工作区

这是 Cortex Probe 的文档驱动工作区，包含巡检文档、检查工具和角色定义。

## 概述

Probe Workspace 是 Cortex Probe Web 服务的工作目录，存放：
- **巡检文档** (`inspections/*.md`) - 定义巡检要求和分级标准
- **检查工具** (`tools/*.py`) - 数据采集和修复脚本
- **角色定义** (`CLAUDE.md`) - Probe Agent 的职责和工作流程
- **输出目录** (`output/`) - 报告和日志

## 工作原理

```
┌──────────────────────┐
│   Probe Web 服务      │
│   (FastAPI)          │
└──────────┬───────────┘
           │
           │ 周期性触发
           ▼
┌──────────────────────┐
│   Claude Executor    │
│   执行 claude -p      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Probe Workspace      │
│  - 读取 CLAUDE.md    │
│  - 扫描 inspections/ │
│  - 调用 tools/       │
│  - 输出到 output/    │
└──────────────────────┘
```

Probe Web 服务会周期性地调用 `claude -p`，LLM 读取此工作区的文档并执行巡检。

## 目录结构

```
probe_workspace/
├── CLAUDE.md              # Probe Agent 角色定义
├── README.md              # 本文件
├── inspections/           # 巡检要求文档
│   ├── TEMPLATE.md        # 模板文件
│   ├── disk_space.md      # 磁盘空间巡检
│   ├── memory.md          # 内存使用巡检
│   ├── cpu.md             # CPU 负载巡检
│   └── services.md        # 服务状态巡检
├── tools/                 # 检查和修复工具
│   ├── check_disk.py
│   ├── check_memory.py
│   ├── check_cpu.py
│   ├── check_services.py
│   ├── cleanup_disk.py    # L1 修复工具
│   ├── report_builder.py  # 报告构建
│   └── report_to_monitor.py
├── output/                # 输出目录
│   ├── report.json        # 最新报告
│   └── probe.log          # 执行日志
└── mcp/                   # MCP 配置（预留）
```

## 核心文件说明

### CLAUDE.md

定义 Probe Agent 的角色、职责和工作流程。LLM 会首先读取这个文件来理解自己的任务。

### inspections/*.md

每个文件定义一个巡检项，包含：
- 巡检目标
- 使用的工具
- 阈值定义
- L1/L2/L3 分级标准
- 修复方法

### tools/*.py

数据采集和修复脚本，输出标准 JSON 格式。

## 添加新的巡检项

### 步骤

1. **复制模板**
   ```bash
   cd probe_workspace/inspections
   cp TEMPLATE.md my_new_check.md
   ```

2. **编辑巡检文档**
   ```bash
   nano my_new_check.md
   ```

   定义：
   - 巡检目标和意义
   - 使用的检查工具
   - 正常/警告/严重的阈值
   - L1/L2/L3 分级标准
   - 每个级别的处理方法

3. **（可选）创建检查工具**

   如果需要专门的检查脚本：
   ```bash
   cd probe_workspace/tools
   nano check_my_new.py
   ```

   输出标准 JSON 格式：
   ```json
   {
     "status": "ok" | "warning" | "error",
     "metric_value": 42.5,
     "message": "Check description",
     "details": {...}
   }
   ```

4. **测试**

   手动触发 Probe 执行：
   ```bash
   curl -X POST http://localhost:8001/execute
   ```

   查看日志：
   ```bash
   tail -f logs/probe.log
   ```

就这么简单！下次 Probe 执行时，会自动包含新的巡检项。

## 问题分级

### L1 - 可自动修复

**特征**：
- 风险低、影响小
- 有标准修复流程
- 不需要人工审批

**示例**：
- 清理临时文件（磁盘使用 80-90%）
- 清理日志（日志文件 > 1GB）
- 清理缓存

**处理**：Probe 直接执行修复，记录到 `actions_taken`

### L2 - 需要决策

**特征**：
- 有一定风险
- 需要权衡利弊
- 可能影响服务

**示例**：
- 重启内存泄漏的服务
- 调整资源配额
- 清理业务数据

**处理**：上报给 Monitor，由 Monitor 的 L2 决策引擎分析

### L3 - 严重问题

**特征**：
- 严重故障
- 数据风险
- 未知错误

**示例**：
- 数据库连接失败
- 磁盘故障
- 安全漏洞

**处理**：立即告警，通知人工介入

## 工具脚本规范

### 检查工具输出格式

所有检查工具必须输出 JSON 到 stdout：

```json
{
  "status": "ok" | "warning" | "error",
  "metric_name": "cpu_percent",
  "metric_value": 45.2,
  "threshold": 70.0,
  "message": "CPU usage is normal",
  "details": {
    "1min": 0.85,
    "5min": 0.92,
    "15min": 1.01
  }
}
```

### 修复工具输出格式

L1 修复工具输出：

```json
{
  "action": "cleaned_temp_files",
  "result": "success" | "failed",
  "before": {
    "disk_usage_percent": 85.2,
    "free_space_gb": 15.3
  },
  "after": {
    "disk_usage_percent": 72.1,
    "free_space_gb": 28.9
  },
  "freed_space_gb": 13.6,
  "details": [
    "Cleaned /tmp: 8.5GB",
    "Cleaned old logs: 5.1GB"
  ]
}
```

## 使用 Probe Workspace

### 本地测试

如果你想在本地测试文档驱动的巡检（不通过 Probe Web 服务）：

```bash
cd probe_workspace

# 手动调用 claude -p
claude -p "Execute a full system inspection as a Cortex Probe Agent. Read CLAUDE.md and follow the workflow."
```

### 配置 Workspace 路径

在 Probe 配置中指定 workspace 路径：

```yaml
# config.yaml
probe:
  workspace: "/path/to/probe_workspace"
```

### 查看执行结果

```bash
# 查看最新报告
cat probe_workspace/output/report.json | python3 -m json.tool

# 查看执行日志
tail -f probe_workspace/output/probe.log
```

## 最佳实践

1. **文档清晰**：巡检文档要清楚描述目标、阈值和分级标准
2. **工具简单**：检查工具只负责数据采集，输出标准 JSON
3. **职责分离**：文档定义"做什么"，工具提供"数据"，LLM 决定"如何做"
4. **版本控制**：将 workspace 纳入 Git 管理，跟踪变更
5. **测试充分**：新增巡检项后，手动触发执行验证

## 示例：网络监控

假设要添加网络连接监控：

**1. 创建文档** (`inspections/network.md`)：
```markdown
# 网络连接巡检

## 巡检目标
监控关键服务的网络连接状态

## 使用的工具
- `tools/check_network.py`

## L1 - 可自动修复
防火墙规则异常 → 恢复规则

## L2 - 需要决策
服务端口未监听 → 需要重启服务？

## L3 - 严重问题
DNS 解析失败 → 人工介入
```

**2. 创建工具** (`tools/check_network.py`)：
```python
#!/usr/bin/env python3
import json
import socket

result = {
    "status": "ok",
    "ports_listening": {
        "80": check_port(80),
        "443": check_port(443)
    }
}
print(json.dumps(result))
```

**3. 测试**：
```bash
curl -X POST http://localhost:8001/execute
```

完成！

## 与 Probe Web 服务集成

Probe Workspace 由 Probe Web 服务自动使用：

- **读取**：`claude -p` 从这里读取文档和工具
- **写入**：执行结果写入 `output/` 目录
- **调度**：由 Probe Web 服务的 APScheduler 管理
- **监控**：通过 Probe API 查询执行状态

无需手动配置 cron 或运行脚本，一切由 Probe Web 服务管理。

## 故障排查

### 巡检未执行

检查 Probe Web 服务状态：
```bash
curl http://localhost:8001/status
```

查看调度信息：
```bash
curl http://localhost:8001/schedule
```

### 工具脚本失败

查看执行日志：
```bash
tail -100 probe_workspace/output/probe.log
```

手动测试工具：
```bash
cd probe_workspace
python3 tools/check_disk.py
```

### 报告格式错误

验证 JSON 格式：
```bash
cat output/report.json | python3 -m json.tool
```

## 相关文档

- [Probe 工作流程详解](../docs/probe_workflow.md)
- [Probe API 文档](../docs/probe_validation.md)
- [CLAUDE.md](CLAUDE.md) - Agent 角色定义
- [巡检模板](inspections/TEMPLATE.md)
