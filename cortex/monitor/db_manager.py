"""
数据库管理器
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from cortex.config.settings import Settings
from cortex.monitor.database import Base


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        database_url = settings.monitor.database_url

        # 将 sqlite:/// 转换为 sqlite+aiosqlite:///
        if database_url.startswith("sqlite:///"):
            database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")

        self.engine = create_async_engine(
            database_url,
            echo=False,  # 生产环境设为 False
            pool_pre_ping=True,
        )

        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def init_database(self) -> None:
        """初始化数据库（创建表）"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话（依赖注入）"""
        async with self.async_session_maker() as session:
            try:
                yield session
            finally:
                await session.close()

    async def close(self) -> None:
        """关闭数据库连接"""
        await self.engine.dispose()
