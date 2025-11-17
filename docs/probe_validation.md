# Probe 新架构验证清单

本文档提供了验证 Probe 新架构的完整清单和测试步骤。

## 架构概览

新的 Probe 架构包含以下组件：

1. **FastAPI Web 服务** (`cortex/probe/app.py`)
   - REST API 端点
   - WebSocket 实时通信
   - 健康检查和状态查询

2. **APScheduler 调度服务** (`cortex/probe/scheduler_service.py`)
   - 周期性任务调度
   - 执行历史管理
   - 暂停/恢复控制

3. **Claude 执行器** (`cortex/probe/claude_executor.py`)
   - 异步执行 `claude -p` 命令
   - 超时处理
   - 报告解析

4. **WebSocket 管理器** (`cortex/probe/websocket_manager.py`)
   - 连接管理
   - 实时事件广播

5. **CLI 入口** (`cortex/probe/cli.py`)
   - 启动 uvicorn 服务器
   - 配置加载
   - 命令行参数解析

## 验证步骤

### 1. 环境准备

```bash
# 克隆代码
git clone <repo-url>
cd cortex

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .
```

### 2. 配置文件准备

创建 `.env`：

```yaml
agent:
  id: "probe-dev-01"
  name: "Development Probe"
  mode: "standalone"

probe:
  host: "127.0.0.1"
  port: 8001
  schedule: "*/5 * * * *"  # 每 5 分钟
  timeout_seconds: 300
  workspace: "./probe_workspace"

monitor:
  host: "127.0.0.1"
  port: 8000
  database_url: "sqlite:///./cortex.db"
  registration_token: "dev-token-123"

claude:
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-sonnet-4"

logging:
  level: "DEBUG"
  file: "logs/cortex.log"
```

### 3. 单元测试

```bash
# 运行所有测试
pytest tests/probe/ -v

# 运行特定测试
pytest tests/probe/test_probe_service.py -v

# 运行测试并查看覆盖率
pytest tests/probe/ --cov=cortex.probe --cov-report=html
```

**预期结果**：
- ✅ 所有测试通过
- ✅ 测试覆盖率 > 80%

### 4. 手动启动测试

```bash
# 启动 Probe 服务
cortex-probe --config .env --log-level DEBUG

# 或使用开发模式（自动重载）
cortex-probe --config .env --reload
```

**预期输出**：
```
INFO:     Starting Cortex Probe Web Service...
INFO:     Binding to 127.0.0.1:8001
INFO:     Workspace: ./probe_workspace
INFO:     Schedule: */5 * * * *
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     ProbeSchedulerService initialized
INFO:     Scheduled inspection with cron: */5 * * * *
INFO:     ProbeSchedulerService started successfully
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8001
```

### 5. API 端点测试

在另一个终端执行：

#### 5.1 健康检查

```bash
curl http://127.0.0.1:8001/health
```

**预期响应**：
```json
{
  "status": "healthy",
  "scheduler_running": true,
  "timestamp": "2025-11-16T10:00:00.000000"
}
```

#### 5.2 状态查询

```bash
curl http://127.0.0.1:8001/status
```

**预期响应**：
```json
{
  "scheduler_status": "running",
  "paused": false,
  "next_inspection": "2025-11-16T10:05:00",
  "last_inspection": null,
  "current_execution": null,
  "total_executions": 0
}
```

#### 5.3 调度信息

```bash
curl http://127.0.0.1:8001/schedule
```

**预期响应**：
```json
{
  "jobs": [
    {
      "id": "probe_inspection",
      "name": "Periodic Inspection",
      "next_run_time": "2025-11-16T10:05:00",
      "trigger": "cron[minute='*/5']"
    }
  ],
  "scheduler_running": true,
  "paused": false
}
```

#### 5.4 手动触发巡检

```bash
curl -X POST http://127.0.0.1:8001/execute \
  -H "Content-Type: application/json" \
  -d '{"force": false}'
```

**预期响应**：
```json
{
  "status": "started",
  "execution_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

#### 5.5 查询报告列表

```bash
curl http://127.0.0.1:8001/reports
```

**预期响应**：
```json
{
  "reports": [
    {
      "execution_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "status": "completed",
      "started_at": "2025-11-16T10:00:00",
      "completed_at": "2025-11-16T10:02:30",
      "duration_seconds": 150.5,
      "has_report": true
    }
  ]
}
```

#### 5.6 查询特定报告

```bash
curl http://127.0.0.1:8001/reports/f47ac10b-58cc-4372-a567-0e02b2c3d479
```

#### 5.7 暂停调度

```bash
curl -X POST http://127.0.0.1:8001/pause
```

**预期响应**：
```json
{
  "status": "paused",
  "message": "Scheduled inspections paused"
}
```

#### 5.8 恢复调度

```bash
curl -X POST http://127.0.0.1:8001/resume
```

**预期响应**：
```json
{
  "status": "resumed",
  "message": "Scheduled inspections resumed"
}
```

### 6. WebSocket 测试

使用 websocat 或浏览器测试：

```bash
# 安装 websocat
cargo install websocat

# 连接 WebSocket
websocat ws://127.0.0.1:8001/ws
```

**预期行为**：
1. 连接建立成功
2. 收到实时状态更新
3. 当巡检执行时，收到事件：
   - `inspection_started`
   - `inspection_progress`
   - `inspection_completed` 或 `inspection_failed`

**示例消息**：
```json
{
  "type": "inspection_started",
  "execution_id": "abc123",
  "message": "System inspection started",
  "timestamp": "2025-11-16T10:00:00.000000"
}
```

### 7. 日志验证

检查日志文件 `logs/probe.log`：

```bash
tail -f logs/probe.log
```

**应包含**：
- ✅ 服务启动日志
- ✅ 调度器初始化日志
- ✅ 定时任务触发日志
- ✅ Claude 执行日志
- ✅ 报告生成日志

### 8. 进程管理测试

#### 8.1 优雅关闭

按 `Ctrl+C`，观察：

```
INFO:     Shutting down
INFO:     Stopping ProbeSchedulerService...
INFO:     ProbeSchedulerService stopped
INFO:     Finished server process [12345]
```

#### 8.2 信号处理

```bash
# 发送 SIGTERM
kill -TERM <pid>
```

**预期**：服务优雅关闭

### 9. 错误处理验证

#### 9.1 配置文件缺失

```bash
cortex-probe --config nonexistent.yaml
```

**预期**：
- ❌ 错误消息提示配置文件不存在
- ❌ 进程退出码非 0

#### 9.2 端口已占用

启动两个实例：

```bash
cortex-probe --port 8001
cortex-probe --port 8001  # 第二个
```

**预期**：
- ❌ 第二个实例启动失败
- ❌ 错误消息提示端口已占用

#### 9.3 工作区不存在

配置中设置不存在的 workspace：

**预期**：
- ❌ 服务启动失败
- ❌ 错误消息提示工作区路径无效

### 10. 性能验证

#### 10.1 响应时间

```bash
# 使用 apache bench
ab -n 100 -c 10 http://127.0.0.1:8001/health
```

**预期**：
- ✅ 平均响应时间 < 50ms
- ✅ 无失败请求

#### 10.2 并发连接

```bash
# 多个 WebSocket 连接
for i in {1..10}; do
  websocat ws://127.0.0.1:8001/ws &
done
```

**预期**：
- ✅ 所有连接建立成功
- ✅ 广播消息发送到所有客户端

### 11. 集成验证清单

- [ ] 配置加载正常
- [ ] FastAPI 服务启动成功
- [ ] APScheduler 调度器运行正常
- [ ] 定时任务按 cron 表达式触发
- [ ] Claude 执行器能够异步执行
- [ ] WebSocket 连接和广播正常
- [ ] 所有 API 端点返回正确响应
- [ ] 日志记录完整
- [ ] 优雅关闭机制工作
- [ ] 错误处理机制完善

## 常见问题排查

### Q1: 服务无法启动

**检查**：
1. Python 版本 >= 3.11
2. 所有依赖已安装：`pip install -e .`
3. 配置文件路径正确
4. 端口未被占用：`lsof -i :8001`

### Q2: 调度器未触发任务

**检查**：
1. cron 表达式格式正确
2. 调度器状态：`GET /schedule`
3. 调度器未被暂停：`paused: false`

### Q3: Claude 执行失败

**检查**：
1. `claude` 命令可用：`which claude`
2. API key 已设置
3. workspace 目录存在
4. 超时时间设置合理

### Q4: WebSocket 无法连接

**检查**：
1. 服务正在运行
2. 使用正确的 WebSocket URL：`ws://host:port/ws`
3. 防火墙/代理设置

## 验证成功标准

所有以下条件满足，即视为验证成功：

✅ 单元测试全部通过
✅ 服务能够正常启动和关闭
✅ 所有 API 端点响应正确
✅ WebSocket 连接和广播正常
✅ 定时任务能够触发
✅ Claude 执行器能够异步执行（模拟）
✅ 日志记录完整清晰
✅ 错误处理机制完善
✅ 性能指标符合预期

## 下一步

验证成功后，可以：

1. 部署到测试环境
2. 配置 systemd 服务
3. 进行压力测试
4. 编写更多集成测试
5. 准备生产环境部署
