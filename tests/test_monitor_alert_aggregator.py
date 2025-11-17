"""
AlertAggregator 测试
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from cortex.common.models import IssueReport
from cortex.monitor.database import Alert
from cortex.monitor.services.alert_aggregator import AlertAggregator


@pytest.fixture
def alert_aggregator(test_settings):
    """创建 AlertAggregator 实例（使用真实的测试配置）"""
    return AlertAggregator(test_settings)


@pytest.fixture
def sample_l3_issue():
    """创建示例 L3 问题"""
    return IssueReport(
        level="L3",
        type="database_connection_failed",
        severity="critical",
        description="Unable to connect to primary database",
        proposed_fix="Manual intervention required",
        risk_assessment="Critical - service degradation",
        details={"database": "postgres-primary", "error_code": "CONNECTION_TIMEOUT"},
    )


@pytest.mark.asyncio
async def test_process_issues_create_new_alert(alert_aggregator, sample_l3_issue, test_db_session):
    """测试处理 L3 问题并创建新告警"""
    issues = [sample_l3_issue]

    alerts = await alert_aggregator.process_issues(
        issues=issues, agent_id="test-agent-001", session=test_db_session
    )

    assert len(alerts) == 1
    assert alerts[0].agent_id == "test-agent-001"
    assert alerts[0].type == "database_connection_failed"
    assert alerts[0].severity == "critical"
    assert alerts[0].status == "new"


@pytest.mark.asyncio
async def test_duplicate_alert_detection(alert_aggregator, sample_l3_issue, test_db_session):
    """测试告警去重功能"""
    # 第一次处理 - 应该创建告警
    alerts_first = await alert_aggregator.process_issues(
        issues=[sample_l3_issue], agent_id="test-agent-001", session=test_db_session
    )
    assert len(alerts_first) == 1

    # 第二次处理相同问题（30分钟内）- 应该被去重
    alerts_second = await alert_aggregator.process_issues(
        issues=[sample_l3_issue], agent_id="test-agent-001", session=test_db_session
    )
    assert len(alerts_second) == 0  # 已去重，不创建新告警


@pytest.mark.asyncio
async def test_alert_dedup_window_expired(alert_aggregator, sample_l3_issue, test_db_session):
    """测试去重时间窗口过期后可以创建新告警"""
    # 创建一个旧告警（超过去重窗口）
    old_alert = Alert(
        agent_id="test-agent-001",
        level="L3",
        type="database_connection_failed",
        description="Unable to connect to primary database",
        severity="critical",
        status="new",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=35),  # 35分钟前
    )
    test_db_session.add(old_alert)
    await test_db_session.commit()

    # 处理新的相同问题 - 应该创建新告警（时间窗口已过）
    alerts = await alert_aggregator.process_issues(
        issues=[sample_l3_issue], agent_id="test-agent-001", session=test_db_session
    )
    assert len(alerts) == 1


@pytest.mark.asyncio
async def test_multiple_different_alerts(alert_aggregator, test_db_session):
    """测试处理多个不同类型的告警"""
    issues = [
        IssueReport(
            level="L3",
            type="disk_full",
            severity="critical",
            description="Disk usage at 99%",
            proposed_fix="Manual cleanup required",
            risk_assessment="Critical",
        ),
        IssueReport(
            level="L3",
            type="service_down",
            severity="critical",
            description="Web service not responding",
            proposed_fix="Restart service manually",
            risk_assessment="Critical",
        ),
    ]

    alerts = await alert_aggregator.process_issues(
        issues=issues, agent_id="test-agent-002", session=test_db_session
    )

    assert len(alerts) == 2
    assert alerts[0].type == "disk_full"
    assert alerts[1].type == "service_down"


@pytest.mark.asyncio
async def test_get_alert_summary(alert_aggregator, test_db_session):
    """测试获取告警摘要统计"""
    # 创建多个不同状态的告警
    alerts = [
        Alert(
            agent_id="agent-001",
            level="L3",
            type="issue_type_1",
            description="Test alert 1",
            severity="critical",
            status="new",
        ),
        Alert(
            agent_id="agent-001",
            level="L2",
            type="issue_type_2",
            description="Test alert 2",
            severity="medium",
            status="acknowledged",
        ),
        Alert(
            agent_id="agent-002",
            level="L3",
            type="issue_type_3",
            description="Test alert 3",
            severity="critical",
            status="new",
        ),
    ]

    for alert in alerts:
        test_db_session.add(alert)
    await test_db_session.commit()

    # 获取摘要
    summary = await alert_aggregator.get_alerts_summary(session=test_db_session, hours=24)

    assert summary["total_alerts"] == 3
    assert summary["by_severity"]["critical"] == 2
    assert summary["by_severity"]["medium"] == 1
    assert summary["by_status"]["new"] == 2
    assert summary["by_status"]["acknowledged"] == 1


@pytest.mark.asyncio
async def test_format_alert_notification(alert_aggregator, sample_l3_issue):
    """测试格式化告警通知消息"""
    alert = Alert(
        agent_id="test-agent-001",
        level="L3",
        type="database_connection_failed",
        description="Unable to connect to primary database",
        severity="critical",
        details={"database": "postgres-primary"},
        status="new",
        created_at=datetime.now(timezone.utc),
    )

    message = alert_aggregator.format_alert_for_notification(alert)

    assert "🚨" in message or "critical" in message.lower()
    assert "test-agent-001" in message
    assert "database_connection_failed" in message
    assert "Unable to connect" in message


@pytest.mark.asyncio
async def test_alert_different_agents_no_dedup(alert_aggregator, sample_l3_issue, test_db_session):
    """测试来自不同 Agent 的相同问题不会去重"""
    # Agent 1 创建告警
    alerts_agent1 = await alert_aggregator.process_issues(
        issues=[sample_l3_issue], agent_id="agent-001", session=test_db_session
    )
    assert len(alerts_agent1) == 1

    # Agent 2 报告相同问题 - 应该创建新告警（不同 Agent）
    alerts_agent2 = await alert_aggregator.process_issues(
        issues=[sample_l3_issue], agent_id="agent-002", session=test_db_session
    )
    assert len(alerts_agent2) == 1

    # 验证数据库中有两条告警
    result = await test_db_session.execute(select(Alert))
    all_alerts = result.scalars().all()
    assert len(all_alerts) == 2
