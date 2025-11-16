"""
Monitor 数据库模型测试
"""

from datetime import datetime

import pytest
from sqlalchemy import select

from cortex.monitor.database import Agent, Alert, Decision, Report


@pytest.mark.asyncio
async def test_create_agent(test_db_session):
    """测试创建 Agent 记录"""
    agent = Agent(
        id="test-agent-001",
        name="Test Agent",
        api_key="test-api-key-123",
        status="online",
        health_status="healthy",
        last_heartbeat=datetime.now(),
        metadata_json={"region": "us-west-1", "version": "1.0.0"},
    )

    test_db_session.add(agent)
    await test_db_session.commit()

    # 查询验证
    result = await test_db_session.execute(select(Agent).where(Agent.id == "test-agent-001"))
    saved_agent = result.scalar_one()

    assert saved_agent.id == "test-agent-001"
    assert saved_agent.name == "Test Agent"
    assert saved_agent.status == "online"
    assert saved_agent.health_status == "healthy"
    assert saved_agent.metadata_json["region"] == "us-west-1"


@pytest.mark.asyncio
async def test_create_report(test_db_session):
    """测试创建 Report 记录"""
    report = Report(
        agent_id="test-agent-001",
        timestamp=datetime.now(),
        status="healthy",
        metrics={
            "cpu_percent": 45.2,
            "memory_percent": 62.1,
            "disk_percent": 55.0,
        },
        issues=[
            {
                "type": "disk_usage",
                "severity": "L1",
                "description": "Disk usage above 80%",
            }
        ],
        actions_taken=[
            {
                "action": "cleanup_temp_files",
                "result": "success",
                "freed_space_mb": 1024,
            }
        ],
    )

    test_db_session.add(report)
    await test_db_session.commit()

    # 查询验证
    result = await test_db_session.execute(select(Report).where(Report.agent_id == "test-agent-001"))
    saved_report = result.scalar_one()

    assert saved_report.agent_id == "test-agent-001"
    assert saved_report.status == "healthy"
    assert saved_report.metrics["cpu_percent"] == 45.2
    assert len(saved_report.issues) == 1
    assert saved_report.issues[0]["type"] == "disk_usage"
    assert len(saved_report.actions_taken) == 1


@pytest.mark.asyncio
async def test_create_decision(test_db_session):
    """测试创建 Decision 记录"""
    decision = Decision(
        agent_id="test-agent-001",
        issue_type="high_memory",
        issue_description="Memory usage above 90%",
        proposed_action="Restart memory-heavy service",
        llm_analysis="The proposed action is safe and appropriate",
        status="approved",
        reason="Low risk operation that can effectively solve the problem",
    )

    test_db_session.add(decision)
    await test_db_session.commit()

    # 查询验证
    result = await test_db_session.execute(select(Decision).where(Decision.agent_id == "test-agent-001"))
    saved_decision = result.scalar_one()

    assert saved_decision.agent_id == "test-agent-001"
    assert saved_decision.issue_type == "high_memory"
    assert saved_decision.status == "approved"
    assert saved_decision.llm_analysis is not None


@pytest.mark.asyncio
async def test_create_alert(test_db_session):
    """测试创建 Alert 记录"""
    alert = Alert(
        agent_id="test-agent-001",
        level="L3",
        type="system_down",
        description="Database connection failed",
        severity="critical",
        details={
            "error": "Connection timeout",
            "host": "db.example.com",
            "port": 5432,
        },
        status="new",
    )

    test_db_session.add(alert)
    await test_db_session.commit()

    # 查询验证
    result = await test_db_session.execute(select(Alert).where(Alert.agent_id == "test-agent-001"))
    saved_alert = result.scalar_one()

    assert saved_alert.agent_id == "test-agent-001"
    assert saved_alert.level == "L3"
    assert saved_alert.type == "system_down"
    assert saved_alert.severity == "critical"
    assert saved_alert.status == "new"
    assert saved_alert.details["port"] == 5432


@pytest.mark.asyncio
async def test_agent_unique_api_key(test_db_session):
    """测试 Agent API Key 唯一性约束"""
    agent1 = Agent(
        id="agent-001",
        name="Agent 1",
        api_key="unique-key-123",
        status="online",
    )

    agent2 = Agent(
        id="agent-002",
        name="Agent 2",
        api_key="unique-key-123",  # 相同的 API Key
        status="online",
    )

    test_db_session.add(agent1)
    await test_db_session.commit()

    test_db_session.add(agent2)

    # 应该抛出唯一性约束错误
    with pytest.raises(Exception):  # SQLAlchemy IntegrityError
        await test_db_session.commit()
