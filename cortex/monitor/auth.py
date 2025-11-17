"""
认证与授权工具模块
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.config.settings import get_settings
from cortex.monitor.database import APIKey, User
from cortex.monitor.dependencies import get_db

# ==================== 配置 ====================

# 获取配置实例
_settings = get_settings()

# JWT 配置
SECRET_KEY = _settings.auth.secret_key
ALGORITHM = _settings.auth.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = _settings.auth.access_token_expire_minutes

# 密码哈希
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


# ==================== Pydantic 模型 ====================


class Token(BaseModel):
    """Token 响应模型"""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token 数据模型"""

    username: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None


class UserInToken(BaseModel):
    """Token 中的用户信息"""

    id: int
    username: str
    email: str
    role: str


# ==================== 密码哈希工具 ====================


def hash_password(password: str) -> str:
    """哈希密码"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


# ==================== API Key 工具 ====================


def generate_api_key() -> str:
    """生成随机 API Key"""
    return f"sk_{secrets.token_urlsafe(48)}"


async def validate_api_key(
    api_key_value: Optional[str],
    session: AsyncSession,
) -> Optional[APIKey]:
    """验证 API Key"""
    if not api_key_value:
        return None

    # 查询数据库
    stmt = select(APIKey).where(APIKey.key == api_key_value)
    result = await session.execute(stmt)
    api_key = result.scalar_one_or_none()

    if not api_key:
        return None

    # 检查是否激活
    if not api_key.is_active:
        return None

    # 检查是否过期
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        return None

    # 更新使用统计
    api_key.last_used_at = datetime.now(timezone.utc)
    api_key.usage_count += 1
    await session.commit()

    return api_key


# ==================== JWT 工具 ====================


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT Token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """解码 JWT Token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        role: str = payload.get("role")

        if username is None:
            return None

        return TokenData(username=username, user_id=user_id, role=role)
    except JWTError:
        return None


# ==================== 认证依赖 ====================


async def get_current_user_from_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """从 JWT Token 获取当前用户"""
    if not credentials:
        return None

    token = credentials.credentials
    token_data = decode_access_token(token)

    if not token_data or not token_data.username:
        return None

    # 查询用户
    stmt = select(User).where(User.username == token_data.username)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        return None

    return user


async def get_current_user_from_api_key(
    api_key_value: Optional[str] = Security(api_key_header),
    session: AsyncSession = Depends(get_db),
) -> Optional[tuple[APIKey, Optional[User]]]:
    """从 API Key 获取认证信息"""
    if not api_key_value:
        return None

    api_key = await validate_api_key(api_key_value, session)
    if not api_key:
        return None

    # 如果 API Key 关联了用户，查询用户信息
    user = None
    if api_key.owner_id:
        stmt = select(User).where(User.id == api_key.owner_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

    return (api_key, user)


async def get_current_user(
    token_user: Optional[User] = Depends(get_current_user_from_token),
    api_key_auth: Optional[tuple[APIKey, Optional[User]]] = Depends(
        get_current_user_from_api_key
    ),
) -> dict:
    """
    获取当前用户（支持 JWT Token 和 API Key 两种方式）

    返回格式：
    {
        "auth_type": "token" | "api_key",
        "user": User | None,
        "api_key": APIKey | None,
        "role": str,
        "is_authenticated": bool
    }
    """
    # 优先使用 JWT Token
    if token_user:
        return {
            "auth_type": "token",
            "user": token_user,
            "api_key": None,
            "role": token_user.role,
            "is_authenticated": True,
        }

    # 其次使用 API Key
    if api_key_auth:
        api_key, user = api_key_auth
        return {
            "auth_type": "api_key",
            "user": user,
            "api_key": api_key,
            "role": api_key.role,
            "is_authenticated": True,
        }

    # 未认证
    return {
        "auth_type": None,
        "user": None,
        "api_key": None,
        "role": "anonymous",
        "is_authenticated": False,
    }


async def require_auth(current_user: dict = Depends(get_current_user)) -> dict:
    """要求必须认证（Token 或 API Key）"""
    if not current_user["is_authenticated"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please provide a valid token or API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


# ==================== RBAC 权限控制 ====================


ROLE_HIERARCHY = {
    "admin": 3,
    "operator": 2,
    "viewer": 1,
    "anonymous": 0,
}


def check_permission(user_role: str, required_role: str) -> bool:
    """
    检查权限

    权限继承规则：
    - admin 拥有所有权限
    - operator 拥有 operator 和 viewer 权限
    - viewer 只有查看权限
    """
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    required_level = ROLE_HIERARCHY.get(required_role, 0)
    return user_level >= required_level


def require_role(required_role: str):
    """
    创建角色要求依赖

    用法：
    @app.get("/admin/endpoint", dependencies=[Depends(require_role("admin"))])
    """

    async def role_checker(current_user: dict = Depends(require_auth)):
        if not check_permission(current_user["role"], required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}, your role: {current_user['role']}",
            )
        return current_user

    return role_checker


# ==================== 便捷依赖 ====================


require_admin = require_role("admin")
require_operator = require_role("operator")
require_viewer = require_role("viewer")
