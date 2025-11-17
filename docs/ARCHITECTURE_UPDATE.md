# Probe 架构更新说明

**更新日期**: 2025-11-16
**版本**: Phase 1.5
**状态**: ✅ 已完成

## 更新概述

Probe 模块已从 cron 触发的脚本架构升级为持久化 Web 服务架构，同时保留文档驱动的核心优势。

## 架构变更对比

### 旧架构（已弃用）

```
┌─────────────┐
│   cron      │
│  定时触发    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ run_probe.sh│
│  脚本执行    │
│  执行完退出   │
└─────────────┘
```

**问题**：
- ❌ 无法实时查询状态
- ❌ 无法手动触发执行
- ❌ 无法获取执行历史
- ❌ 无法实时监控进度
- ❌ 依赖外部 cron 配置

### 新架构（Phase 1.5）

```
┌────────────────────────────────────┐
│    Probe Web 服务 (FastAPI)         │
│                                    │
│  ┌──────────┐  ┌──────────┐       │
│  │ REST API │  │WebSocket │       │
│  └──────────┘  └──────────┘       │
│         │            │             │
│         └────┬───────┘             │
│              ▼                     │
│      APScheduler (内部调度)         │
│              │                     │
│              ▼                     │
│      Claude Executor               │
│      (异步执行 claude -p)           │
└──────────────┬─────────────────────┘
               │
               ▼
         文档驱动巡检
      (probe_workspace/)
```

**优势**：
- ✅ 持久化进程，常驻运行
- ✅ 完整的 REST API
- ✅ WebSocket 实时推送
- ✅ 内部调度管理
- ✅ 执行历史记录
- ✅ 手动触发能力
- ✅ 暂停/恢复控制

## 核心组件

### 1. FastAPI 应用 (`cortex/probe/app.py`)

提供完整的 Web API 接口：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/status` | GET | 查询状态和下次执行时间 |
| `/execute` | POST | 手动触发巡检 |
| `/pause` | POST | 暂停定时巡检 |
| `/resume` | POST | 恢复定时巡检 |
| `/schedule` | GET | 查询调度信息 |
| `/reports` | GET | 获取报告列表 |
| `/reports/{id}` | GET | 获取指定报告 |
| `/ws` | WebSocket | 实时状态推送 |

### 2. APScheduler 调度服务 (`cortex/probe/scheduler_service.py`)

- Cron 表达式调度
- 执行历史管理（内存，最多 100 条）
- 暂停/恢复功能
- 与 Claude Executor 和 WebSocket 的协调

### 3. Claude 执行器 (`cortex/probe/claude_executor.py`)

- 异步执行 `claude -p` 命令
- 超时处理（默认 300 秒）
- 状态跟踪（pending, running, completed, failed, timeout）
- 报告解析和存储

### 4. WebSocket 管理器 (`cortex/probe/websocket_manager.py`)

- 连接管理
- 事件广播：
  - `inspection_started` - 巡检开始
  - `inspection_progress` - 巡检进度
  - `inspection_completed` - 巡检完成
  - `inspection_failed` - 巡检失败

### 5. CLI 入口 (`cortex/probe/cli.py`)

- 启动 uvicorn 服务器
- 命令行参数：`--host`, `--port`, `--config`, `--reload`, `--log-level`
- 配置加载和验证

## 配置变更

### 新增配置字段 (`cortex/config/settings.py`)

```python
class ProbeConfig(BaseSettings):
    # Web 服务配置
    host: str = Field("0.0.0.0")
    port: int = Field(8001)

    # 调度配置
    schedule: str = Field("0 * * * *")
    timeout_seconds: int = Field(300)

    # Claude -p 配置
    workspace: Optional[str] = Field(None)

    # 报告配置
    report_retention_days: int = Field(30)
```

## 部署方式变更

### 旧方式（cron）

```bash
# /etc/crontab
0 * * * * /opt/cortex/probe/run_probe.sh
```

### 新方式（systemd）

```ini
[Unit]
Description=Cortex Probe Web Service
After=network.target

[Service]
Type=simple
ExecStart=/opt/cortex/venv/bin/cortex-probe --config /etc/cortex/config.yaml
Restart=always

[Install]
WantedBy=multi-user.target
```

**启动命令**：
```bash
# 开发模式
cortex-probe --config .env --reload

# 生产模式
sudo systemctl start cortex-probe
sudo systemctl enable cortex-probe
```

## 文档驱动工作流保持不变

Probe 仍然使用 `claude -p` 执行文档驱动的巡检：

1. 读取 `probe_workspace/CLAUDE.md` 理解角色
2. 扫描 `probe_workspace/inspections/*.md` 获取巡检要求
3. 使用 `probe_workspace/tools/*.py` 执行检查
4. 分析结果并分级（L1/L2/L3）
5. L1 问题自动修复
6. 生成报告到 `probe_workspace/output/report.json`
7. 上报到 Monitor（如果配置了 `upstream_monitor_url`）

## 迁移指南

### 从旧 Probe 迁移

1. **停止旧服务**：
   ```bash
   # 删除 cron 任务
   sudo crontab -e
   # 移除 cortex probe 相关行
   ```

2. **安装新架构**：
   ```bash
   # 安装依赖
   pip install -e .

   # 配置 systemd
   sudo cp deployment/cortex-probe.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```

3. **更新配置**：
   ```yaml
   # config.yaml
   probe:
     host: "0.0.0.0"
     port: 8001
     schedule: "0 * * * *"  # 保持原有调度频率
     workspace: "/opt/cortex/probe_workspace"
   ```

4. **启动新服务**：
   ```bash
   sudo systemctl start cortex-probe
   sudo systemctl enable cortex-probe
   ```

5. **验证**：
   ```bash
   # 健康检查
   curl http://localhost:8001/health

   # 查询状态
   curl http://localhost:8001/status

   # 手动触发测试
   curl -X POST http://localhost:8001/execute
   ```

## 测试和验证

### 单元测试

```bash
pytest tests/probe/test_probe_service.py -v
```

### 集成测试

```bash
# 启动服务
cortex-probe --config .env

# 运行验证脚本
./scripts/verify_probe.sh
```

### 验证清单

- [ ] Probe 服务可正常启动
- [ ] 健康检查端点返回正确
- [ ] 状态查询显示调度信息
- [ ] 手动触发巡检成功
- [ ] WebSocket 连接正常
- [ ] 定时任务按计划执行
- [ ] 报告生成和存储正常
- [ ] 暂停/恢复功能正常

## 已更新文档

1. ✅ `docs/probe_workflow.md` - 更新架构图和工作流程
2. ✅ `docs/roadmap.md` - 添加 Phase 1.5
3. ✅ `README.md` - 更新架构描述和使用说明
4. ✅ `deployment/DEPLOYMENT.md` - 新增部署指南
5. ✅ `docs/probe_validation.md` - 新增验证指南

## 向后兼容性

- ✅ **文档格式**：`probe_workspace/` 目录结构和文档格式完全兼容
- ✅ **巡检逻辑**：L1/L2/L3 分级机制保持不变
- ✅ **工具脚本**：所有 `tools/*.py` 无需修改
- ✅ **报告格式**：`output/report.json` 格式保持一致
- ❌ **部署方式**：需要从 cron 迁移到 systemd

## 性能优化

- **异步执行**：`claude -p` 在后台异步运行，不阻塞 Web 服务
- **内存管理**：执行历史限制为 100 条，自动清理旧记录
- **连接管理**：WebSocket 自动清理断开的连接
- **错误处理**：超时机制防止任务卡死

## 安全考虑

- **端口绑定**：默认绑定到 `0.0.0.0:8001`，生产环境建议配置防火墙
- **权限控制**：systemd 服务使用专用用户运行
- **日志管理**：完整的日志记录，支持日志轮转
- **配置保护**：敏感配置（API Key）通过环境变量加载

## 下一步计划

- [ ] 添加 API 认证（JWT Token）
- [ ] 实现报告持久化存储（数据库）
- [ ] 优化 WebSocket 性能
- [ ] 添加 Prometheus 指标导出
- [ ] 开发 Web UI 管理界面

## 参考文档

- [Probe 工作流程详解](probe_workflow.md)
- [API 验证指南](probe_validation.md)
- [部署文档](../deployment/DEPLOYMENT.md)
- [开发路线图](roadmap.md)
