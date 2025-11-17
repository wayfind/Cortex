"""
Pytest 配置和 Fixtures
"""

import asyncio
from typing import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from cortex.config.settings import (
    AgentConfig,
    AuthConfig,
    ClaudeConfig,
    IntentEngineConfig,
    LoggingConfig,
    MonitorConfig,
    ProbeConfig,
    Settings,
    TelegramConfig,
)
from cortex.monitor.auth import create_access_token, hash_password
from cortex.monitor.database import Base, User


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings():
    """创建测试配置"""
    return Settings(
        agent=AgentConfig(id="test-agent", name="Test Agent", mode="standalone"),
        probe=ProbeConfig(),
        monitor=MonitorConfig(
            database_url="sqlite+aiosqlite:///:memory:",
            registration_token="test-token",
        ),
        claude=ClaudeConfig(api_key="sk-test-key"),
        telegram=TelegramConfig(),
        intent_engine=IntentEngineConfig(),
        logging=LoggingConfig(),
        auth=AuthConfig(),
    )


@pytest.fixture
async def test_app(test_settings):
    """创建测试应用（包含数据库初始化）"""
    from cortex.monitor.app import app
    from cortex.monitor.db_manager import DatabaseManager
    from cortex.monitor.dependencies import set_db_manager
    from cortex.config import settings as settings_module

    # 覆盖全局设置为测试配置
    settings_module._settings = test_settings

    # 使用测试配置初始化 DatabaseManager
    db_manager = DatabaseManager(test_settings)

    # 创建数据库表
    await db_manager.init_database()

    set_db_manager(db_manager)

    yield app

    # 清理
    await db_manager.close()
    app.dependency_overrides.clear()
    settings_module._settings = None


@pytest.fixture
async def test_db_session(test_app) -> AsyncGenerator[AsyncSession, None]:
    """创建测试数据库会话（使用与 test_app 相同的数据库）"""
    from cortex.monitor.dependencies import get_db_manager

    db_manager = get_db_manager()
    async for session in db_manager.get_session():
        yield session


@pytest.fixture
async def admin_user(test_db_session) -> User:
    """创建测试 admin 用户"""
    user = User(
        username="admin",
        email="admin@example.com",
        password_hash=hash_password("admin123"),
        role="admin",
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user) -> str:
    """创建 admin JWT token"""
    return create_access_token(
        {"sub": admin_user.username, "user_id": admin_user.id, "role": admin_user.role}
    )
