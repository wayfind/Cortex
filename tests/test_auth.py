"""
认证与授权测试

测试覆盖：
- 用户登录和认证
- JWT Token 生成和验证
- API Key 生成和验证
- 用户管理 CRUD
- API Key 管理 CRUD
- 角色权限控制 (RBAC)
- 密码哈希和验证
"""

from datetime import datetime, timedelta, UTC
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from cortex.monitor.auth import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    decode_access_token,
    generate_api_key,
    hash_password,
    verify_password,
)
from cortex.monitor.database import APIKey, User


# ==================== 密码哈希测试 ====================


class TestPasswordHashing:
    """测试密码哈希功能"""

    def test_hash_password(self):
        """测试密码哈希"""
        password = "test_password_123"
        hashed = hash_password(password)

        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self):
        """测试正确密码验证"""
        password = "test_password_123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """测试错误密码验证"""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_hash_different_for_same_password(self):
        """测试相同密码生成不同哈希（使用 salt）"""
        password = "test_password_123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # 因为 bcrypt 使用随机 salt
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


# ==================== API Key 测试 ====================


class TestAPIKeyGeneration:
    """测试 API Key 生成"""

    def test_generate_api_key(self):
        """测试生成 API Key"""
        key = generate_api_key()

        assert key.startswith("sk_")
        assert len(key) > 48  # token_urlsafe(48) + "sk_" prefix

    def test_generate_unique_keys(self):
        """测试生成唯一 API Keys"""
        key1 = generate_api_key()
        key2 = generate_api_key()

        assert key1 != key2


# ==================== JWT Token 测试 ====================


class TestJWTToken:
    """测试 JWT Token 生成和解析"""

    def test_create_access_token(self):
        """测试创建 access token"""
        data = {"sub": "testuser", "user_id": 1, "role": "admin"}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

        # 验证 token 可以被解析
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "testuser"
        assert decoded["user_id"] == 1
        assert decoded["role"] == "admin"

    def test_create_access_token_with_expiration(self):
        """测试创建带过期时间的 token"""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=15)
        token = create_access_token(data, expires_delta)

        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in decoded

        # 验证过期时间大约为 15 分钟后
        exp_time = datetime.fromtimestamp(decoded["exp"], UTC)
        now = datetime.now(UTC)
        delta = exp_time - now

        assert 14 <= delta.total_seconds() / 60 <= 16

    def test_decode_access_token_valid(self):
        """测试解析有效 token"""
        data = {"sub": "testuser", "user_id": 1}
        token = create_access_token(data)

        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded.username == "testuser"
        assert decoded.user_id == 1

    def test_decode_access_token_invalid(self):
        """测试解析无效 token"""
        invalid_token = "invalid.token.here"
        decoded = decode_access_token(invalid_token)
        assert decoded is None

    def test_decode_access_token_expired(self):
        """测试解析过期 token"""
        data = {"sub": "testuser"}
        # 创建已过期的 token（-1 秒）
        expires_delta = timedelta(seconds=-1)
        token = create_access_token(data, expires_delta)

        decoded = decode_access_token(token)
        assert decoded is None


# ==================== 用户认证 API 测试 ====================


@pytest.mark.asyncio
class TestAuthenticationAPI:
    """测试认证 API 端点"""

    async def test_login_success(self, test_db_session, test_app):
        """测试成功登录"""
        # 创建测试用户
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("password123"),
            role="admin",
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # 登录
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"username": "testuser", "password": "password123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # 验证 token 有效
        token = data["access_token"]
        decoded = decode_access_token(token)
        assert decoded.username == "testuser"

    async def test_login_wrong_password(self, test_db_session, test_app):
        """测试错误密码"""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("password123"),
            role="admin",
        )
        test_db_session.add(user)
        await test_db_session.commit()

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"username": "testuser", "password": "wrongpassword"},
            )

        assert response.status_code == 401

    async def test_login_nonexistent_user(self, test_db_session, test_app):
        """测试不存在的用户"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"username": "nonexistent", "password": "password123"},
            )

        assert response.status_code == 401

    async def test_login_inactive_user(self, test_db_session, test_app):
        """测试禁用用户"""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("password123"),
            role="admin",
            is_active=False,
        )
        test_db_session.add(user)
        await test_db_session.commit()

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"username": "testuser", "password": "password123"},
            )

        assert response.status_code == 403

    async def test_get_current_user(self, test_db_session, test_app):
        """测试获取当前用户信息"""
        # 创建用户和 token
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("password123"),
            role="admin",
        )
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        token = create_access_token({"sub": user.username, "user_id": user.id, "role": user.role})

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"

    async def test_refresh_token(self, test_db_session, test_app):
        """测试刷新 token"""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("password123"),
            role="admin",
        )
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        old_token = create_access_token({"sub": user.username, "user_id": user.id, "role": user.role})

        # 等待1秒确保新 token 的过期时间不同
        import asyncio
        await asyncio.sleep(1)

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/refresh",
                headers={"Authorization": f"Bearer {old_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"] != old_token


# ==================== 用户管理 API 测试 ====================


@pytest.mark.asyncio
class TestUserManagementAPI:
    """测试用户管理 API"""

    async def test_create_user(self, test_db_session, test_app, admin_token):
        """测试创建用户"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/users",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "username": "newuser",
                    "email": "newuser@example.com",
                    "password": "password123",
                    "role": "viewer",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert data["role"] == "viewer"

    async def test_create_user_duplicate_username(self, test_db_session, test_app, admin_token):
        """测试创建重复用户名"""
        # 创建第一个用户
        user = User(
            username="existinguser",
            email="existing@example.com",
            password_hash=hash_password("password123"),
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # 尝试创建重复用户
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/users",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "username": "existinguser",
                    "email": "different@example.com",
                    "password": "password123",
                },
            )

        assert response.status_code == 400

    async def test_list_users(self, test_db_session, test_app, admin_token):
        """测试列出用户"""
        # 创建几个测试用户
        users = [
            User(username=f"user{i}", email=f"user{i}@example.com", password_hash=hash_password("pass"))
            for i in range(3)
        ]
        for user in users:
            test_db_session.add(user)
        await test_db_session.commit()

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/users",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        # 至少包含创建的 3 个用户 + admin 用户
        assert len(data) >= 3

    async def test_get_user_detail(self, test_db_session, test_app, admin_token):
        """测试获取用户详情"""
        user = User(
            username="detailuser",
            email="detail@example.com",
            password_hash=hash_password("password123"),
        )
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/auth/users/{user.id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "detailuser"

    async def test_update_user(self, test_db_session, test_app, admin_token):
        """测试更新用户"""
        user = User(
            username="updateuser",
            email="old@example.com",
            password_hash=hash_password("oldpassword"),
            role="viewer",
        )
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/auth/users/{user.id}",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"email": "new@example.com", "role": "operator"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["role"] == "operator"

    async def test_delete_user(self, test_db_session, test_app, admin_token):
        """测试删除用户"""
        user = User(
            username="deleteuser",
            email="delete@example.com",
            password_hash=hash_password("password123"),
        )
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/auth/users/{user.id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200


# ==================== API Key 管理测试 ====================


@pytest.mark.asyncio
class TestAPIKeyManagement:
    """测试 API Key 管理"""

    async def test_create_api_key(self, test_db_session, test_app, admin_token):
        """测试创建 API Key"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/api-keys",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"name": "Test API Key", "role": "viewer", "expires_in_days": 30},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test API Key"
        assert data["role"] == "viewer"
        assert "key" in data
        assert data["key"].startswith("sk_")

    async def test_list_api_keys(self, test_db_session, test_app, admin_token):
        """测试列出 API Keys"""
        # 创建几个 API Keys
        for i in range(3):
            api_key = APIKey(
                key=generate_api_key(),
                name=f"Key {i}",
                role="viewer",
            )
            test_db_session.add(api_key)
        await test_db_session.commit()

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/api-keys",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3

        # 验证 key 被隐藏
        for item in data:
            assert "key_preview" in item
            assert item["key_preview"].endswith("...")

    async def test_delete_api_key(self, test_db_session, test_app, admin_token):
        """测试删除 API Key"""
        api_key = APIKey(key=generate_api_key(), name="Delete Me", role="viewer")
        test_db_session.add(api_key)
        await test_db_session.commit()
        await test_db_session.refresh(api_key)

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/auth/api-keys/{api_key.id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200

    async def test_toggle_api_key(self, test_db_session, test_app, admin_token):
        """测试切换 API Key 状态"""
        api_key = APIKey(key=generate_api_key(), name="Toggle Key", role="viewer", is_active=True)
        test_db_session.add(api_key)
        await test_db_session.commit()
        await test_db_session.refresh(api_key)

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/auth/api-keys/{api_key.id}/toggle",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200

        # 验证状态已切换
        await test_db_session.refresh(api_key)
        assert api_key.is_active is False


# ==================== 权限控制测试 ====================


@pytest.mark.asyncio
class TestRBACPermissions:
    """测试基于角色的权限控制"""

    async def test_viewer_cannot_create_user(self, test_db_session, test_app):
        """测试 viewer 不能创建用户"""
        # 创建 viewer 用户
        user = User(
            username="viewer",
            email="viewer@example.com",
            password_hash=hash_password("password123"),
            role="viewer",
        )
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        # 生成 viewer token
        token = create_access_token({"sub": user.username, "user_id": user.id, "role": "viewer"})

        # 尝试创建用户
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/users",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "username": "newuser",
                    "email": "new@example.com",
                    "password": "pass",
                },
            )

        assert response.status_code == 403

    async def test_operator_cannot_create_user(self, test_db_session, test_app):
        """测试 operator 不能创建用户"""
        user = User(
            username="operator",
            email="operator@example.com",
            password_hash=hash_password("password123"),
            role="operator",
        )
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        token = create_access_token({"sub": user.username, "user_id": user.id, "role": "operator"})

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/users",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "username": "newuser",
                    "email": "new@example.com",
                    "password": "pass",
                },
            )

        assert response.status_code == 403

    async def test_admin_can_create_user(self, test_db_session, test_app, admin_token):
        """测试 admin 可以创建用户"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/users",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "username": "newuser",
                    "email": "new@example.com",
                    "password": "pass",
                    "role": "viewer",
                },
            )

        assert response.status_code == 200
