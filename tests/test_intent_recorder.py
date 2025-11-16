"""
IntentRecorder 测试
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from cortex.common.intent_recorder import IntentRecord, IntentRecorder
from cortex.config.settings import Settings


@pytest.fixture
def mock_settings():
    """创建 Mock 配置"""
    settings = MagicMock()
    settings.intent_engine = MagicMock()
    settings.intent_engine.enabled = True
    settings.intent_engine.database_url = "sqlite+aiosqlite:///:memory:"
    return settings


@pytest.fixture
async def intent_recorder(mock_settings):
    """创建 IntentRecorder 实例"""
    recorder = IntentRecorder(mock_settings)
    await recorder.initialize()
    yield recorder
    await recorder.close()


@pytest.mark.asyncio
async def test_record_decision(intent_recorder):
    """测试记录决策"""
    intent_id = await intent_recorder.record_decision(
        agent_id="test-agent-001",
        level="L1",
        category="disk_cleanup",
        description="Cleaned /tmp directory, freed 2GB",
        status="completed",
        metadata={"freed_space_gb": 2.0},
    )

    assert intent_id is not None

    # 验证记录
    async with intent_recorder.async_session_factory() as session:
        result = await session.execute(select(IntentRecord).where(IntentRecord.id == intent_id))
        record = result.scalar_one()

        assert record.agent_id == "test-agent-001"
        assert record.intent_type == "decision"
        assert record.level == "L1"
        assert record.category == "disk_cleanup"
        assert record.status == "completed"
        assert "2.0" in record.metadata_json


@pytest.mark.asyncio
async def test_record_blocker(intent_recorder):
    """测试记录严重问题"""
    intent_id = await intent_recorder.record_blocker(
        agent_id="test-agent-002",
        category="database_connection",
        description="Unable to connect to primary database",
        metadata={"error_code": "CONNECTION_TIMEOUT"},
    )

    assert intent_id is not None

    # 验证记录
    async with intent_recorder.async_session_factory() as session:
        result = await session.execute(select(IntentRecord).where(IntentRecord.id == intent_id))
        record = result.scalar_one()

        assert record.agent_id == "test-agent-002"
        assert record.intent_type == "blocker"
        assert record.level == "L3"
        assert record.category == "database_connection"
        assert "CONNECTION_TIMEOUT" in record.metadata_json


@pytest.mark.asyncio
async def test_record_milestone(intent_recorder):
    """测试记录里程碑"""
    intent_id = await intent_recorder.record_milestone(
        agent_id="test-agent-003",
        category="probe_execution_completed",
        description="Probe execution completed successfully",
        metadata={"l1_fixes_count": 3},
    )

    assert intent_id is not None

    # 验证记录
    async with intent_recorder.async_session_factory() as session:
        result = await session.execute(select(IntentRecord).where(IntentRecord.id == intent_id))
        record = result.scalar_one()

        assert record.agent_id == "test-agent-003"
        assert record.intent_type == "milestone"
        assert record.category == "probe_execution_completed"


@pytest.mark.asyncio
async def test_record_note(intent_recorder):
    """测试记录常规日志"""
    intent_id = await intent_recorder.record_note(
        agent_id="test-agent-004",
        category="routine_check",
        description="System metrics collected",
        metadata={"cpu_percent": 45.2},
    )

    assert intent_id is not None

    # 验证记录
    async with intent_recorder.async_session_factory() as session:
        result = await session.execute(select(IntentRecord).where(IntentRecord.id == intent_id))
        record = result.scalar_one()

        assert record.agent_id == "test-agent-004"
        assert record.intent_type == "note"
        assert record.category == "routine_check"


@pytest.mark.asyncio
async def test_query_recent_intents(intent_recorder):
    """测试查询最近的意图记录"""
    # 创建多条记录
    await intent_recorder.record_decision(
        agent_id="agent-001",
        level="L1",
        category="test_category",
        description="Test 1",
        status="completed",
    )
    await intent_recorder.record_blocker(
        agent_id="agent-001", category="test_category", description="Test 2"
    )
    await intent_recorder.record_milestone(
        agent_id="agent-002", category="test_category", description="Test 3"
    )

    # 查询所有记录
    all_records = await intent_recorder.query_recent_intents(limit=10)
    assert len(all_records) >= 3

    # 查询特定 Agent
    agent_records = await intent_recorder.query_recent_intents(agent_id="agent-001", limit=10)
    assert len(agent_records) >= 2
    assert all(r.agent_id == "agent-001" for r in agent_records)

    # 查询特定类型
    decision_records = await intent_recorder.query_recent_intents(intent_type="decision", limit=10)
    assert len(decision_records) >= 1
    assert all(r.intent_type == "decision" for r in decision_records)


@pytest.mark.asyncio
async def test_disabled_intent_engine():
    """测试 Intent-Engine 禁用时的行为"""
    settings = MagicMock()
    settings.intent_engine = MagicMock()
    settings.intent_engine.enabled = False

    recorder = IntentRecorder(settings)
    await recorder.initialize()  # 应该跳过初始化

    # 记录应该返回 None
    intent_id = await recorder.record_decision(
        agent_id="test-agent", level="L1", category="test", description="Test", status="completed"
    )

    assert intent_id is None

    # 查询应该返回空列表
    records = await recorder.query_recent_intents()
    assert records == []

    await recorder.close()


@pytest.mark.asyncio
async def test_record_with_special_characters(intent_recorder):
    """测试包含特殊字符的记录"""
    intent_id = await intent_recorder.record_decision(
        agent_id="test-agent-005",
        level="L2",
        category="special_chars",
        description="Description with 中文 and special chars: <>\"'&",
        status="completed",
        metadata={"key": "value with 中文"},
    )

    assert intent_id is not None

    # 验证记录可以正确存储和检索
    async with intent_recorder.async_session_factory() as session:
        result = await session.execute(select(IntentRecord).where(IntentRecord.id == intent_id))
        record = result.scalar_one()

        assert "中文" in record.description
        assert "中文" in record.metadata_json
