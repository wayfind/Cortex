#!/usr/bin/env python
"""
初始化认证系统脚本

创建默认 admin 用户和 API Key
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from cortex.config.settings import get_settings
from cortex.monitor.auth import generate_api_key, hash_password
from cortex.monitor.database import APIKey, Base, User


async def init_auth_system():
    """初始化认证系统"""
    settings = get_settings()

    # 创建数据库引擎
    database_url = settings.monitor.database_url

    # 转换为异步 URL
    if database_url.startswith("sqlite:///"):
        database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")

    engine = create_async_engine(database_url, echo=False)

    # 创建表（如果不存在）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 创建 session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # 检查是否已存在 admin 用户
        stmt = select(User).where(User.username == "admin")
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print("✓ Admin user already exists")
            print(f"  Username: {existing_user.username}")
            print(f"  Email: {existing_user.email}")
            print(f"  Role: {existing_user.role}")
        else:
            # 创建 admin 用户
            admin_user = User(
                username="admin",
                email="admin@cortex.local",
                password_hash=hash_password("admin123"),  # 默认密码
                role="admin",
                is_active=True,
            )
            session.add(admin_user)
            await session.commit()
            await session.refresh(admin_user)

            print("✓ Created admin user")
            print(f"  Username: {admin_user.username}")
            print(f"  Email: {admin_user.email}")
            print(f"  Password: admin123 (请立即修改！)")
            print(f"  Role: {admin_user.role}")

        # 检查是否已存在默认 API Key
        stmt = select(APIKey).where(APIKey.name == "Default Admin API Key")
        result = await session.execute(stmt)
        existing_api_key = result.scalar_one_or_none()

        if existing_api_key:
            print("\n✓ Default API Key already exists")
            print(f"  Name: {existing_api_key.name}")
            print(f"  Key: {existing_api_key.key[:20]}... (hidden)")
            print(f"  Role: {existing_api_key.role}")
        else:
            # 创建默认 API Key
            api_key = generate_api_key()

            # 获取 admin 用户 ID
            stmt = select(User).where(User.username == "admin")
            result = await session.execute(stmt)
            admin_user = result.scalar_one()

            default_api_key = APIKey(
                key=api_key,
                name="Default Admin API Key",
                role="admin",
                owner_id=admin_user.id,
                owner_name="admin",
                is_active=True,
            )
            session.add(default_api_key)
            await session.commit()
            await session.refresh(default_api_key)

            print("\n✓ Created default API Key")
            print(f"  Name: {default_api_key.name}")
            print(f"  Key: {api_key}")
            print(f"  Role: {default_api_key.role}")
            print(f"  Owner: {default_api_key.owner_name}")
            print("\n  ⚠️  请妥善保存此 API Key，它不会再次显示！")

    await engine.dispose()
    print("\n✓ Authentication system initialized successfully!")


async def main():
    """主函数"""
    try:
        await init_auth_system()
    except Exception as e:
        print(f"\n✗ Error initializing authentication system: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
