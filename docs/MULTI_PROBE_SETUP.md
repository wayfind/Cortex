# 多 Probe 不同巡检方案部署指南

本文档说明如何在 Docker 环境中部署多个 Probe，每个 Probe 使用不同的巡检方案。

## 核心概念

每个 Probe 通过 `probe_workspace/` 目录中的文档来定义巡检规则。通过挂载不同的 workspace 目录，可以实现：

- **不同的巡检内容**：Web 服务、数据库、K8s、安全审计等
- **不同的巡检频率**：每小时、每 15 分钟、每天等
- **不同的阈值配置**：根据服务类型调整 CPU/内存/磁盘阈值
- **不同的日志级别**：关键服务使用 DEBUG，普通服务使用 INFO

## 目录结构

```
cortex/
├── probe_workspaces/           # 各类 Probe 的 workspace 目录
│   ├── web/                    # Web 服务监控 workspace
│   │   ├── README.md          # 巡检说明文档
│   │   ├── check_nginx.md     # Nginx 巡检规则
│   │   ├── check_apache.md    # Apache 巡检规则
│   │   └── output/            # 巡检输出目录
│   ├── database/               # 数据库监控 workspace
│   │   ├── README.md
│   │   ├── check_postgres.md  # PostgreSQL 巡检规则
│   │   ├── check_mysql.md     # MySQL 巡检规则
│   │   └── output/
│   ├── kubernetes/             # K8s 监控 workspace
│   │   ├── README.md
│   │   ├── check_pods.md      # Pod 健康检查
│   │   ├── check_nodes.md     # Node 资源检查
│   │   └── output/
│   └── security/               # 安全审计 workspace
│       ├── README.md
│       ├── check_vulnerabilities.md  # 漏洞扫描
│       ├── check_compliance.md       # 合规检查
│       └── output/
├── docker-compose.multi-probe.yml    # 多 Probe 部署配置
└── .env                               # 环境变量配置
```

## 快速开始

### 1. 创建 Workspace 目录

```bash
# 创建各类 Probe 的 workspace
mkdir -p probe_workspaces/{web,database,kubernetes,security}/output

# 复制基础 README 模板
for dir in probe_workspaces/*; do
    cp probe_workspace/README.md "$dir/"
done
```

### 2. 编写巡检规则

#### Web 服务巡检示例

创建 `probe_workspaces/web/check_nginx.md`：

```markdown
# Nginx 健康巡检

## 巡检目标

检查 Nginx 服务的运行状态、配置正确性和性能指标。

## 巡检项目

### 1. 服务状态
- [ ] Nginx 进程是否运行
- [ ] 端口监听是否正常（80, 443）
- [ ] systemd 服务状态

### 2. 配置检查
- [ ] 配置文件语法是否正确 (`nginx -t`)
- [ ] 虚拟主机配置
- [ ] SSL 证书有效期

### 3. 性能指标
- [ ] 请求响应时间
- [ ] 并发连接数
- [ ] 错误率

### 4. 日志分析
- [ ] access.log 中的异常请求
- [ ] error.log 中的错误信息
- [ ] 最近 1 小时的 5xx 错误统计

## 自动修复建议

- **L1**: 重启 Nginx 服务（如果进程挂掉）
- **L2**: 重新加载配置（如果配置更新）
- **L3**: 严重错误需人工介入

## 告警阈值

- 5xx 错误率 > 1%: 触发 L2 告警
- Nginx 进程不存在: 触发 L3 告警
- SSL 证书 < 7 天过期: 触发 L3 告警
```

#### 数据库巡检示例

创建 `probe_workspaces/database/check_postgres.md`：

```markdown
# PostgreSQL 健康巡检

## 巡检目标

检查 PostgreSQL 数据库的运行状态、性能和数据完整性。

## 巡检项目

### 1. 服务状态
- [ ] PostgreSQL 进程是否运行
- [ ] 端口监听（5432）
- [ ] 可以建立连接

### 2. 数据库健康
- [ ] 主从复制状态（如果有）
- [ ] 长时间运行的查询
- [ ] 死锁检测
- [ ] 表膨胀率

### 3. 性能指标
- [ ] 连接数 / 最大连接数
- [ ] 慢查询日志分析
- [ ] 缓存命中率
- [ ] 事务提交率

### 4. 备份检查
- [ ] 最后一次备份时间
- [ ] 备份文件完整性
- [ ] WAL 归档状态

## 自动修复建议

- **L1**: 终止长时间运行的查询
- **L2**: 重启数据库服务（需批准）
- **L3**: 数据损坏需人工介入

## 告警阈值

- 连接数 > 90%: L2 告警
- 慢查询 > 10s: L2 告警
- 备份失败: L3 告警
- 主从延迟 > 60s: L2 告警
```

#### Kubernetes 巡检示例

创建 `probe_workspaces/kubernetes/check_pods.md`：

```markdown
# Kubernetes Pod 健康巡检

## 巡检目标

检查 K8s 集群中 Pod 的运行状态和资源使用。

## 巡检项目

### 1. Pod 状态
- [ ] CrashLoopBackOff 的 Pod
- [ ] Pending 状态的 Pod
- [ ] ImagePullBackOff 的 Pod
- [ ] Evicted 的 Pod

### 2. 资源使用
- [ ] CPU 使用率 > 阈值的 Pod
- [ ] 内存使用率 > 阈值的 Pod
- [ ] 磁盘使用率

### 3. 配置检查
- [ ] 资源 requests/limits 配置
- [ ] 健康检查（liveness/readiness probe）
- [ ] 重启次数异常

### 4. 日志分析
- [ ] 最近 1 小时的错误日志
- [ ] OOMKilled 事件

## 自动修复建议

- **L1**: 重启异常 Pod
- **L2**: 调整资源配额（需批准）
- **L3**: 集群级别问题需人工介入

## 告警阈值

- Pod 重启 > 5 次/小时: L2 告警
- CrashLoopBackOff: L2 告警
- OOMKilled: L2 告警
- 集群节点 NotReady: L3 告警
```

### 3. 配置环境变量

编辑 `.env` 文件：

```bash
# 共享配置
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
CORTEX_MONITOR_REGISTRATION_TOKEN=your-secret-token
CORTEX_AUTH_SECRET_KEY=your-jwt-secret-min-32-chars

# Monitor 配置
CORTEX_MONITOR_PORT=8000

# 前端配置
CORTEX_FRONTEND_PORT=3000

# 日志级别
CORTEX_LOG_LEVEL=INFO
```

### 4. 启动多 Probe 环境

```bash
# 使用多 Probe 配置文件
docker-compose -f docker-compose.multi-probe.yml up -d

# 查看所有服务状态
docker-compose -f docker-compose.multi-probe.yml ps

# 查看特定 Probe 日志
docker-compose -f docker-compose.multi-probe.yml logs -f cortex-probe-web
docker-compose -f docker-compose.multi-probe.yml logs -f cortex-probe-database
```

### 5. 验证部署

```bash
# 检查 Monitor
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/agents

# 检查各个 Probe
curl http://localhost:8011/health  # Web Probe
curl http://localhost:8012/health  # Database Probe
curl http://localhost:8013/health  # K8s Probe
curl http://localhost:8014/health  # Security Probe

# 在 Monitor API 中查看注册的 Probe
curl http://localhost:8000/api/v1/agents | jq
```

## Probe 配置详解

### 巡检频率配置

使用 Cron 表达式配置巡检频率：

```yaml
# 每小时执行
CORTEX_PROBE_SCHEDULE=0 * * * *

# 每 30 分钟执行
CORTEX_PROBE_SCHEDULE=*/30 * * * *

# 每 15 分钟执行
CORTEX_PROBE_SCHEDULE=*/15 * * * *

# 每天凌晨 2 点执行
CORTEX_PROBE_SCHEDULE=0 2 * * *

# 每周日凌晨 3 点执行
CORTEX_PROBE_SCHEDULE=0 3 * * 0
```

### 阈值配置

根据服务类型调整阈值：

```yaml
# Web 服务（相对宽松）
CORTEX_PROBE_THRESHOLD_CPU_PERCENT=85.0
CORTEX_PROBE_THRESHOLD_MEMORY_PERCENT=90.0
CORTEX_PROBE_THRESHOLD_DISK_PERCENT=85.0

# 数据库（严格）
CORTEX_PROBE_THRESHOLD_CPU_PERCENT=70.0
CORTEX_PROBE_THRESHOLD_MEMORY_PERCENT=80.0
CORTEX_PROBE_THRESHOLD_DISK_PERCENT=80.0

# K8s（中等）
CORTEX_PROBE_THRESHOLD_CPU_PERCENT=75.0
CORTEX_PROBE_THRESHOLD_MEMORY_PERCENT=85.0
CORTEX_PROBE_THRESHOLD_DISK_PERCENT=90.0
```

### 超时配置

根据巡检复杂度调整超时时间：

```yaml
# 简单巡检（Web 服务）
CORTEX_PROBE_TIMEOUT_SECONDS=300  # 5 分钟

# 复杂巡检（数据库）
CORTEX_PROBE_TIMEOUT_SECONDS=600  # 10 分钟

# 非常复杂巡检（K8s/安全审计）
CORTEX_PROBE_TIMEOUT_SECONDS=1800  # 30 分钟
```

## 高级场景

### 场景 1: 多环境部署

为不同环境（dev/staging/prod）部署不同的 Probe：

```yaml
# 开发环境 Probe
cortex-probe-dev:
  environment:
    - CORTEX_AGENT_ID=probe-dev-001
    - CORTEX_PROBE_SCHEDULE=0 * * * *  # 每小时
  volumes:
    - ./probe_workspaces/dev:/app/probe_workspace

# 生产环境 Probe
cortex-probe-prod:
  environment:
    - CORTEX_AGENT_ID=probe-prod-001
    - CORTEX_PROBE_SCHEDULE=*/15 * * * *  # 每 15 分钟（更频繁）
  volumes:
    - ./probe_workspaces/prod:/app/probe_workspace
```

### 场景 2: 地域分布部署

为不同地域部署 Probe：

```yaml
# 北京节点
cortex-probe-beijing:
  environment:
    - CORTEX_AGENT_ID=probe-beijing-001
    - CORTEX_AGENT_NAME=Beijing Probe
  volumes:
    - ./probe_workspaces/beijing:/app/probe_workspace

# 上海节点
cortex-probe-shanghai:
  environment:
    - CORTEX_AGENT_ID=probe-shanghai-001
    - CORTEX_AGENT_NAME=Shanghai Probe
  volumes:
    - ./probe_workspaces/shanghai:/app/probe_workspace
```

### 场景 3: 专项巡检

为特定任务创建专项 Probe：

```yaml
# 备份验证 Probe（每天凌晨验证备份）
cortex-probe-backup-verify:
  environment:
    - CORTEX_AGENT_ID=probe-backup-001
    - CORTEX_PROBE_SCHEDULE=0 1 * * *  # 每天凌晨 1 点
  volumes:
    - ./probe_workspaces/backup_verify:/app/probe_workspace

# 性能测试 Probe（每周执行一次）
cortex-probe-performance:
  environment:
    - CORTEX_AGENT_ID=probe-perf-001
    - CORTEX_PROBE_SCHEDULE=0 3 * * 0  # 每周日凌晨 3 点
  volumes:
    - ./probe_workspaces/performance:/app/probe_workspace
```

## 管理和监控

### 查看 Probe 状态

```bash
# Web UI 查看
# 访问 http://localhost:3000/nodes

# API 查看所有 Probe
curl http://localhost:8000/api/v1/agents | jq '.[] | {id, name, status, health}'

# 查看特定 Probe 的详细信息
curl http://localhost:8000/api/v1/agents/probe-web-001 | jq
```

### 查看巡检报告

```bash
# 查看最近的巡检报告
curl http://localhost:8000/api/v1/reports?agent_id=probe-web-001&limit=10 | jq

# 查看特定报告
curl http://localhost:8000/api/v1/reports/{report_id} | jq
```

### 手动触发巡检

```bash
# 通过 Probe API 手动触发
curl -X POST http://localhost:8011/execute

# 通过 WebSocket 实时查看执行过程
# 见 WebSocket 文档
```

### 日志管理

```bash
# 查看所有 Probe 日志
docker-compose -f docker-compose.multi-probe.yml logs

# 查看特定 Probe 日志
docker-compose -f docker-compose.multi-probe.yml logs cortex-probe-web

# 实时跟踪日志
docker-compose -f docker-compose.multi-probe.yml logs -f cortex-probe-database

# 查看日志文件
docker exec cortex-probe-web tail -f /app/logs/probe-web.log
```

## 最佳实践

### 1. Workspace 版本控制

将 workspace 目录纳入 Git 管理：

```bash
git add probe_workspaces/
git commit -m "Add probe workspace configurations"
```

### 2. 使用配置模板

创建通用的巡检模板，然后为每个环境定制：

```
probe_workspaces/
├── _templates/          # 通用模板
│   ├── check_template.md
│   └── README_template.md
├── web/                 # 基于模板定制
├── database/
└── kubernetes/
```

### 3. 环境变量分离

为每个环境创建独立的 `.env` 文件：

```bash
.env.dev
.env.staging
.env.prod
```

使用时指定：

```bash
docker-compose --env-file .env.prod -f docker-compose.multi-probe.yml up -d
```

### 4. 定期审查巡检规则

- 每月审查巡检文档的有效性
- 根据实际情况调整阈值
- 优化巡检频率

### 5. 监控 Probe 性能

- 关注巡检执行时间
- 监控 Probe 资源使用
- 避免巡检任务重叠

## 故障排查

### Probe 无法注册

检查：
1. Monitor 服务是否运行
2. `CORTEX_AGENT_UPSTREAM_MONITOR_URL` 是否正确
3. `CORTEX_MONITOR_REGISTRATION_TOKEN` 是否匹配

### Workspace 挂载失败

检查：
1. Workspace 目录是否存在
2. 目录权限是否正确
3. docker-compose.yml 中的卷挂载路径

### 巡检不执行

检查：
1. Cron 表达式是否正确
2. Probe 日志中的错误信息
3. Claude API Key 是否有效

## 参考资料

- [Probe 工作流程文档](./probe_workflow.md)
- [Docker 部署指南](./DOCKER_DEPLOYMENT.md)
- [配置参考](./CONFIGURATION.md)
- [Cron 表达式参考](https://crontab.guru/)
