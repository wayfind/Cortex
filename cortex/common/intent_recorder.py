"""
Intent 记录器 - 用于记录 Cortex 操作意图和事件
"""

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from loguru import logger
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from cortex.config.settings import Settings


class IntentBase(DeclarativeBase):
    """Intent 数据库基类"""

    pass


class IntentRecord(IntentBase):
    """意图记录表"""

    __tablename__ = "intent_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    intent_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # decision, blocker, milestone, note
    level: Mapped[Optional[str]] = mapped_column(String(10))  # L1, L2, L3
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # 操作类别
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON 格式的元数据
    status: Mapped[Optional[str]] = mapped_column(String(50))  # approved, rejected, completed, etc.


class IntentRecorder:
    """
    意图记录器

    用于记录 Cortex Probe 和 Monitor 的操作意图，实现全生命周期可追溯。

    使用示例：
        recorder = IntentRecorder(settings)
        await recorder.initialize()

        # 记录 L1 自动修复决策
        await recorder.record_decision(
            agent_id="agent-001",
            level="L1",
            category="disk_cleanup",
            description="Cleaned /tmp directory, freed 2GB",
            status="completed"
        )

        # 记录 L3 严重问题
        await recorder.record_blocker(
            agent_id="agent-001",
            category="database_connection",
            description="Unable to connect to primary database"
        )
    """

    def __init__(self, settings: Settings) -> None:
        """
        初始化意图记录器

        Args:
            settings: 全局配置
        """
        self.settings = settings
        self.enabled = settings.intent_engine.enabled
        self.engine = None
        self.async_session_factory = None

        if self.enabled:
            # 创建异步引擎
            db_url = settings.intent_engine.database_url
            # 转换为异步 URL（如果是 sqlite）
            if db_url.startswith("sqlite:///"):
                db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")

            self.engine = create_async_engine(db_url, echo=False)
            self.async_session_factory = sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )

    async def initialize(self) -> None:
        """初始化数据库表"""
        if not self.enabled:
            logger.info("Intent-Engine disabled, skipping initialization")
            return

        async with self.engine.begin() as conn:
            await conn.run_sync(IntentBase.metadata.create_all)
        logger.info("Intent-Engine initialized successfully")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self.engine:
            await self.engine.dispose()

    async def record_intent(
        self,
        agent_id: str,
        intent_type: Literal["decision", "blocker", "milestone", "note"],
        category: str,
        description: str,
        level: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
    ) -> Optional[int]:
        """
        记录意图（通用方法）

        Args:
            agent_id: Agent ID
            intent_type: 意图类型 (decision/blocker/milestone/note)
            category: 操作类别
            description: 描述
            level: 问题级别 (L1/L2/L3)
            metadata: 额外的元数据
            status: 状态

        Returns:
            记录 ID，如果 Intent-Engine 禁用则返回 None
        """
        if not self.enabled:
            logger.debug(f"Intent recording disabled, skipping: {category}")
            return None

        try:
            import json

            async with self.async_session_factory() as session:
                record = IntentRecord(
                    agent_id=agent_id,
                    intent_type=intent_type,
                    level=level,
                    category=category,
                    description=description,
                    metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
                    status=status,
                )

                session.add(record)
                await session.commit()
                await session.refresh(record)

                logger.info(
                    f"Intent recorded: [{intent_type}] {category} for {agent_id} (ID: {record.id})"
                )
                return record.id

        except Exception as e:
            logger.error(f"Failed to record intent: {e}")
            return None

    async def record_decision(
        self,
        agent_id: str,
        level: str,
        category: str,
        description: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        记录决策（L1 自动修复、L2 LLM 决策等）

        Args:
            agent_id: Agent ID
            level: 决策级别 (L1/L2)
            category: 问题类别
            description: 决策描述
            status: 决策状态 (approved/rejected/completed)
            metadata: 额外信息（如修复结果、风险评估等）

        Returns:
            记录 ID
        """
        return await self.record_intent(
            agent_id=agent_id,
            intent_type="decision",
            level=level,
            category=category,
            description=description,
            status=status,
            metadata=metadata,
        )

    async def record_blocker(
        self,
        agent_id: str,
        category: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        记录严重问题/阻塞项（L3 级问题）

        Args:
            agent_id: Agent ID
            category: 问题类别
            description: 问题描述
            metadata: 额外信息

        Returns:
            记录 ID
        """
        return await self.record_intent(
            agent_id=agent_id,
            intent_type="blocker",
            level="L3",
            category=category,
            description=description,
            metadata=metadata,
        )

    async def record_milestone(
        self,
        agent_id: str,
        category: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        记录重要里程碑事件

        Args:
            agent_id: Agent ID
            category: 事件类别
            description: 事件描述
            metadata: 额外信息

        Returns:
            记录 ID
        """
        return await self.record_intent(
            agent_id=agent_id,
            intent_type="milestone",
            category=category,
            description=description,
            metadata=metadata,
        )

    async def record_note(
        self,
        agent_id: str,
        category: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        记录常规日志/笔记

        Args:
            agent_id: Agent ID
            category: 日志类别
            description: 日志内容
            metadata: 额外信息

        Returns:
            记录 ID
        """
        return await self.record_intent(
            agent_id=agent_id,
            intent_type="note",
            category=category,
            description=description,
            metadata=metadata,
        )

    async def query_recent_intents(
        self,
        agent_id: Optional[str] = None,
        intent_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[IntentRecord]:
        """
        查询最近的意图记录

        Args:
            agent_id: 筛选特定 Agent（可选）
            intent_type: 筛选意图类型（可选）
            limit: 返回数量限制

        Returns:
            意图记录列表
        """
        if not self.enabled:
            return []

        try:
            from sqlalchemy import select

            async with self.async_session_factory() as session:
                query = select(IntentRecord).order_by(IntentRecord.timestamp.desc()).limit(limit)

                if agent_id:
                    query = query.where(IntentRecord.agent_id == agent_id)
                if intent_type:
                    query = query.where(IntentRecord.intent_type == intent_type)

                result = await session.execute(query)
                return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Failed to query intents: {e}")
            return []
