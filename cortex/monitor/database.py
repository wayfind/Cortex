"""
Monitor 数据库模型定义
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, func, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""

    pass


class Agent(Base):
    """Agent 节点信息表"""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # agent_id
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)  # 父节点 ID（用于拓扑）
    upstream_monitor_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    api_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)

    # 状态
    status: Mapped[str] = mapped_column(
        String(20), default="offline", nullable=False, index=True  # 添加索引
    )  # online/offline
    health_status: Mapped[str] = mapped_column(
        String(20), default="unknown", nullable=True
    )  # healthy/warning/critical

    # 时间戳
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # 元数据
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # 组合索引：按状态和父节点查询
    __table_args__ = (
        Index("ix_agents_status_parent", "status", "parent_id"),
    )


class Report(Base):
    """Probe 上报数据表"""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True  # 添加索引
    )  # healthy/warning/critical

    # JSON 存储的数据
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)  # SystemMetrics
    issues: Mapped[list] = mapped_column(JSON, nullable=True)  # List[IssueReport]
    actions_taken: Mapped[list] = mapped_column(JSON, nullable=True)  # List[ActionReport]
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # 接收时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # 组合索引：按 agent 和时间范围查询（常见的分页查询）
    __table_args__ = (
        Index("ix_reports_agent_timestamp", "agent_id", "timestamp"),
        Index("ix_reports_agent_status", "agent_id", "status"),
    )


class Decision(Base):
    """L2 决策记录表"""

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # 问题信息
    issue_type: Mapped[str] = mapped_column(String(100), nullable=False)
    issue_description: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_action: Mapped[str] = mapped_column(Text, nullable=False)

    # 决策信息
    llm_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # approved/rejected
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    execution_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 组合索引：常见查询模式
    __table_args__ = (
        Index("ix_decisions_agent_created", "agent_id", "created_at"),
        Index("ix_decisions_agent_status", "agent_id", "status"),
        Index("ix_decisions_status_created", "status", "created_at"),
    )


class Alert(Base):
    """告警记录表"""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # 告警信息
    level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # L1/L2/L3
    type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True  # 添加索引
    )  # low/medium/high/critical

    # 状态
    status: Mapped[str] = mapped_column(
        String(20), default="new", nullable=False, index=True
    )  # new/acknowledged/resolved

    # 详细信息
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 备注
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 组合索引：常见查询模式（按状态、级别、时间过滤）
    __table_args__ = (
        Index("ix_alerts_agent_status_created", "agent_id", "status", "created_at"),
        Index("ix_alerts_status_level_severity", "status", "level", "severity"),
        Index("ix_alerts_agent_level", "agent_id", "level"),
    )


class User(Base):
    """用户表（用于 Web UI 认证）"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), default="viewer", nullable=False
    )  # admin/operator/viewer

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 激活状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class APIKey(Base):
    """API Key 表（用于 API 认证）"""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)  # API Key 名称/描述
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 关联的 User ID（可选）
    owner_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 所有者名称

    # 权限级别（继承 User 的 role 概念）
    role: Mapped[str] = mapped_column(
        String(20), default="viewer", nullable=False
    )  # admin/operator/viewer

    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)  # 添加索引

    # 使用统计
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # 过期时间（可选）

    # 组合索引：查询有效的 API Key
    __table_args__ = (
        Index("ix_api_keys_active_expires", "is_active", "expires_at"),
    )
