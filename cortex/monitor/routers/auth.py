"""
认证与授权 API 路由
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.monitor.auth import (
    Token,
    UserInToken,
    create_access_token,
    generate_api_key,
    get_current_user,
    hash_password,
    require_admin,
    require_auth,
    verify_password,
)
from cortex.monitor.database import APIKey, User
from cortex.monitor.dependencies import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


# ==================== Pydantic 模型 ====================


class UserLogin(BaseModel):
    """用户登录请求"""

    username: str
    password: str


class UserCreate(BaseModel):
    """创建用户请求"""

    username: str
    email: EmailStr
    password: str
    role: str = "viewer"  # admin/operator/viewer


class UserUpdate(BaseModel):
    """更新用户请求"""

    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """用户响应"""

    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class APIKeyCreate(BaseModel):
    """创建 API Key 请求"""

    name: str
    role: str = "viewer"
    owner_name: Optional[str] = None
    expires_in_days: Optional[int] = None  # None = 永不过期


class APIKeyResponse(BaseModel):
    """API Key 响应"""

    id: int
    key: str  # 仅在创建时返回完整 key
    name: str
    role: str
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    is_active: bool
    usage_count: int
    last_used_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class APIKeyListResponse(BaseModel):
    """API Key 列表响应（隐藏完整 key）"""

    id: int
    key_preview: str  # 只显示前缀
    name: str
    role: str
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    is_active: bool
    usage_count: int
    last_used_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None


# ==================== 用户认证 API ====================


@router.post("/login", response_model=Token)
async def login(
    user_login: UserLogin,
    session: AsyncSession = Depends(get_db),
):
    """
    用户登录

    返回 JWT Token
    """
    # 查询用户
    stmt = select(User).where(User.username == user_login.username)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    # 验证用户和密码
    if not user or not verify_password(user_login.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查用户是否激活
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # 更新最后登录时间
    user.last_login = datetime.now(timezone.utc)
    await session.commit()

    # 创建 access token
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "role": user.role,
        }
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(require_auth),
):
    """
    获取当前登录用户信息
    """
    user = current_user.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User information not available (API Key authentication)",
        )

    return user


@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: dict = Depends(require_auth),
):
    """
    刷新 Token
    """
    if current_user["auth_type"] != "token":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token refresh only available for JWT authentication",
        )

    user = current_user["user"]

    # 创建新的 access token
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "role": user.role,
        }
    )

    return {"access_token": access_token, "token_type": "bearer"}


# ==================== 用户管理 API ====================


@router.post("/users", response_model=UserResponse, dependencies=[Depends(require_admin)])
async def create_user(
    user_create: UserCreate,
    session: AsyncSession = Depends(get_db),
):
    """
    创建用户（仅 admin）
    """
    # 检查用户名是否已存在
    stmt = select(User).where(User.username == user_create.username)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # 检查邮箱是否已存在
    stmt = select(User).where(User.email == user_create.email)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )

    # 验证角色
    if user_create.role not in ["admin", "operator", "viewer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be one of: admin, operator, viewer",
        )

    # 创建用户
    new_user = User(
        username=user_create.username,
        email=user_create.email,
        password_hash=hash_password(user_create.password),
        role=user_create.role,
    )

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    return new_user


@router.get("/users", response_model=List[UserResponse], dependencies=[Depends(require_admin)])
async def list_users(
    session: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    """
    列出所有用户（仅 admin）
    """
    stmt = select(User).offset(skip).limit(limit)
    result = await session.execute(stmt)
    users = result.scalars().all()
    return users


@router.get("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(require_admin)])
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_db),
):
    """
    获取用户详情（仅 admin）
    """
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


@router.patch("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(require_admin)])
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_db),
):
    """
    更新用户（仅 admin）
    """
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # 更新字段
    if user_update.email is not None:
        # 检查邮箱是否已被其他用户使用
        stmt = select(User).where(User.email == user_update.email, User.id != user_id)
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )
        user.email = user_update.email

    if user_update.password is not None:
        user.password_hash = hash_password(user_update.password)

    if user_update.role is not None:
        if user_update.role not in ["admin", "operator", "viewer"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role",
            )
        user.role = user_update.role

    if user_update.is_active is not None:
        user.is_active = user_update.is_active

    await session.commit()
    await session.refresh(user)

    return user


@router.delete("/users/{user_id}", dependencies=[Depends(require_admin)])
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_db),
):
    """
    删除用户（仅 admin）
    """
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await session.delete(user)
    await session.commit()

    return {"message": "User deleted successfully"}


# ==================== API Key 管理 API ====================


@router.post("/api-keys", response_model=APIKeyResponse, dependencies=[Depends(require_admin)])
async def create_api_key(
    api_key_create: APIKeyCreate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """
    创建 API Key（仅 admin）
    """
    # 验证角色
    if api_key_create.role not in ["admin", "operator", "viewer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be one of: admin, operator, viewer",
        )

    # 生成 API Key
    key = generate_api_key()

    # 计算过期时间
    expires_at = None
    if api_key_create.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=api_key_create.expires_in_days)

    # 获取 owner_id
    owner_id = None
    if current_user["user"]:
        owner_id = current_user["user"].id

    # 创建 API Key
    new_api_key = APIKey(
        key=key,
        name=api_key_create.name,
        role=api_key_create.role,
        owner_id=owner_id,
        owner_name=api_key_create.owner_name,
        expires_at=expires_at,
    )

    session.add(new_api_key)
    await session.commit()
    await session.refresh(new_api_key)

    return new_api_key


@router.get("/api-keys", response_model=List[APIKeyListResponse], dependencies=[Depends(require_admin)])
async def list_api_keys(
    session: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    """
    列出所有 API Keys（仅 admin）
    """
    stmt = select(APIKey).offset(skip).limit(limit)
    result = await session.execute(stmt)
    api_keys = result.scalars().all()

    # 隐藏完整 key，只显示前缀
    return [
        APIKeyListResponse(
            id=ak.id,
            key_preview=ak.key[:15] + "..." if len(ak.key) > 15 else ak.key,
            name=ak.name,
            role=ak.role,
            owner_id=ak.owner_id,
            owner_name=ak.owner_name,
            is_active=ak.is_active,
            usage_count=ak.usage_count,
            last_used_at=ak.last_used_at,
            created_at=ak.created_at,
            expires_at=ak.expires_at,
        )
        for ak in api_keys
    ]


@router.delete("/api-keys/{api_key_id}", dependencies=[Depends(require_admin)])
async def delete_api_key(
    api_key_id: int,
    session: AsyncSession = Depends(get_db),
):
    """
    删除 API Key（仅 admin）
    """
    stmt = select(APIKey).where(APIKey.id == api_key_id)
    result = await session.execute(stmt)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found",
        )

    await session.delete(api_key)
    await session.commit()

    return {"message": "API Key deleted successfully"}


@router.patch("/api-keys/{api_key_id}/toggle", dependencies=[Depends(require_admin)])
async def toggle_api_key(
    api_key_id: int,
    session: AsyncSession = Depends(get_db),
):
    """
    切换 API Key 激活状态（仅 admin）
    """
    stmt = select(APIKey).where(APIKey.id == api_key_id)
    result = await session.execute(stmt)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found",
        )

    api_key.is_active = not api_key.is_active
    await session.commit()

    return {"message": f"API Key {'activated' if api_key.is_active else 'deactivated'} successfully"}
