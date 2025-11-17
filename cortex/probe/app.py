"""
Cortex Probe Agent - FastAPI Web Service

这是 Probe Agent 的主应用，提供：
- REST API 端点（健康检查、状态查询、手动触发）
- WebSocket 实时状态推送
- 内置 APScheduler 调度器（周期性执行 claude -p 巡检）
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cortex.config import get_settings
from cortex.probe.claude_executor import ClaudeExecutor, ExecutionStatus
from cortex.probe.scheduler_service import ProbeSchedulerService
from cortex.probe.websocket_manager import WebSocketManager

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局状态
scheduler_service: Optional[ProbeSchedulerService] = None
ws_manager: WebSocketManager = WebSocketManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global scheduler_service

    # 启动时
    logger.info("Starting Cortex Probe Agent...")
    settings = get_settings()

    # 初始化调度器服务
    scheduler_service = ProbeSchedulerService(settings, ws_manager)
    await scheduler_service.start()

    logger.info(f"Probe Agent started successfully")
    logger.info(f"Agent ID: {settings.agent.id}")
    logger.info(f"Schedule: {settings.probe.schedule}")

    yield

    # 关闭时
    logger.info("Shutting down Cortex Probe Agent...")
    if scheduler_service:
        await scheduler_service.stop()
    logger.info("Probe Agent stopped")


# 创建 FastAPI 应用
app = FastAPI(
    title="Cortex Probe Agent",
    description="Document-driven autonomous inspection agent",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================================
# API 端点
# ============================================================================

@app.get("/health")
async def health_check():
    """
    健康检查端点

    返回：
        - status: healthy/unhealthy
        - scheduler_running: 调度器是否运行中
        - timestamp: 当前时间
    """
    is_healthy = scheduler_service and scheduler_service.is_running()

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "scheduler_running": is_healthy,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/status")
async def get_status():
    """
    获取 Probe 当前状态

    返回：
        - agent_id: Agent ID
        - agent_name: Agent 名称
        - upstream_monitor_url: 上级 Monitor URL
        - scheduler_status: 调度器状态
        - last_inspection: 上次巡检时间
        - next_inspection: 下次巡检时间
        - current_execution: 当前执行状态（如果正在巡检）
    """
    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    settings = get_settings()
    status_info = scheduler_service.get_status()

    return {
        "agent_id": settings.agent.id,
        "agent_name": settings.agent.name,
        "upstream_monitor_url": settings.agent.upstream_monitor_url,
        "scheduler_status": status_info["scheduler_status"],
        "paused": status_info["paused"],
        "last_inspection": status_info["last_inspection"],
        "next_inspection": status_info["next_inspection"],
        "current_execution": status_info.get("current_execution"),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


class ExecuteRequest(BaseModel):
    """手动执行请求"""
    force: bool = False  # 是否强制执行（即使已有任务在运行）


@app.post("/execute")
async def execute_inspection(request: ExecuteRequest = ExecuteRequest()):
    """
    手动触发一次巡检

    参数：
        - force: 是否强制执行（默认 False）

    返回：
        - status: started/already_running
        - execution_id: 执行 ID
        - message: 描述信息
    """
    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    try:
        execution_id = await scheduler_service.execute_once(force=request.force)

        return {
            "status": "started",
            "execution_id": execution_id,
            "message": "Inspection started successfully",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except RuntimeError as e:
        return JSONResponse(
            status_code=409,
            content={
                "status": "already_running",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@app.get("/config")
async def get_config():
    """
    获取当前配置

    返回完整的配置信息（敏感信息已脱敏）
    """
    settings = get_settings()

    # 脱敏配置
    config_dict = settings.model_dump()
    if "claude" in config_dict and "api_key" in config_dict["claude"]:
        config_dict["claude"]["api_key"] = "***REDACTED***"

    return config_dict


@app.get("/schedule")
async def get_schedule():
    """
    获取调度任务信息

    返回：
        - jobs: 调度任务列表
        - next_run_time: 下次运行时间
    """
    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    return scheduler_service.get_schedule_info()


@app.post("/schedule/pause")
async def pause_schedule():
    """暂停定时巡检"""
    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    scheduler_service.pause_schedule()

    return {
        "status": "paused",
        "message": "Scheduled inspections paused",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/schedule/resume")
async def resume_schedule():
    """恢复定时巡检"""
    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    scheduler_service.resume_schedule()

    return {
        "status": "resumed",
        "message": "Scheduled inspections resumed",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/reports")
async def get_reports(limit: int = 20):
    """
    获取历史报告列表

    参数：
        - limit: 返回数量（默认 20）

    返回：
        - reports: 报告列表
        - total: 总数
    """
    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    reports = scheduler_service.get_recent_reports(limit)

    return {
        "reports": reports,
        "total": len(reports),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/reports/{execution_id}")
async def get_report(execution_id: str):
    """
    获取指定报告详情

    参数：
        - execution_id: 执行 ID

    返回：
        - report: 报告详情
    """
    if not scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    report = scheduler_service.get_report(execution_id)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return report


# ============================================================================
# WebSocket 端点
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 实时状态推送

    客户端连接后，会实时接收：
    - inspection_started: 巡检开始
    - inspection_progress: 巡检进度更新
    - inspection_completed: 巡检完成
    - inspection_failed: 巡检失败
    """
    await ws_manager.connect(websocket)

    try:
        # 发送欢迎消息
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to Cortex Probe Agent",
            "agent_id": get_settings().agent.id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # 保持连接，接收客户端消息（如果需要）
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received WebSocket message: {data}")
            # 可以处理客户端发送的命令

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")


# ============================================================================
# 错误处理
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


# ============================================================================
# 启动信息
# ============================================================================

@app.get("/")
async def root():
    """根路径 - 返回 API 信息"""
    return {
        "name": "Cortex Probe Agent",
        "version": "1.0.0",
        "description": "Document-driven autonomous inspection agent",
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "execute": "/execute",
            "config": "/config",
            "schedule": "/schedule",
            "reports": "/reports",
            "websocket": "/ws",
            "docs": "/docs"
        }
    }
