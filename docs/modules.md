# Cortex 模块设计文档

## 1. Probe 模块详细设计

### 1.1 模块职责

Probe 模块是 Cortex Agent 的执行单元，负责：

1. **定时系统巡检**：按照 Cron 配置定期执行系统健康检查
2. **问题分级识别**：将发现的问题分为 L1/L2/L3 三个级别
3. **L1 问题自主修复**：对简单问题进行自动修复
4. **上报数据生成**：生成结构化的上报数据发送给 Monitor

### 1.2 核心组件架构

```python
# 核心类设计

class ProbeScheduler:
    """Probe 调度器：负责定时触发巡检"""

    def __init__(self, config: ProbeConfig):
        self.scheduler = AsyncIOScheduler()
        self.config = config

    async def start(self):
        """启动调度器"""
        self.scheduler.add_job(
            self.run_inspection,
            CronTrigger.from_crontab(self.config.schedule),
            id='probe_inspection'
        )
        self.scheduler.start()

    async def run_inspection(self):
        """执行巡检任务"""
        executor = ProbeExecutor(self.config)
        await executor.execute()


class ProbeExecutor:
    """Probe 执行器：实际执行巡检逻辑"""

    def __init__(self, config: ProbeConfig):
        self.config = config
        self.llm_client = AnthropicClient(api_key=config.claude_api_key)
        self.issue_classifier = IssueClassifier()
        self.auto_fixer = L1AutoFixer()
        self.reporter = ProbeReporter(config.monitor_url)

    async def execute(self):
        """执行完整的巡检流程"""
        # 1. 收集系统信息
        system_info = await self.collect_system_info()

        # 2. LLM 巡检分析
        issues = await self.llm_inspect(system_info)

        # 3. 问题分级
        classified_issues = self.issue_classifier.classify(issues)

        # 4. L1 问题自动修复
        fixed_issues = await self.auto_fix_l1(classified_issues['L1'])

        # 5. 生成并上报数据
        report = self.generate_report(
            system_info,
            classified_issues,
            fixed_issues
        )
        await self.reporter.send(report)

        # 6. 等待 L2 决策响应（如有）
        if classified_issues['L2']:
            await self.handle_l2_decisions(classified_issues['L2'])

    async def collect_system_info(self) -> SystemInfo:
        """收集系统信息"""
        return SystemInfo(
            cpu=psutil.cpu_percent(interval=1),
            memory=psutil.virtual_memory().percent,
            disk=psutil.disk_usage('/').percent,
            load_average=os.getloadavg(),
            processes=self.get_critical_processes(),
            disk_io=psutil.disk_io_counters(),
            network=psutil.net_io_counters()
        )

    async def llm_inspect(self, system_info: SystemInfo) -> List[Issue]:
        """使用 LLM 进行系统巡检"""
        prompt = self.build_inspection_prompt(system_info)

        response = await self.llm_client.messages.create(
            model="claude-sonnet-4",
            max_tokens=2000,
            tools=self.get_inspection_tools(),
            messages=[{"role": "user", "content": prompt}]
        )

        # 解析 LLM 返回的问题列表
        return self.parse_llm_response(response)


class IssueClassifier:
    """问题分级器"""

    def classify(self, issues: List[Issue]) -> Dict[str, List[Issue]]:
        """将问题分为 L1/L2/L3 三个级别"""
        classified = {'L1': [], 'L2': [], 'L3': []}

        for issue in issues:
            level = self.determine_level(issue)
            classified[level].append(issue)

        return classified

    def determine_level(self, issue: Issue) -> str:
        """判断问题级别"""
        # L1: 可安全自动修复的简单问题
        if issue.type in ['disk_space_low', 'temp_files_cleanup',
                          'log_rotation_needed']:
            return 'L1'

        # L3: 严重或未知问题
        if issue.severity == 'critical' or issue.type == 'unknown':
            return 'L3'

        # L2: 需要决策批准的问题
        return 'L2'


class L1AutoFixer:
    """L1 问题自动修复器"""

    async def fix(self, issue: Issue) -> FixResult:
        """执行自动修复"""
        fixer_method = self.get_fixer(issue.type)

        if not fixer_method:
            return FixResult(success=False, reason="No fixer available")

        try:
            # 执行修复
            result = await fixer_method(issue)

            # 验证修复结果
            verified = await self.verify_fix(issue, result)

            # 记录意图
            await self.record_intent(issue, result, verified)

            return FixResult(
                success=verified,
                action=result.action,
                details=result.details
            )
        except Exception as e:
            logger.error(f"Fix failed: {e}")
            return FixResult(success=False, reason=str(e))

    async def fix_disk_space_low(self, issue: Issue) -> ActionResult:
        """修复磁盘空间不足问题"""
        # 清理 /tmp
        subprocess.run(['find', '/tmp', '-type', 'f', '-atime', '+7', '-delete'])

        # 清理旧日志
        subprocess.run(['find', '/var/log', '-name', '*.gz', '-mtime', '+30', '-delete'])

        freed_space = self.calculate_freed_space()

        return ActionResult(
            action="cleaned_disk_space",
            details=f"Freed {freed_space}GB of disk space"
        )


class ProbeReporter:
    """Probe 上报器"""

    def __init__(self, monitor_url: str):
        self.monitor_url = monitor_url
        self.http_client = httpx.AsyncClient()

    async def send(self, report: ProbeReport) -> Response:
        """发送上报数据到 Monitor"""
        try:
            response = await self.http_client.post(
                f"{self.monitor_url}/api/v1/reports",
                json=report.dict(),
                timeout=30.0
            )
            response.raise_for_status()
            return response
        except httpx.HTTPError as e:
            logger.error(f"Failed to send report: {e}")
            # 保存到本地队列，稍后重试
            await self.save_to_retry_queue(report)
```

### 1.3 LLM 集成详细设计

#### 1.3.1 巡检 Prompt 模板

```python
INSPECTION_PROMPT_TEMPLATE = """
你是一个系统运维专家，正在对服务器进行健康检查。

当前系统信息：
- CPU 使用率: {cpu_percent}%
- 内存使用率: {memory_percent}%
- 磁盘使用率: {disk_percent}%
- 系统负载: {load_average}
- 关键进程状态:
{process_status}

近期日志摘要:
{log_summary}

请执行以下任务：
1. 分析系统当前状态，识别潜在问题
2. 对每个问题进行严重级别评估
3. 对于简单问题，提供自动修复建议

使用提供的工具函数进行更深入的检查。

输出格式：JSON 列表，每个问题包含：
- type: 问题类型
- description: 问题描述
- severity: 严重程度 (low/medium/high/critical)
- proposed_fix: 修复建议（如适用）
- risk_assessment: 风险评估
"""
```

#### 1.3.2 Tools 定义

```python
INSPECTION_TOOLS = [
    {
        "name": "check_service_status",
        "description": "检查指定服务的运行状态",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "服务名称，如 nginx, postgresql"
                }
            },
            "required": ["service_name"]
        }
    },
    {
        "name": "check_port_listening",
        "description": "检查指定端口是否在监听",
        "input_schema": {
            "type": "object",
            "properties": {
                "port": {
                    "type": "integer",
                    "description": "端口号"
                }
            },
            "required": ["port"]
        }
    },
    {
        "name": "scan_error_logs",
        "description": "扫描最近的错误日志",
        "input_schema": {
            "type": "object",
            "properties": {
                "log_file": {
                    "type": "string",
                    "description": "日志文件路径"
                },
                "hours": {
                    "type": "integer",
                    "description": "扫描最近几小时的日志",
                    "default": 24
                }
            },
            "required": ["log_file"]
        }
    }
]
```

### 1.4 巡检项目清单

| 巡检类别 | 具体项目 | 检查方法 | 阈值 |
|---------|---------|---------|------|
| **系统健康** | | | |
| | CPU 使用率 | psutil.cpu_percent() | > 80% 告警 |
| | 内存使用率 | psutil.virtual_memory() | > 85% 告警 |
| | 磁盘使用率 | psutil.disk_usage('/') | > 90% 告警 |
| | 系统负载 | os.getloadavg() | > CPU 核心数 × 2 |
| | inode 使用率 | df -i | > 90% 告警 |
| **服务状态** | | | |
| | 关键进程存活 | psutil.process_iter() | 进程不存在告警 |
| | 服务端口监听 | socket 连接测试 | 端口不可达告警 |
| | Docker 容器状态 | docker ps | 容器异常退出告警 |
| | Systemd 服务状态 | systemctl status | 服务失败告警 |
| **日志异常** | | | |
| | 错误日志扫描 | grep ERROR/FATAL | 新增错误告警 |
| | 异常模式识别 | LLM 分析日志 | 识别异常模式 |
| | 日志文件大小 | os.path.getsize() | 超大文件告警 |
| **网络连通性** | | | |
| | 外部 API 可达 | HTTP 请求测试 | 超时或错误告警 |
| | 内部服务通信 | 服务间 ping | 不可达告警 |
| | DNS 解析 | socket.gethostbyname() | 解析失败告警 |
| **安全检查** | | | |
| | 失败登录尝试 | /var/log/auth.log | 异常登录告警 |
| | 文件完整性 | 关键文件 checksum | 文件被篡改告警 |
| | 证书有效期 | SSL 证书检查 | 30 天内过期告警 |

### 1.5 数据上报格式

```python
# 数据模型定义

class ProbeReport(BaseModel):
    """Probe 上报数据模型"""

    agent_id: str
    timestamp: datetime
    status: Literal['healthy', 'warning', 'critical']

    # 系统指标
    metrics: SystemMetrics

    # 发现的问题
    issues: List[IssueReport]

    # 已执行的修复操作
    actions_taken: List[ActionReport]

    # 元数据
    metadata: Dict[str, Any]


class SystemMetrics(BaseModel):
    """系统指标"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    load_average: Tuple[float, float, float]
    uptime_seconds: int

    # 可选的详细指标
    disk_io: Optional[Dict[str, int]] = None
    network_io: Optional[Dict[str, int]] = None
    process_count: Optional[int] = None


class IssueReport(BaseModel):
    """问题报告"""
    level: Literal['L1', 'L2', 'L3']
    type: str
    description: str
    severity: Literal['low', 'medium', 'high', 'critical']

    # L2 决策请求字段
    proposed_fix: Optional[str] = None
    risk_assessment: Optional[str] = None

    # 附加信息
    details: Dict[str, Any] = {}
    timestamp: datetime


class ActionReport(BaseModel):
    """修复操作报告"""
    level: Literal['L1', 'L2']
    action: str
    result: Literal['success', 'failed', 'partial']
    details: str
    timestamp: datetime

    # Intent-Engine 意图 ID（如已记录）
    intent_id: Optional[int] = None
```

**JSON 示例**：

```json
{
  "agent_id": "node-prod-001",
  "timestamp": "2025-11-16T10:00:00Z",
  "status": "warning",
  "metrics": {
    "cpu_percent": 45.2,
    "memory_percent": 62.1,
    "disk_percent": 92.5,
    "load_average": [1.2, 1.5, 1.8],
    "uptime_seconds": 864000,
    "process_count": 156
  },
  "issues": [
    {
      "level": "L1",
      "type": "disk_space_low",
      "description": "磁盘使用率 92.5%，接近告警阈值",
      "severity": "medium",
      "details": {
        "partition": "/",
        "used_gb": 185,
        "total_gb": 200
      },
      "timestamp": "2025-11-16T10:00:05Z"
    },
    {
      "level": "L2",
      "type": "service_down",
      "description": "nginx 服务意外停止",
      "severity": "high",
      "proposed_fix": "systemctl restart nginx",
      "risk_assessment": "中风险：重启 nginx 会短暂中断 Web 服务（约 2-3 秒），但可恢复服务。建议批准。",
      "details": {
        "service": "nginx",
        "last_active": "2025-11-16T09:45:00Z",
        "exit_code": 1
      },
      "timestamp": "2025-11-16T10:00:10Z"
    }
  ],
  "actions_taken": [
    {
      "level": "L1",
      "action": "cleaned_disk_space",
      "result": "success",
      "details": "Cleaned /tmp and old logs, freed 5.2GB",
      "timestamp": "2025-11-16T10:00:15Z",
      "intent_id": 1234
    }
  ],
  "metadata": {
    "probe_version": "1.0.0",
    "execution_time_seconds": 18.5,
    "llm_model": "claude-sonnet-4"
  }
}
```

---

## 2. Monitor 模块详细设计

### 2.1 Web 服务架构

```python
# FastAPI 应用结构

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Cortex Monitor", version="1.0.0")

# 挂载静态文件（Web UI）
app.mount("/static", StaticFiles(directory="frontend/dist"), name="static")

# API 路由
from .routers import reports, decisions, cluster, alerts, websocket

app.include_router(reports.router, prefix="/api/v1", tags=["reports"])
app.include_router(decisions.router, prefix="/api/v1", tags=["decisions"])
app.include_router(cluster.router, prefix="/api/v1", tags=["cluster"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(websocket.router, tags=["websocket"])

# 启动时初始化
@app.on_event("startup")
async def startup_event():
    # 初始化数据库
    await init_database()

    # 启动后台任务
    asyncio.create_task(alert_aggregator_task())
    asyncio.create_task(node_health_monitor_task())

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}
```

### 2.2 核心 API 端点设计

#### 2.2.1 数据接收接口

```python
# routers/reports.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.post("/reports")
async def receive_report(
    report: ProbeReport,
    db: AsyncSession = Depends(get_db)
):
    """
    接收 Probe 上报数据

    处理流程：
    1. 验证数据格式
    2. 更新节点心跳时间
    3. 存储报告到数据库
    4. 处理 L2 决策请求（如有）
    5. 触发 L3 告警（如有）
    6. 通过 WebSocket 推送更新到 UI
    """
    try:
        # 1. 验证 agent_id
        agent = await get_agent(db, report.agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # 2. 更新心跳
        await update_agent_heartbeat(db, report.agent_id, report.timestamp)

        # 3. 存储报告
        report_id = await store_report(db, report)

        # 4. 处理 L2 决策请求
        l2_issues = [i for i in report.issues if i.level == 'L2']
        decision_responses = []
        for issue in l2_issues:
            decision = await process_l2_decision(db, report.agent_id, issue)
            decision_responses.append(decision)

        # 5. 处理 L3 告警
        l3_issues = [i for i in report.issues if i.level == 'L3']
        if l3_issues:
            await trigger_l3_alerts(db, report.agent_id, l3_issues)

        # 6. WebSocket 推送
        await websocket_manager.broadcast({
            "type": "report_received",
            "agent_id": report.agent_id,
            "status": report.status,
            "timestamp": report.timestamp
        })

        return {
            "success": True,
            "report_id": report_id,
            "l2_decisions": decision_responses,
            "timestamp": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Error processing report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heartbeat")
async def receive_heartbeat(
    heartbeat: HeartbeatData,
    db: AsyncSession = Depends(get_db)
):
    """
    接收心跳数据（轻量级上报）
    """
    await update_agent_heartbeat(db, heartbeat.agent_id, heartbeat.timestamp)

    return {"success": True, "timestamp": datetime.utcnow()}
```

#### 2.2.2 决策管理接口

```python
# routers/decisions.py

@router.post("/decisions/request")
async def request_decision(
    decision_request: DecisionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    L2 决策请求

    处理流程：
    1. 验证请求
    2. 启动 LLM 风险分析
    3. 生成决策（批准/拒绝）
    4. 存储决策记录
    5. 记录 Intent
    6. 返回决策结果
    """
    # 1. 验证请求
    agent = await get_agent(db, decision_request.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # 2. 启动决策引擎
    decision_engine = DecisionEngine(db)
    decision = await decision_engine.process_l2_request(decision_request)

    # 3. 返回决策
    return {
        "success": True,
        "decision_id": decision.id,
        "status": decision.status,  # approved | rejected
        "reason": decision.reason,
        "timestamp": datetime.utcnow()
    }


@router.get("/decisions/{decision_id}")
async def get_decision(
    decision_id: int,
    db: AsyncSession = Depends(get_db)
):
    """查询决策结果"""
    decision = await db.get(Decision, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    return decision
```

#### 2.2.3 集群管理接口

```python
# routers/cluster.py

@router.get("/cluster/nodes")
async def get_cluster_nodes(
    db: AsyncSession = Depends(get_db)
):
    """
    获取集群节点列表

    返回所有下级节点的状态信息
    """
    # 获取所有配置了当前节点为 upstream 的 Agent
    nodes = await get_downstream_agents(db)

    return {
        "total": len(nodes),
        "online": len([n for n in nodes if n.is_online]),
        "nodes": [
            {
                "agent_id": n.id,
                "name": n.name,
                "status": n.status,
                "health": n.health_status,
                "last_heartbeat": n.last_heartbeat,
                "issues_count": await get_agent_issues_count(db, n.id)
            }
            for n in nodes
        ]
    }


@router.get("/cluster/nodes/{agent_id}")
async def get_node_details(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取单个节点详情（下钻分析）
    """
    agent = await get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # 获取最近的报告
    recent_reports = await get_agent_reports(db, agent_id, limit=20)

    # 获取历史事件
    events = await get_agent_events(db, agent_id, limit=50)

    # 获取决策历史
    decisions = await get_agent_decisions(db, agent_id, limit=20)

    # 获取告警
    alerts = await get_agent_alerts(db, agent_id, status='active')

    return {
        "agent": agent,
        "recent_reports": recent_reports,
        "events": events,
        "decisions": decisions,
        "alerts": alerts,
        "metrics": await calculate_agent_metrics(db, agent_id)
    }


@router.get("/cluster/topology")
async def get_cluster_topology(
    db: AsyncSession = Depends(get_db)
):
    """
    获取集群拓扑结构

    返回树形结构展示层级关系
    """
    topology = await build_cluster_topology(db)
    return topology
```

#### 2.2.4 告警接口

```python
# routers/alerts.py

@router.get("/alerts")
async def get_alerts(
    status: Optional[str] = None,
    level: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    获取告警列表（支持筛选）
    """
    query = select(Alert)

    if status:
        query = query.where(Alert.status == status)
    if level:
        query = query.where(Alert.level == level)
    if agent_id:
        query = query.where(Alert.agent_id == agent_id)

    query = query.order_by(Alert.created_at.desc()).limit(limit)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return {"total": len(alerts), "alerts": alerts}


@router.post("/alerts/{alert_id}/ack")
async def acknowledge_alert(
    alert_id: int,
    ack_data: AlertAcknowledgment,
    db: AsyncSession = Depends(get_db)
):
    """确认告警"""
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = 'acknowledged'
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = ack_data.user
    alert.notes = ack_data.notes

    await db.commit()

    return {"success": True, "alert": alert}
```

### 2.3 决策引擎设计

```python
# services/decision_engine.py

class DecisionEngine:
    """L2 决策引擎"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_client = AnthropicClient()
        self.intent_recorder = IntentRecorder()

    async def process_l2_request(
        self,
        request: DecisionRequest
    ) -> Decision:
        """
        处理 L2 决策请求

        流程：
        1. 收集上下文信息
        2. 启动 LLM 分析
        3. 生成决策
        4. 记录到数据库
        5. 记录 Intent
        """
        # 1. 收集上下文
        agent = await self.get_agent(request.agent_id)
        context = await self.build_decision_context(agent, request.issue)

        # 2. LLM 分析
        llm_analysis = await self.llm_analyze_risk(context, request)

        # 3. 生成决策
        decision_status = self.make_decision(llm_analysis)

        # 4. 创建决策记录
        decision = Decision(
            agent_id=request.agent_id,
            issue_type=request.issue.type,
            issue_description=request.issue.description,
            proposed_action=request.issue.proposed_fix,
            llm_analysis=llm_analysis,
            status=decision_status,
            reason=self.extract_reason(llm_analysis),
            created_at=datetime.utcnow()
        )

        self.db.add(decision)
        await self.db.commit()

        # 5. 记录 Intent
        await self.intent_recorder.add_event(
            event_type='decision',
            data=f"L2 Decision for {agent.name}: {decision_status} - {request.issue.type}",
            metadata={
                'agent_id': request.agent_id,
                'decision_id': decision.id,
                'issue_type': request.issue.type
            }
        )

        return decision

    async def llm_analyze_risk(
        self,
        context: DecisionContext,
        request: DecisionRequest
    ) -> str:
        """使用 LLM 进行风险分析"""

        prompt = f"""
你是一个运维决策专家，需要评估一个自动修复操作的风险。

节点信息：
- 节点 ID: {context.agent.id}
- 节点名称: {context.agent.name}
- 当前状态: {context.agent.status}

问题描述：
- 类型: {request.issue.type}
- 描述: {request.issue.description}
- 严重程度: {request.issue.severity}

提议的修复操作：
{request.issue.proposed_fix}

节点最近状态：
{context.recent_history}

请分析：
1. 执行该操作的风险级别（低/中/高）
2. 可能的影响范围
3. 是否建议批准该操作
4. 理由说明

以结构化的格式输出你的分析。
"""

        response = await self.llm_client.messages.create(
            model="claude-sonnet-4",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text

    def make_decision(self, llm_analysis: str) -> str:
        """
        根据 LLM 分析生成最终决策

        简单策略：检查分析中是否包含"建议批准"等关键词
        复杂策略：可以再次调用 LLM 或使用规则引擎
        """
        if "建议批准" in llm_analysis or "approve" in llm_analysis.lower():
            return "approved"
        elif "拒绝" in llm_analysis or "reject" in llm_analysis.lower():
            return "rejected"
        else:
            # 默认保守策略：不确定时拒绝
            return "rejected"
```

### 2.4 告警聚合器设计

```python
# services/alert_aggregator.py

class AlertAggregator:
    """L3 告警聚合器"""

    def __init__(self, db: AsyncSession, telegram_bot: TelegramBot):
        self.db = db
        self.telegram_bot = telegram_bot
        self.dedup_window = timedelta(minutes=5)

    async def process_l3_alerts(
        self,
        agent_id: str,
        issues: List[IssueReport]
    ):
        """
        处理 L3 告警

        流程：
        1. 去重（避免重复告警）
        2. 关联分析（识别相关问题）
        3. 生成统一告警
        4. 发送 Telegram 通知
        5. 记录到数据库
        """
        # 1. 去重
        deduplicated = await self.deduplicate_alerts(agent_id, issues)

        if not deduplicated:
            return  # 所有告警都是重复的，跳过

        # 2. 关联分析
        correlated = await self.correlate_alerts(deduplicated)

        # 3. 生成告警记录
        alerts = []
        for issue in deduplicated:
            alert = Alert(
                agent_id=agent_id,
                level='L3',
                type=issue.type,
                description=issue.description,
                severity=issue.severity,
                status='new',
                details=issue.details,
                created_at=datetime.utcnow()
            )
            self.db.add(alert)
            alerts.append(alert)

        await self.db.commit()

        # 4. 生成通知消息
        message = self.build_alert_message(agent_id, deduplicated, correlated)

        # 5. 发送 Telegram
        await self.telegram_bot.send_alert(message)

        # 6. 记录 Intent
        await self.record_alert_intent(agent_id, alerts)

    async def deduplicate_alerts(
        self,
        agent_id: str,
        issues: List[IssueReport]
    ) -> List[IssueReport]:
        """去重：检查最近是否有相同告警"""
        deduplicated = []

        for issue in issues:
            # 查询最近时间窗口内的相同告警
            recent_alert = await self.db.execute(
                select(Alert).where(
                    Alert.agent_id == agent_id,
                    Alert.type == issue.type,
                    Alert.created_at > datetime.utcnow() - self.dedup_window
                )
            )

            if not recent_alert.scalar():
                deduplicated.append(issue)

        return deduplicated

    async def correlate_alerts(
        self,
        issues: List[IssueReport]
    ) -> Dict[str, List[IssueReport]]:
        """
        关联分析：识别可能相关的问题

        例如：
        - 磁盘故障 → 数据库崩溃
        - 网络中断 → 多个服务不可达
        """
        # 简单的基于规则的关联
        correlation_rules = {
            'disk_failure': ['database_crash', 'service_crash'],
            'network_down': ['api_unreachable', 'service_unreachable'],
            'memory_exhausted': ['process_killed', 'oom_error']
        }

        correlated = {}

        for issue in issues:
            related = correlation_rules.get(issue.type, [])
            related_issues = [i for i in issues if i.type in related]

            if related_issues:
                correlated[issue.type] = related_issues

        return correlated

    def build_alert_message(
        self,
        agent_id: str,
        issues: List[IssueReport],
        correlated: Dict[str, List[IssueReport]]
    ) -> str:
        """构建 Telegram 告警消息"""
        agent = self.get_agent_sync(agent_id)

        message = f"""
🚨 **Cortex 集群告警**

**节点**: {agent.name} (`{agent_id}`)
**时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

**严重问题 ({len(issues)} 个)**:
"""

        for i, issue in enumerate(issues, 1):
            emoji = self.get_severity_emoji(issue.severity)
            message += f"\n{i}. {emoji} **{issue.type}**\n"
            message += f"   {issue.description}\n"

        if correlated:
            message += "\n**可能的关联问题**:\n"
            for root, related in correlated.items():
                message += f"- {root} 可能导致: {', '.join([r.type for r in related])}\n"

        message += f"\n[查看详情](https://monitor.example.com/nodes/{agent_id})"

        return message
```

---

## 3. Intent-Engine 模块设计

### 3.1 集成方式

Cortex 使用 MCP (Model Context Protocol) 提供的 Intent-Engine 工具进行意图跟踪。

**配置示例**：

```json
// mcp_config.json
{
  "mcpServers": {
    "intent-engine": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-intent-engine"],
      "env": {
        "DATABASE_URL": "sqlite:///./cortex_intents.db"
      }
    }
  }
}
```

### 3.2 意图分类与使用场景

| 意图类型 | 使用场景 | 示例 |
|---------|---------|------|
| **decision** | L1 自主修复、L2 决策批准/拒绝 | "Auto-fixed disk space: cleaned 5GB" |
| **blocker** | L3 严重问题、无法自动修复的错误 | "Database crashed on node-001" |
| **milestone** | 重要操作完成、阶段性成果 | "Cluster successfully scaled to 10 nodes" |
| **note** | 常规巡检日志、一般性记录 | "Daily inspection completed, all healthy" |

### 3.3 Probe 中的意图记录

```python
# probe/intent_recorder.py

class IntentRecorder:
    """Intent 记录器"""

    def __init__(self):
        # 假设 MCP 工具已通过环境配置可用
        from mcp_client import MCPClient
        self.mcp_client = MCPClient()

    async def record_l1_fix(
        self,
        issue: Issue,
        result: FixResult
    ):
        """记录 L1 修复意图"""
        await self.mcp_client.task_add(
            name=f"L1 Fix: {issue.type}",
            spec=f"""
## 问题
{issue.description}

## 修复操作
{result.action}

## 结果
{result.details}

## 状态
{'成功' if result.success else '失败'}
"""
        )

        # 立即标记为完成
        await self.mcp_client.task_done()

    async def record_probe_execution(
        self,
        report: ProbeReport
    ):
        """记录 Probe 执行"""
        event_type = 'note' if report.status == 'healthy' else 'milestone'

        await self.mcp_client.event_add(
            event_type=event_type,
            data=f"""
# Probe 巡检报告

**节点**: {report.agent_id}
**状态**: {report.status}
**时间**: {report.timestamp}

## 指标
- CPU: {report.metrics.cpu_percent}%
- 内存: {report.metrics.memory_percent}%
- 磁盘: {report.metrics.disk_percent}%

## 问题
- L1: {len([i for i in report.issues if i.level == 'L1'])} 个
- L2: {len([i for i in report.issues if i.level == 'L2'])} 个
- L3: {len([i for i in report.issues if i.level == 'L3'])} 个

## 修复操作
{len(report.actions_taken)} 个操作已执行
"""
        )
```

### 3.4 Monitor 中的意图记录

```python
# monitor/intent_recorder.py

class MonitorIntentRecorder:
    """Monitor 意图记录器"""

    async def record_l2_decision(
        self,
        decision: Decision
    ):
        """记录 L2 决策意图"""
        await mcp_client.task_add(
            name=f"L2 Decision: {decision.agent_id} - {decision.issue_type}",
            spec=f"""
## 节点
{decision.agent_id}

## 问题
**类型**: {decision.issue_type}
**描述**: {decision.issue_description}

## 提议操作
{decision.proposed_action}

## LLM 分析
{decision.llm_analysis}

## 决策结果
**状态**: {decision.status}
**理由**: {decision.reason}
"""
        )

        await mcp_client.task_done()

    async def record_l3_alert(
        self,
        agent_id: str,
        alerts: List[Alert]
    ):
        """记录 L3 告警意图"""
        await mcp_client.event_add(
            event_type='blocker',
            data=f"""
# L3 严重告警

**节点**: {agent_id}
**告警数量**: {len(alerts)}

## 详情
{self._format_alerts(alerts)}

**已通知人类管理员**
"""
        )
```

---

## 4. Web UI 模块设计

### 4.1 页面结构与路由

```typescript
// React Router 配置

import { BrowserRouter, Routes, Route } from 'react-router-dom';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 全局仪表盘（首页） */}
        <Route path="/" element={<ClusterDashboard />} />

        {/* 节点详情页 */}
        <Route path="/nodes/:agentId" element={<NodeDetails />} />

        {/* 告警中心 */}
        <Route path="/alerts" element={<AlertCenter />} />

        {/* 自身状态 */}
        <Route path="/self" element={<SelfStatus />} />

        {/* 决策历史 */}
        <Route path="/decisions" element={<DecisionHistory />} />

        {/* 设置 */}
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </BrowserRouter>
  );
}
```

### 4.2 全局仪表盘设计

```typescript
// components/ClusterDashboard.tsx

import { useQuery } from '@tanstack/react-query';
import { useWebSocket } from '@/hooks/useWebSocket';

interface ClusterDashboardProps {}

export function ClusterDashboard() {
  // 获取集群节点数据
  const { data: clusterData } = useQuery({
    queryKey: ['cluster', 'nodes'],
    queryFn: () => api.get('/api/v1/cluster/nodes'),
    refetchInterval: 30000, // 30 秒轮询
  });

  // WebSocket 实时更新
  useWebSocket({
    onMessage: (event) => {
      if (event.type === 'report_received') {
        // 更新节点状态
        queryClient.invalidateQueries(['cluster', 'nodes']);
      }
    }
  });

  return (
    <div className="dashboard-container">
      {/* 顶部统计卡片 */}
      <div className="stats-cards">
        <StatCard
          title="总节点数"
          value={clusterData?.total || 0}
          icon={<ServerIcon />}
        />
        <StatCard
          title="在线节点"
          value={clusterData?.online || 0}
          status="success"
        />
        <StatCard
          title="告警节点"
          value={clusterData?.warning || 0}
          status="warning"
        />
        <StatCard
          title="故障节点"
          value={clusterData?.critical || 0}
          status="error"
        />
      </div>

      {/* 节点状态矩阵 */}
      <NodeStatusGrid nodes={clusterData?.nodes || []} />

      {/* 实时告警流 */}
      <RealTimeAlertFeed />

      {/* 集群关键指标 */}
      <ClusterMetricsCharts />
    </div>
  );
}

// 节点状态网格
function NodeStatusGrid({ nodes }: { nodes: Node[] }) {
  return (
    <div className="node-grid">
      {nodes.map(node => (
        <NodeCard
          key={node.agent_id}
          node={node}
          onClick={() => navigate(`/nodes/${node.agent_id}`)}
        />
      ))}
    </div>
  );
}
```

### 4.3 节点详情页设计

```typescript
// components/NodeDetails.tsx

export function NodeDetails() {
  const { agentId } = useParams();

  const { data: nodeData } = useQuery({
    queryKey: ['node', agentId],
    queryFn: () => api.get(`/api/v1/cluster/nodes/${agentId}`),
  });

  return (
    <div className="node-details">
      {/* 节点头部信息 */}
      <NodeHeader node={nodeData?.agent} />

      {/* 健康指标图表（时间序列） */}
      <div className="metrics-section">
        <h2>健康指标</h2>
        <MetricsCharts
          data={nodeData?.recent_reports}
          metrics={['cpu_percent', 'memory_percent', 'disk_percent']}
        />
      </div>

      {/* 历史事件时间线 */}
      <div className="events-section">
        <h2>历史事件</h2>
        <EventTimeline events={nodeData?.events} />
      </div>

      {/* 操作日志 */}
      <div className="actions-section">
        <h2>操作日志</h2>
        <ActionLogTable actions={nodeData?.actions} />
      </div>

      {/* 决策历史 */}
      <div className="decisions-section">
        <h2>决策历史</h2>
        <DecisionHistoryTable decisions={nodeData?.decisions} />
      </div>

      {/* 活跃告警 */}
      <div className="alerts-section">
        <h2>活跃告警</h2>
        <AlertList alerts={nodeData?.alerts} />
      </div>
    </div>
  );
}
```

### 4.4 实时通信设计

```typescript
// hooks/useWebSocket.ts

import { useEffect } from 'react';
import io from 'socket.io-client';

export function useWebSocket({ onMessage }: { onMessage: (event: any) => void }) {
  useEffect(() => {
    const socket = io('ws://localhost:8000');

    socket.on('connect', () => {
      console.log('WebSocket connected');
    });

    socket.on('message', (data) => {
      onMessage(data);
    });

    socket.on('disconnect', () => {
      console.log('WebSocket disconnected');
    });

    return () => {
      socket.disconnect();
    };
  }, [onMessage]);
}
```

```python
# monitor/websocket.py (后端)

from fastapi import WebSocket, WebSocketDisconnect
from typing import List

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """广播消息到所有连接的客户端"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                # 连接已断开，移除
                self.disconnect(connection)

manager = WebSocketManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 保持连接
            data = await websocket.receive_text()
            # 可选：处理客户端发送的消息
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

---

## 5. API 接口设计

### 5.1 认证与授权

#### 5.1.1 API Key 认证（Agent 通信）

```python
# middleware/auth.py

from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    """验证 API Key"""
    # 从数据库查询 API Key
    agent = await get_agent_by_api_key(api_key)

    if not agent:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key"
        )

    return agent


# 在路由中使用
@router.post("/reports")
async def receive_report(
    report: ProbeReport,
    agent: Agent = Depends(verify_api_key),  # 自动认证
    db: AsyncSession = Depends(get_db)
):
    # agent 已通过认证
    ...
```

#### 5.1.2 JWT Token 认证（Web UI）

```python
# auth/jwt.py

from datetime import datetime, timedelta
from jose import JWTError, jwt

SECRET_KEY = "your-secret-key"  # 应从环境变量读取
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict):
    """创建 JWT Token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """从 JWT Token 获取当前用户"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await get_user(username)
    if user is None:
        raise credentials_exception

    return user


# 登录端点
@router.post("/auth/login")
async def login(credentials: LoginCredentials):
    user = await authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}
```

### 5.2 统一响应格式

```python
# models/response.py

from pydantic import BaseModel
from typing import Generic, TypeVar, Optional
from datetime import datetime

T = TypeVar('T')

class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    success: bool
    data: Optional[T] = None
    message: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class APIError(BaseModel):
    """错误响应"""
    success: bool = False
    error: ErrorDetail
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None


# 使用示例
@router.get("/cluster/nodes")
async def get_cluster_nodes() -> APIResponse[ClusterNodesData]:
    nodes = await fetch_nodes()
    return APIResponse(
        success=True,
        data=nodes,
        message="Cluster nodes retrieved successfully"
    )
```

---

## 6. 数据库设计

### 6.1 核心表结构

```sql
-- agents 表：节点信息
CREATE TABLE agents (
    id TEXT PRIMARY KEY,  -- agent_id
    name TEXT NOT NULL,
    upstream_monitor_url TEXT,  -- NULL 表示独立模式或顶级节点
    api_key TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'offline',  -- online/offline
    health_status TEXT DEFAULT 'unknown',  -- healthy/warning/critical
    last_heartbeat TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON  -- 额外的节点元数据
);

-- reports 表：上报数据
CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    status TEXT NOT NULL,  -- healthy/warning/critical
    metrics JSON NOT NULL,  -- SystemMetrics
    issues JSON,  -- List[IssueReport]
    actions_taken JSON,  -- List[ActionReport]
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- decisions 表：决策记录
CREATE TABLE decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    issue_description TEXT NOT NULL,
    proposed_action TEXT NOT NULL,
    llm_analysis TEXT,
    status TEXT NOT NULL,  -- approved/rejected
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP,  -- 执行时间（如已执行）
    execution_result TEXT,  -- 执行结果
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- alerts 表：告警记录
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    level TEXT NOT NULL,  -- L1/L2/L3
    type TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,  -- low/medium/high/critical
    status TEXT NOT NULL DEFAULT 'new',  -- new/acknowledged/resolved
    details JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP,
    acknowledged_by TEXT,
    resolved_at TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- users 表：Web UI 用户（可选）
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',  -- admin/operator/viewer
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);
```

### 6.2 索引设计

```sql
-- 优化查询性能的索引

-- reports 表索引
CREATE INDEX idx_reports_agent_timestamp ON reports(agent_id, timestamp DESC);
CREATE INDEX idx_reports_status ON reports(status);
CREATE INDEX idx_reports_created_at ON reports(created_at DESC);

-- decisions 表索引
CREATE INDEX idx_decisions_agent_created ON decisions(agent_id, created_at DESC);
CREATE INDEX idx_decisions_status ON decisions(status);

-- alerts 表索引
CREATE INDEX idx_alerts_status_created ON alerts(status, created_at DESC);
CREATE INDEX idx_alerts_agent_status ON alerts(agent_id, status);
CREATE INDEX idx_alerts_level ON alerts(level);

-- agents 表索引
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_heartbeat ON agents(last_heartbeat DESC);
```

### 6.3 数据保留策略

```python
# services/data_retention.py

class DataRetentionService:
    """数据保留策略服务"""

    async def cleanup_old_data(self):
        """定期清理旧数据"""
        await self.archive_old_reports()
        await self.cleanup_resolved_alerts()

    async def archive_old_reports(self):
        """归档 30 天前的报告"""
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        # 1. 导出到归档文件
        old_reports = await self.db.execute(
            select(Report).where(Report.created_at < cutoff_date)
        )

        await self.export_to_archive(old_reports.scalars().all())

        # 2. 删除旧记录
        await self.db.execute(
            delete(Report).where(Report.created_at < cutoff_date)
        )
        await self.db.commit()

    async def cleanup_resolved_alerts(self):
        """清理 90 天前已解决的告警"""
        cutoff_date = datetime.utcnow() - timedelta(days=90)

        await self.db.execute(
            delete(Alert).where(
                Alert.status == 'resolved',
                Alert.resolved_at < cutoff_date
            )
        )
        await self.db.commit()
```

---

本文档详细定义了 Cortex 各模块的设计，包括 Probe、Monitor、Intent-Engine、Web UI、API 和数据库。这些设计遵循 spec01.md 的核心架构思想，为实际开发提供了清晰的技术蓝图。
