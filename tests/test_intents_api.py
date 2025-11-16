"""
Intents API 测试
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from cortex.monitor.app import app


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_intent_recorder():
    """Mock IntentRecorder"""
    recorder = MagicMock()
    recorder.initialize = AsyncMock()
    recorder.close = AsyncMock()
    recorder.async_session_factory = MagicMock()
    return recorder


@pytest.mark.asyncio
async def test_query_intents_list(client, mock_intent_recorder):
    """测试查询意图列表 API"""
    # Mock 查询结果
    from cortex.common.intent_recorder import IntentRecord
    from datetime import datetime

    mock_records = [
        IntentRecord(
            id=1,
            timestamp=datetime.utcnow(),
            agent_id="agent-001",
            intent_type="decision",
            level="L1",
            category="disk_cleanup",
            description="Cleaned /tmp",
            metadata_json='{"freed_space_gb": 2.0}',
            status="completed",
        ),
        IntentRecord(
            id=2,
            timestamp=datetime.utcnow(),
            agent_id="agent-002",
            intent_type="blocker",
            level="L3",
            category="database_error",
            description="Connection failed",
            metadata_json='{"error_code": "TIMEOUT"}',
            status=None,
        ),
    ]

    # Mock session 和查询
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_records
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()

    mock_intent_recorder.async_session_factory.return_value = mock_session

    # Mock 总数查询
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 2

    with patch("cortex.monitor.routers.intents.IntentRecorder", return_value=mock_intent_recorder):
        with patch("cortex.monitor.routers.intents.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.intent_engine.enabled = True
            mock_get_settings.return_value = mock_settings

            # 模拟两次 execute 调用：一次获取总数，一次获取数据
            mock_session.execute.side_effect = [
                AsyncMock(return_value=mock_count_result)(),
                AsyncMock(return_value=mock_result)(),
            ]

            response = client.get("/api/v1/intents?limit=10&offset=0")

            assert response.status_code == 200
            data = response.json()

            assert data["total"] == 2
            assert data["limit"] == 10
            assert data["offset"] == 0
            assert len(data["items"]) == 2
            assert data["items"][0]["agent_id"] == "agent-001"
            assert data["items"][0]["intent_type"] == "decision"


@pytest.mark.asyncio
async def test_query_intents_with_filters(client):
    """测试带过滤条件的查询"""
    with patch("cortex.monitor.routers.intents.IntentRecorder") as mock_recorder_class:
        with patch("cortex.monitor.routers.intents.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.intent_engine.enabled = True
            mock_get_settings.return_value = mock_settings

            mock_recorder = MagicMock()
            mock_recorder.initialize = AsyncMock()
            mock_recorder.close = AsyncMock()

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []

            mock_count_result = MagicMock()
            mock_count_result.scalar.return_value = 0

            mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

            mock_recorder.async_session_factory.return_value = mock_session
            mock_recorder_class.return_value = mock_recorder

            response = client.get(
                "/api/v1/intents?agent_id=agent-001&intent_type=decision&level=L1"
            )

            assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_intent_by_id(client):
    """测试获取单个意图详情"""
    from cortex.common.intent_recorder import IntentRecord
    from datetime import datetime

    mock_record = IntentRecord(
        id=1,
        timestamp=datetime.utcnow(),
        agent_id="agent-001",
        intent_type="decision",
        level="L1",
        category="disk_cleanup",
        description="Test description",
        metadata_json='{"test": "data"}',
        status="completed",
    )

    with patch("cortex.monitor.routers.intents.IntentRecorder") as mock_recorder_class:
        with patch("cortex.monitor.routers.intents.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.intent_engine.enabled = True
            mock_get_settings.return_value = mock_settings

            mock_recorder = MagicMock()
            mock_recorder.initialize = AsyncMock()
            mock_recorder.close = AsyncMock()

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_record

            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_recorder.async_session_factory.return_value = mock_session
            mock_recorder_class.return_value = mock_recorder

            response = client.get("/api/v1/intents/1")

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == 1
            assert data["agent_id"] == "agent-001"
            assert data["intent_type"] == "decision"


@pytest.mark.asyncio
async def test_get_intent_not_found(client):
    """测试获取不存在的意图"""
    with patch("cortex.monitor.routers.intents.IntentRecorder") as mock_recorder_class:
        with patch("cortex.monitor.routers.intents.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.intent_engine.enabled = True
            mock_get_settings.return_value = mock_settings

            mock_recorder = MagicMock()
            mock_recorder.initialize = AsyncMock()
            mock_recorder.close = AsyncMock()

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None

            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_recorder.async_session_factory.return_value = mock_session
            mock_recorder_class.return_value = mock_recorder

            response = client.get("/api/v1/intents/999")

            assert response.status_code == 404


@pytest.mark.asyncio
async def test_intent_stats_summary(client):
    """测试意图统计摘要"""
    from cortex.common.intent_recorder import IntentRecord
    from datetime import datetime

    mock_records = [
        IntentRecord(
            id=1,
            timestamp=datetime.utcnow(),
            agent_id="agent-001",
            intent_type="decision",
            level="L1",
            category="disk_cleanup",
            description="Test 1",
            metadata_json=None,
            status="completed",
        ),
        IntentRecord(
            id=2,
            timestamp=datetime.utcnow(),
            agent_id="agent-001",
            intent_type="blocker",
            level="L3",
            category="database_error",
            description="Test 2",
            metadata_json=None,
            status=None,
        ),
        IntentRecord(
            id=3,
            timestamp=datetime.utcnow(),
            agent_id="agent-002",
            intent_type="milestone",
            level=None,
            category="probe_completed",
            description="Test 3",
            metadata_json=None,
            status=None,
        ),
    ]

    with patch("cortex.monitor.routers.intents.IntentRecorder") as mock_recorder_class:
        with patch("cortex.monitor.routers.intents.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.intent_engine.enabled = True
            mock_get_settings.return_value = mock_settings

            mock_recorder = MagicMock()
            mock_recorder.initialize = AsyncMock()
            mock_recorder.close = AsyncMock()

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = mock_records

            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_recorder.async_session_factory.return_value = mock_session
            mock_recorder_class.return_value = mock_recorder

            response = client.get("/api/v1/intents/stats/summary?hours=24")

            assert response.status_code == 200
            data = response.json()

            assert data["total"] == 3
            assert data["time_range_hours"] == 24
            assert data["by_type"]["decision"] == 1
            assert data["by_type"]["blocker"] == 1
            assert data["by_type"]["milestone"] == 1
            assert data["by_level"]["L1"] == 1
            assert data["by_level"]["L3"] == 1
            assert data["by_agent"]["agent-001"] == 2
            assert data["by_agent"]["agent-002"] == 1


@pytest.mark.asyncio
async def test_intent_engine_disabled(client):
    """测试 Intent-Engine 禁用时的响应"""
    with patch("cortex.monitor.routers.intents.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.intent_engine.enabled = False
        mock_get_settings.return_value = mock_settings

        response = client.get("/api/v1/intents")

        assert response.status_code == 503
        assert "disabled" in response.json()["detail"].lower()
