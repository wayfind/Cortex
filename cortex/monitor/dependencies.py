"""
Monitor 依赖注入
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from cortex.monitor.db_manager import DatabaseManager
from cortex.monitor.websocket_manager import WebSocketManager

# 全局数据库管理器
_db_manager: DatabaseManager | None = None

# 全局 WebSocket 管理器
_ws_manager: WebSocketManager | None = None


def set_db_manager(manager: DatabaseManager) -> None:
    """设置全局数据库管理器"""
    global _db_manager
    _db_manager = manager


def get_db_manager() -> DatabaseManager:
    """获取数据库管理器（用于依赖注入）"""
    if _db_manager is None:
        raise RuntimeError("DatabaseManager not initialized")
    return _db_manager


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库 Session（FastAPI 依赖注入）

    用法:
    async def my_route(session: AsyncSession = Depends(get_db)):
        ...
    """
    db_manager = get_db_manager()
    async for session in db_manager.get_session():
        yield session


def set_ws_manager(manager: WebSocketManager) -> None:
    """设置全局 WebSocket 管理器"""
    global _ws_manager
    _ws_manager = manager


def get_ws_manager() -> WebSocketManager:
    """获取 WebSocket 管理器（用于依赖注入）"""
    if _ws_manager is None:
        raise RuntimeError("WebSocketManager not initialized")
    return _ws_manager
