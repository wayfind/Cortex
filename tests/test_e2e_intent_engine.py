"""
端到端测试：Intent-Engine 完整集成

测试场景：
1. 完整意图生命周期（创建 → 查询 → 更新状态）
2. Intent 查询和过滤（按 agent_id, type, level）
3. Intent 统计聚合（按类型、层级、Agent 统计）
4. 便捷方法测试（record_decision, record_blocker, record_milestone）

覆盖模块：
- cortex/common/intent_recorder.py（核心逻辑）
- Intent 生命周期管理
- 数据持久化和查询

注：API 层的测试在 test_intents_api.py 中
"""

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func

from cortex.common.intent_recorder import IntentRecorder, IntentRecord, IntentBase
from cortex.config.settings import IntentEngineConfig


class TestIntentEngineE2E:
    """Intent-Engine 端到端集成测试（直接测试 IntentRecorder）"""

    @pytest.fixture
    async def intent_recorder(self):
        """创建 IntentRecorder 实例，每个测试独立的数据库"""
        from unittest.mock import MagicMock

        # 创建内存数据库引擎
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
        )

        # 创建表结构
        async with engine.begin() as conn:
            await conn.run_sync(IntentBase.metadata.create_all)

        # 创建 mock Settings 对象
        mock_settings = MagicMock()
        mock_settings.intent_engine = IntentEngineConfig(
            enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )

        recorder = IntentRecorder(mock_settings)
        recorder.engine = engine

        # 创建 session factory
        recorder.async_session_factory = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        await recorder.initialize()

        yield recorder

        await recorder.close()
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_完整意图生命周期(self, intent_recorder: IntentRecorder):
        """
        测试场景：完整意图生命周期

        步骤：
        1. 创建 L2 decision intent
        2. 查询并验证 intent 详情
        3. 更新 intent 状态（模拟决策批准）
        4. 验证状态转换
        """
        # 1. 创建 intent
        intent_id = await intent_recorder.record_intent(
            agent_id="test-agent-001",
            intent_type="decision",
            level="L2",
            category="memory_restart",
            description="Restart high-memory service after approval",
            metadata={"service": "worker-01", "memory_mb": 8500},
            status="pending",
        )

        assert intent_id is not None
        assert intent_id > 0

        # 2. 查询 intent 详情（通过数据库）
        async with intent_recorder.async_session_factory() as session:
            stmt = select(IntentRecord).where(IntentRecord.id == intent_id)
            result = await session.execute(stmt)
            record = result.scalar_one()

            # 验证字段完整性
            assert record.id == intent_id
            assert record.agent_id == "test-agent-001"
            assert record.intent_type == "decision"
            assert record.level == "L2"
            assert record.category == "memory_restart"
            assert record.status == "pending"
            assert record.description == "Restart high-memory service after approval"

            metadata = json.loads(record.metadata_json)
            assert metadata["service"] == "worker-01"
            assert metadata["memory_mb"] == 8500

        # 3. 更新 intent 状态
        success = await intent_recorder.update_intent_status(intent_id, "approved")
        assert success is True

        # 4. 验证状态更新
        async with intent_recorder.async_session_factory() as session:
            stmt = select(IntentRecord).where(IntentRecord.id == intent_id)
            result = await session.execute(stmt)
            record = result.scalar_one()
            assert record.status == "approved"

        # 5. 继续状态转换: approved → executed → completed
        await intent_recorder.update_intent_status(intent_id, "executed")
        await intent_recorder.update_intent_status(intent_id, "completed")

        # 验证最终状态
        async with intent_recorder.async_session_factory() as session:
            stmt = select(IntentRecord).where(IntentRecord.id == intent_id)
            result = await session.execute(stmt)
            record = result.scalar_one()
            assert record.status == "completed"

    @pytest.mark.asyncio
    async def test_intent查询和过滤(self, intent_recorder: IntentRecorder):
        """
        测试场景：Intent 查询和过滤

        创建多个不同类型的 intent，测试查询方法
        """
        # 创建多个 intent
        intents_data = [
            # Agent 001
            {
                "agent_id": "agent-001",
                "intent_type": "decision",
                "level": "L1",
                "category": "disk_cleanup",
                "description": "L1 disk cleanup",
            },
            {
                "agent_id": "agent-001",
                "intent_type": "blocker",
                "level": "L3",
                "category": "database_error",
                "description": "Database connection failed",
            },
            # Agent 002
            {
                "agent_id": "agent-002",
                "intent_type": "decision",
                "level": "L2",
                "category": "memory_restart",
                "description": "L2 memory restart",
            },
            {
                "agent_id": "agent-002",
                "intent_type": "milestone",
                "level": None,
                "category": "probe_completed",
                "description": "Probe inspection completed",
            },
        ]

        for data in intents_data:
            await intent_recorder.record_intent(**data)

        # 测试 1: 按 agent_id 查询
        intents = await intent_recorder.query_recent_intents(agent_id="agent-001", limit=50)
        assert len(intents) == 2
        for intent in intents:
            assert intent.agent_id == "agent-001"

        # 测试 2: 按 intent_type 查询
        intents = await intent_recorder.query_recent_intents(intent_type="decision", limit=50)
        assert len(intents) == 2
        for intent in intents:
            assert intent.intent_type == "decision"

        # 测试 3: 限制返回数量
        intents = await intent_recorder.query_recent_intents(limit=2)
        assert len(intents) == 2

        # 测试 4: 查询所有
        intents = await intent_recorder.query_recent_intents(limit=50)
        assert len(intents) == 4

    @pytest.mark.asyncio
    async def test_intent统计聚合(self, intent_recorder: IntentRecorder):
        """
        测试场景：Intent 统计聚合

        创建多样化的 intent，验证统计功能
        """
        # 创建多种类型的 intent
        test_data = [
            # Decision 类型
            ("agent-A", "decision", "L1", "disk_cleanup"),
            ("agent-A", "decision", "L2", "memory_restart"),
            ("agent-B", "decision", "L2", "service_restart"),
            # Blocker 类型
            ("agent-A", "blocker", "L3", "database_error"),
            ("agent-B", "blocker", "L3", "network_timeout"),
            # Milestone 类型
            ("agent-A", "milestone", None, "probe_completed"),
            ("agent-B", "milestone", None, "cluster_synced"),
            ("agent-C", "milestone", None, "health_check_passed"),
        ]

        for agent_id, intent_type, level, category in test_data:
            await intent_recorder.record_intent(
                agent_id=agent_id,
                intent_type=intent_type,
                level=level,
                category=category,
                description=f"{intent_type} - {category}",
            )

        # 统计验证 - 直接查询数据库
        async with intent_recorder.async_session_factory() as session:
            # 总数统计
            stmt = select(func.count()).select_from(IntentRecord)
            total = (await session.execute(stmt)).scalar()
            assert total == 8

            # 按类型统计
            stmt = (
                select(IntentRecord.intent_type, func.count())
                .group_by(IntentRecord.intent_type)
            )
            result = await session.execute(stmt)
            type_counts = {row[0]: row[1] for row in result}

            assert type_counts["decision"] == 3
            assert type_counts["blocker"] == 2
            assert type_counts["milestone"] == 3

            # 按层级统计（排除 None）
            stmt = (
                select(IntentRecord.level, func.count())
                .where(IntentRecord.level.isnot(None))
                .group_by(IntentRecord.level)
            )
            result = await session.execute(stmt)
            level_counts = {row[0]: row[1] for row in result}

            assert level_counts["L1"] == 1
            assert level_counts["L2"] == 2
            assert level_counts["L3"] == 2

            # 按 Agent 统计
            stmt = (
                select(IntentRecord.agent_id, func.count())
                .group_by(IntentRecord.agent_id)
            )
            result = await session.execute(stmt)
            agent_counts = {row[0]: row[1] for row in result}

            assert agent_counts["agent-A"] == 4
            assert agent_counts["agent-B"] == 3
            assert agent_counts["agent-C"] == 1

    @pytest.mark.asyncio
    async def test_便捷方法(self, intent_recorder: IntentRecorder):
        """
        测试便捷方法：record_decision, record_blocker, record_milestone
        """
        # 测试 record_decision
        decision_id = await intent_recorder.record_decision(
            agent_id="agent-test",
            level="L2",
            category="service_restart",
            description="Restart service for maintenance",
            status="pending",
        )

        assert decision_id > 0

        # 验证
        async with intent_recorder.async_session_factory() as session:
            stmt = select(IntentRecord).where(IntentRecord.id == decision_id)
            record = (await session.execute(stmt)).scalar_one()
            assert record.intent_type == "decision"
            assert record.level == "L2"
            assert record.category == "service_restart"

        # 测试 record_blocker
        blocker_id = await intent_recorder.record_blocker(
            agent_id="agent-test",
            category="network_failure",
            description="Cannot reach upstream server",
        )

        assert blocker_id > 0

        # 验证
        async with intent_recorder.async_session_factory() as session:
            stmt = select(IntentRecord).where(IntentRecord.id == blocker_id)
            record = (await session.execute(stmt)).scalar_one()
            assert record.intent_type == "blocker"
            assert record.category == "network_failure"

        # 测试 record_milestone
        milestone_id = await intent_recorder.record_milestone(
            agent_id="agent-test",
            category="deployment_completed",
            description="Successfully deployed v2.0",
        )

        assert milestone_id > 0

        # 验证
        async with intent_recorder.async_session_factory() as session:
            stmt = select(IntentRecord).where(IntentRecord.id == milestone_id)
            record = (await session.execute(stmt)).scalar_one()
            assert record.intent_type == "milestone"
            assert record.category == "deployment_completed"

    @pytest.mark.asyncio
    async def test_intent_engine_禁用(self):
        """测试 Intent-Engine 禁用时的行为"""
        from unittest.mock import MagicMock

        mock_settings = MagicMock()
        mock_settings.intent_engine = IntentEngineConfig(
            enabled=False,
            database_url="sqlite+aiosqlite:///:memory:",
        )

        recorder = IntentRecorder(mock_settings)

        # 验证 enabled 状态
        assert recorder.enabled is False

        # 调用方法应返回默认值/空结果
        intent_id = await recorder.record_intent(
            agent_id="test",
            intent_type="decision",
            level="L1",
            category="test",
            description="test",
        )

        assert intent_id is None  # 禁用时应返回 None

        # query 方法应返回空列表
        intents = await recorder.query_recent_intents()
        assert intents == []
