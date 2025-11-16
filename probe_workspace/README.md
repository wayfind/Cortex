# Cortex Probe - 文档驱动模式

基于 `claude -p` 的智能巡检系统。

## 概述

Cortex Probe 是一个智能的系统巡检工具，通过文档驱动的方式实现灵活、可扩展的运维自动化。

### 核心特性

- **文档即代码**：巡检要求通过 Markdown 文档定义，无需编程
- **智能决策**：LLM 根据上下文自主判断问题级别和修复方案
- **三级分类**：L1 自动修复、L2 决策请求、L3 人工介入
- **易于扩展**：新增巡检项只需添加一个 .md 文件

### 工作原理

```
cron 触发 → run_probe.sh → claude -p 读取文档 → 执行巡检 → 生成报告 → 上报 Monitor
```

## 安装

### 前置要求

1. **Claude Code**：从 https://code.claude.com 安装
2. **Python 3.8+**：系统需要 Python 3
3. **Root 权限**：安装需要 root 权限

### 安装步骤

```bash
# 1. 切换到 probe_workspace 目录
cd probe_workspace

# 2. 运行安装脚本
sudo ./install.sh
```

安装脚本会：
- 将文件复制到 `/opt/cortex/probe`
- 安装 Python 依赖
- 创建配置文件 `/etc/cortex/config.yaml`
- （可选）设置 cron 定时任务

## 配置

编辑配置文件：

```bash
sudo nano /etc/cortex/config.yaml
```

关键配置项：

```yaml
agent:
  # 节点唯一标识（必须修改）
  id: "agent-prod-001"

  # 上游 Monitor URL（独立模式下留空）
  upstream_monitor_url: "http://monitor.example.com:8000"

  # Monitor API 密钥
  monitor_api_key: "your-api-key"

probe:
  # Cron 调度表达式
  schedule: "0 * * * *"  # 每小时

  # 阈值配置
  threshold_disk_percent: 80
  threshold_memory_percent: 80
  threshold_cpu_percent: 70

  # 关键服务列表
  critical_services:
    - nginx
    - mysql
    - redis
```

## 使用

### 手动执行

```bash
# 进入安装目录
cd /opt/cortex/probe

# 执行巡检
sudo ./run_probe.sh

# 查看日志
tail -f /var/log/cortex-probe.log
```

### 自动执行（Cron）

如果安装时配置了 cron，系统会自动按计划执行。

查看 cron 任务：
```bash
sudo crontab -l
```

手动添加 cron（如果未自动配置）：
```bash
sudo crontab -e
# 添加以下行：
0 * * * * /opt/cortex/probe/run_probe.sh >> /var/log/cortex-probe.log 2>&1
```

### 查看报告

最新的报告位于：
```bash
cat /opt/cortex/probe/output/report.json | python3 -m json.tool
```

## 添加新的巡检项

### 步骤

1. **复制模板**
   ```bash
   cd /opt/cortex/probe/inspections
   cp TEMPLATE.md my_new_check.md
   ```

2. **编辑巡检文档**
   ```bash
   nano my_new_check.md
   ```

   填写：
   - 巡检目标
   - 检查方法
   - 阈值定义
   - L1/L2/L3 分级标准

3. **（可选）创建检查工具**

   如果需要专门的检查脚本：
   ```bash
   cd /opt/cortex/probe/tools
   nano check_my_new.py
   ```

   输出标准 JSON 格式：
   ```json
   {
     "status": "ok" | "warning" | "error",
     "metric_value": 42.5,
     "message": "Check description"
   }
   ```

4. **测试**
   ```bash
   sudo /opt/cortex/probe/run_probe.sh
   ```

就这么简单！下次执行时，Probe 会自动包含新的巡检项。

## 问题分级

### L1 - 可自动修复

**特征**：
- 风险低、影响小
- 有标准修复流程
- 不需要人工审批

**示例**：
- 清理临时文件
- 重启已挂起的服务
- 清理缓存

**处理**：Probe 直接执行修复，记录到 actions_taken

### L2 - 需要决策

**特征**：
- 有一定风险
- 需要权衡利弊
- 可能影响服务

**示例**：
- 重启内存泄漏的服务
- 调整资源配额
- 清理业务数据

**处理**：上报给 Monitor，由 LLM 或人工决策

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

## 目录结构

```
/opt/cortex/probe/
├── CLAUDE.md                 # Probe Agent 角色定义
├── run_probe.sh             # 执行脚本
├── install.sh               # 安装脚本
├── inspections/             # 巡检要求文档
│   ├── TEMPLATE.md          # 模板
│   ├── disk_space.md
│   ├── memory.md
│   ├── cpu.md
│   └── services.md
├── tools/                   # 工具脚本
│   ├── check_*.py           # 检查工具
│   ├── cleanup_*.py         # 清理工具
│   ├── report_builder.py    # 报告构建
│   └── report_to_monitor.py # 上报工具
├── output/                  # 输出目录
│   ├── report.json          # 最新报告
│   └── probe.log            # 执行日志
└── mcp/                     # MCP 配置（预留）
```

## 工具脚本

### 检查工具

所有检查工具输出标准 JSON：

```bash
python3 tools/check_disk.py
python3 tools/check_memory.py
python3 tools/check_cpu.py
python3 tools/check_services.py
```

### 清理工具

```bash
# 磁盘清理（L1）
python3 tools/cleanup_disk.py --safe --dry-run

# 实际执行
sudo python3 tools/cleanup_disk.py --safe
```

### 报告工具

```bash
# 构建报告
python3 tools/report_builder.py \
  --disk disk_result.json \
  --memory memory_result.json \
  --cpu cpu_result.json \
  -o report.json

# 上报到 Monitor
python3 tools/report_to_monitor.py report.json
```

## 故障排除

### Probe 不执行

1. 检查 cron 是否配置：
   ```bash
   sudo crontab -l
   ```

2. 检查 Claude Code 是否安装：
   ```bash
   claude --version
   ```

3. 手动执行测试：
   ```bash
   sudo /opt/cortex/probe/run_probe.sh
   ```

### 报告上传失败

1. 检查 Monitor URL 配置：
   ```bash
   grep upstream_monitor_url /etc/cortex/config.yaml
   ```

2. 测试网络连接：
   ```bash
   curl -I http://monitor.example.com:8000/api/health
   ```

3. 查看详细日志：
   ```bash
   tail -100 /var/log/cortex-probe.log
   ```

### Python 依赖问题

重新安装依赖：
```bash
sudo pip3 install -r /opt/cortex/probe/requirements.txt
```

## 高级用法

### 调试模式

```bash
CORTEX_DEBUG=1 sudo /opt/cortex/probe/run_probe.sh
```

### 自定义工作目录

```bash
PROBE_WORKSPACE=/custom/path sudo ./run_probe.sh
```

### Dry-run 模式

测试报告生成但不上传：
```bash
python3 tools/report_to_monitor.py report.json --dry-run
```

## 与旧版本的区别

| 特性 | 旧版（Python SDK） | 新版（文档驱动） |
|------|------------------|-----------------|
| 巡检定义 | Python 代码 | Markdown 文档 |
| 扩展方式 | 修改代码 | 添加文档 |
| 决策引擎 | 硬编码规则 | LLM 智能分析 |
| 维护成本 | 高 | 低 |
| 可读性 | 需要编程知识 | 运维人员可读写 |

## 贡献

欢迎贡献新的巡检项！只需：

1. 在 `inspections/` 目录添加新的 .md 文件
2. 遵循 TEMPLATE.md 的格式
3. 提交 PR

## 许可证

见项目根目录的 LICENSE 文件。
