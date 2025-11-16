"""
Monitor API 端点测试
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from cortex.common.models import ProbeReport, SystemMetrics
from cortex.monitor.database import Agent, Alert, Decision


@pytest.mark.asyncio
async def test_health_check():
    """测试健康检查端点"""
    from cortex.monitor.app import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_receive_report_new_agent(test_db_session):
    """测试接收来自新 Agent 的报告"""
    from cortex.monitor.app import app, get_db_manager

    # Mock 数据库会话
    async def override_get_session():
        yield test_db_session

    # 注入测试数据库会话
    app.dependency_overrides[lambda: get_db_manager().get_session()] = override_get_session

    report_data = {
        "agent_id": "new-agent-001",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "healthy",
        "metrics": {
            "cpu_percent": 25.5,
            "memory_percent": 45.2,
            "disk_percent": 60.0,
            "network_bytes_sent": 1024000,
            "network_bytes_recv": 2048000,
        },
        "issues": [],
        "actions_taken": [],
        "metadata": {"version": "1.0.0"},
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/reports", json=report_data)

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Report received successfully"

    # 清理
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_receive_heartbeat(test_db_session):
    """测试心跳端点"""
    from cortex.monitor.app import app, get_db_manager

    # 预先创建 Agent
    agent = Agent(
        id="test-agent-heartbeat",
        name="Test Agent",
        api_key="test-key",
        status="offline",
    )
    test_db_session.add(agent)
    await test_db_session.commit()

    # Mock 数据库会话
    async def override_get_session():
        yield test_db_session

    app.dependency_overrides[lambda: get_db_manager().get_session()] = override_get_session

    heartbeat_data = {
        "agent_id": "test-agent-heartbeat",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "healthy",
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/heartbeat", json=heartbeat_data)

    assert response.status_code == 200

    # 验证 Agent 状态已更新
    await test_db_session.refresh(agent)
    assert agent.status == "online"
    assert agent.last_heartbeat is not None

    # 清理
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_agents_list(test_db_session):
    """测试获取 Agent 列表"""
    from cortex.monitor.app import app, get_db_manager

    # 创建测试 Agents
    agents = [
        Agent(id="agent-001", name="Agent 1", api_key="key1", status="online"),
        Agent(id="agent-002", name="Agent 2", api_key="key2", status="offline"),
    ]
    for agent in agents:
        test_db_session.add(agent)
    await test_db_session.commit()

    # Mock 数据库会话
    async def override_get_session():
        yield test_db_session

    app.dependency_overrides[lambda: get_db_manager().get_session()] = override_get_session

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/agents")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "agent-001"

    # 清理
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_decisions_list(test_db_session):
    """测试获取决策列表"""
    from cortex.monitor.app import app, get_db_manager

    # 创建测试决策
    decisions = [
        Decision(
            agent_id="agent-001",
            issue_type="high_cpu",
            issue_description="CPU usage high",
            proposed_action="Restart service",
            status="approved",
        ),
        Decision(
            agent_id="agent-001",
            issue_type="high_memory",
            issue_description="Memory usage high",
            proposed_action="Clear cache",
            status="rejected",
        ),
    ]
    for decision in decisions:
        test_db_session.add(decision)
    await test_db_session.commit()

    # Mock 数据库会话
    async def override_get_session():
        yield test_db_session

    app.dependency_overrides[lambda: get_db_manager().get_session()] = override_get_session

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/decisions")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # 清理
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_alerts_list(test_db_session):
    """测试获取告警列表"""
    from cortex.monitor.app import app, get_db_manager

    # 创建测试告警
    alerts = [
        Alert(
            agent_id="agent-001",
            type="service_down",
            severity="critical",
            message="Service is down",
            status="new",
        ),
        Alert(
            agent_id="agent-002",
            type="disk_full",
            severity="warning",
            message="Disk almost full",
            status="acknowledged",
        ),
    ]
    for alert in alerts:
        test_db_session.add(alert)
    await test_db_session.commit()

    # Mock 数据库会话
    async def override_get_session():
        yield test_db_session

    app.dependency_overrides[lambda: get_db_manager().get_session()] = override_get_session

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/alerts")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["severity"] == "critical"

    # 清理
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_acknowledge_alert(test_db_session):
    """测试确认告警"""
    from cortex.monitor.app import app, get_db_manager

    # 创建测试告警
    alert = Alert(
        agent_id="agent-001",
        type="test_alert",
        severity="warning",
        message="Test alert",
        status="new",
    )
    test_db_session.add(alert)
    await test_db_session.commit()
    alert_id = alert.id

    # Mock 数据库会话
    async def override_get_session():
        yield test_db_session

    app.dependency_overrides[lambda: get_db_manager().get_session()] = override_get_session

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(f"/api/v1/alerts/{alert_id}/acknowledge")

    assert response.status_code == 200

    # 验证状态已更新
    await test_db_session.refresh(alert)
    assert alert.status == "acknowledged"

    # 清理
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cluster_overview(test_db_session):
    """测试集群概览"""
    from cortex.monitor.app import app, get_db_manager

    # 创建测试数据
    agents = [
        Agent(id="agent-001", name="Agent 1", api_key="key1", status="online", health_status="healthy"),
        Agent(id="agent-002", name="Agent 2", api_key="key2", status="online", health_status="warning"),
        Agent(id="agent-003", name="Agent 3", api_key="key3", status="offline", health_status="critical"),
    ]
    for agent in agents:
        test_db_session.add(agent)
    await test_db_session.commit()

    # Mock 数据库会话
    async def override_get_session():
        yield test_db_session

    app.dependency_overrides[lambda: get_db_manager().get_session()] = override_get_session

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/cluster/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["total_agents"] == 3
    assert data["online_agents"] == 2
    assert data["offline_agents"] == 1

    # 清理
    app.dependency_overrides.clear()
