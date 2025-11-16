"""
Monitor FastAPI 应用主文件
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from cortex.config.settings import get_settings
from cortex.monitor import dependencies
from cortex.monitor.db_manager import DatabaseManager
from cortex.monitor.routers import alerts, cluster, decisions, health, intents, reports


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

    # 启动时的其他初始化
    yield

    # 关闭时清理
    logger.info("Shutting down Cortex Monitor...")
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
