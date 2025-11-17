"""
Monitor FastAPI 应用主文件
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from cortex.config.settings import get_settings
from cortex.monitor import dependencies
from cortex.monitor.db_manager import DatabaseManager
from cortex.monitor.routers import alerts, auth, cluster, decisions, health, intents, reports
from cortex.monitor.services.heartbeat_checker import HeartbeatChecker
from cortex.monitor.websocket_manager import WebSocketManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    logger.info("Starting Cortex Monitor...")

    # 加载配置
    settings = get_settings()

    # 初始化数据库
    db_manager = DatabaseManager(settings)
    await db_manager.init_database()
    logger.success("Database initialized")

    # 设置全局数据库管理器
    dependencies.set_db_manager(db_manager)

    # 初始化 WebSocket 管理器
    ws_manager = WebSocketManager()
    dependencies.set_ws_manager(ws_manager)
    logger.success("WebSocket manager initialized")

    # 启动心跳检测器（5 分钟超时，每 60 秒检查一次）
    heartbeat_checker = HeartbeatChecker(db_manager, timeout_minutes=5, check_interval_seconds=60)
    heartbeat_checker.start()
    logger.success("Heartbeat checker started")

    # 启动时的其他初始化
    yield

    # 关闭时清理
    logger.info("Shutting down Cortex Monitor...")
    await heartbeat_checker.stop()
    logger.info("Heartbeat checker stopped")
    await db_manager.close()
    logger.info("Monitor shutdown complete")


# 创建 FastAPI 应用
app = FastAPI(
    title="Cortex Monitor",
    description="去中心化、分级自治的智能运维网络 - Monitor 模块",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, tags=["authentication"])
app.include_router(reports.router, prefix="/api/v1", tags=["reports"])
app.include_router(decisions.router, prefix="/api/v1", tags=["decisions"])
app.include_router(cluster.router, prefix="/api/v1", tags=["cluster"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(intents.router, prefix="/api/v1", tags=["intents"])


@app.get("/")
async def root() -> dict:
    """根路径"""
    return {
        "name": "Cortex Monitor",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点，用于实时推送事件到前端"""
    ws_manager = dependencies.get_ws_manager()
    await ws_manager.connect(websocket)
    try:
        # 保持连接，接收客户端消息（主要用于心跳检测）
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
