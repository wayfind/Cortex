"""
Monitor 依赖注入
"""

from cortex.monitor.db_manager import DatabaseManager

# 全局数据库管理器
_db_manager: DatabaseManager | None = None


def set_db_manager(manager: DatabaseManager) -> None:
    """设置全局数据库管理器"""
    global _db_manager
    _db_manager = manager


def get_db_manager() -> DatabaseManager:
    """获取数据库管理器（用于依赖注入）"""
    if _db_manager is None:
        raise RuntimeError("DatabaseManager not initialized")
    return _db_manager
