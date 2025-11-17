"""
Probe ↔ Monitor 端到端集成测试

测试完整的 Probe-Monitor 通信流程：
1. L1 问题：Probe 自主修复
2. L2 问题：Monitor 决策批准/拒绝
3. L3 问题：触发告警和通知
4. 混合问题：L1+L2+L3 同时处理
5. Intent-Engine 完整记录
"""

from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.common.models import (
    ActionReport,
    ActionResult,
    AgentStatus,
    IssueReport,
    ProbeReport,
    Severity,
    SystemMetrics,
)
from cortex.monitor.database import Agent, Alert, Decision, Report
from cortex.monitor.app import app


class TestL1SelfHealing:
    """测试 L1 问题的自主修复流程"""

    @pytest.mark.asyncio
    async def test_l1_disk_cleanup_自主修复(self, test_db_session: AsyncSession):
        """
        场景：Probe 检测到 /tmp 磁盘使用率 80%，自主清理成功

        流程：
        1. Probe 检测问题
        2. Probe 自主执行清理（L1）
        3. 生成报告（无 issues，有 actions_taken）
        4. 上报 Monitor
        5. Monitor 存储报告
        6. Intent-Engine 记录操作
        """
        # 准备测试数据库
        from cortex.monitor.routers.reports import get_session

        # 创建测试 Agent
        agent = Agent(
            id="probe-001",
            name="Test Probe 001",
            api_key="test-key-001",
            status="online",
            health_status="healthy",
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        # 模拟 Probe 生成的 L1 自主修复报告
        report_data = ProbeReport(
            agent_id="probe-001",
            timestamp=datetime.utcnow(),
            status=AgentStatus.HEALTHY,  # L1 问题已解决，状态健康
            metrics=SystemMetrics(
                cpu_percent=25.0,
                memory_percent=45.0,
                disk_percent=78.0,  # 清理后降低到 78%
                load_average=[1.0, 1.2, 1.5],
                uptime_seconds=86400,
            ),
            issues=[],  # L1 问题已自主修复，不需要上报 issues
            actions_taken=[
                ActionReport(
                    level="L1",
                    action="disk_cleanup",
                    result=ActionResult.SUCCESS,
                    details="Cleaned /tmp directory, freed 2.5GB. Before: 85%, After: 78%. Removed 150 files.",
                )
            ],
            metadata={"version": "1.0.0", "execution_time_seconds": 5.2},
        )

        # Mock 数据库会话注入
        async def override_get_session():
            yield test_db_session

        app.dependency_overrides[get_session] = override_get_session

        try:
            # 发送报告到 Monitor
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/reports",
                    json=report_data.model_dump(mode="json"),
                )

            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "report_id" in data["data"]
            assert data["data"]["l2_decisions"] == []  # L1 无需决策
            assert data["data"]["l3_alerts_triggered"] == 0

            # 验证数据库记录
            result = await test_db_session.execute(
                select(Report).where(Report.agent_id == "probe-001")
            )
            stored_report = result.scalar_one()

            assert stored_report.status == "healthy"
            assert len(stored_report.actions_taken) == 1
            assert stored_report.actions_taken[0]["level"] == "L1"
            assert stored_report.actions_taken[0]["action"] == "disk_cleanup"
            assert len(stored_report.issues) == 0

        finally:
            # 清理
            app.dependency_overrides.clear()


class TestL2DecisionApproval:
    """测试 L2 问题的决策批准流程"""

    @pytest.mark.asyncio
    async def test_l2_memory_restart_批准执行(self, test_db_session: AsyncSession):
        """
        场景：Probe 检测到内存使用率 88%，请求重启服务，Monitor 批准

        流程：
        1. Probe 检测到 L2 问题
        2. 上报 Monitor 请求决策
        3. Monitor LLM 分析风险（Mock）
        4. Monitor 返回 "approved" 决策
        5. Probe 执行操作（Mock）
        6. 验证 Decision 记录
        """
        from cortex.monitor.routers.reports import get_session
        from cortex.monitor.services.decision_engine import DecisionEngine

        # 创建测试 Agent
        agent = Agent(
            id="probe-002",
            name="Test Probe 002",
            api_key="test-key-002",
            status="online",
            health_status="warning",
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        # 模拟 Probe 生成的 L2 决策请求报告
        report_data = ProbeReport(
            agent_id="probe-002",
            timestamp=datetime.utcnow(),
            status=AgentStatus.WARNING,
            metrics=SystemMetrics(
                cpu_percent=30.0,
                memory_percent=88.0,  # 高内存使用
                disk_percent=60.0,
                load_average=[2.0, 2.5, 2.8],
                uptime_seconds=172800,
            ),
            issues=[
                IssueReport(
                    level="L2",
                    type="high_memory",
                    description="Memory usage at 88%, exceeding threshold 85%",
                    severity=Severity.MEDIUM,
                    proposed_fix="Restart memory-intensive service: backend-worker",
                    risk_assessment="Low risk - worker service has auto-recovery mechanism",
                    details={
                        "current_percent": 88.0,
                        "threshold_percent": 85.0,
                        "top_process": "backend-worker",
                        "process_memory_mb": 4096,
                    },
                )
            ],
            actions_taken=[],
            metadata={},
        )

        # Mock DecisionEngine 的 analyze_and_decide 方法
        async def mock_analyze_and_decide(issue, agent_id, session):
            # 模拟 LLM 分析后批准决策
            decision = Decision(
                agent_id=agent_id,
                issue_type=issue.type,
                issue_description=issue.description,
                proposed_action=issue.proposed_fix,
                llm_analysis="分析：内存使用率确实超过阈值，重启worker服务风险较低，有自动恢复机制。建议批准。",
                status="approved",
                reason="风险评估为低，服务有自动恢复机制，可以执行重启操作",
            )
            session.add(decision)
            await session.flush()  # 获取 decision.id
            return decision

        # Mock 数据库会话
        async def override_get_session():
            yield test_db_session

        app.dependency_overrides[get_session] = override_get_session

        try:
            # Patch DecisionEngine
            with patch.object(
                DecisionEngine, "analyze_and_decide", side_effect=mock_analyze_and_decide
            ):
                # 发送报告到 Monitor
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/v1/reports",
                        json=report_data.model_dump(mode="json"),
                    )

            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]["l2_decisions"]) == 1

            decision_response = data["data"]["l2_decisions"][0]
            assert decision_response["status"] == "approved"
            assert decision_response["issue_type"] == "high_memory"
            assert "decision_id" in decision_response

            # 验证数据库中的 Decision 记录
            result = await test_db_session.execute(
                select(Decision).where(Decision.agent_id == "probe-002")
            )
            stored_decision = result.scalar_one()

            assert stored_decision.status == "approved"
            assert stored_decision.issue_type == "high_memory"
            assert "风险评估为低" in stored_decision.reason
            assert stored_decision.llm_analysis is not None

        finally:
            app.dependency_overrides.clear()


class TestL2DecisionRejection:
    """测试 L2 问题的决策拒绝流程"""

    @pytest.mark.asyncio
    async def test_l2_kill_process_拒绝执行(self, test_db_session: AsyncSession):
        """
        场景：Probe 检测到 CPU 高，建议 kill 关键进程，Monitor 拒绝

        流程：
        1. Probe 检测到 L2 问题（高风险操作）
        2. 上报 Monitor 请求决策
        3. Monitor LLM 分析后拒绝（高风险）
        4. Monitor 返回 "rejected" 决策
        5. Probe 不执行操作
        """
        from cortex.monitor.routers.reports import get_session
        from cortex.monitor.services.decision_engine import DecisionEngine

        # 创建测试 Agent
        agent = Agent(
            id="probe-003",
            name="Test Probe 003",
            api_key="test-key-003",
            status="online",
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        # 模拟高风险 L2 决策请求
        report_data = ProbeReport(
            agent_id="probe-003",
            timestamp=datetime.utcnow(),
            status=AgentStatus.WARNING,
            metrics=SystemMetrics(
                cpu_percent=95.0,  # CPU 极高
                memory_percent=60.0,
                disk_percent=50.0,
                load_average=[8.0, 8.5, 9.0],
                uptime_seconds=3600,
            ),
            issues=[
                IssueReport(
                    level="L2",
                    type="high_cpu",
                    description="CPU usage at 95%, caused by database process",
                    severity=Severity.HIGH,
                    proposed_fix="Kill database main process (PID 1234)",
                    risk_assessment="HIGH RISK - may cause data loss and service outage",
                    details={
                        "current_percent": 95.0,
                        "threshold_percent": 80.0,
                        "process_name": "postgres",
                        "process_pid": 1234,
                    },
                )
            ],
            actions_taken=[],
            metadata={},
        )

        # Mock DecisionEngine 返回拒绝决策
        async def mock_analyze_and_decide_reject(issue, agent_id, session):
            decision = Decision(
                agent_id=agent_id,
                issue_type=issue.type,
                issue_description=issue.description,
                proposed_action=issue.proposed_fix,
                llm_analysis="分析：建议操作为kill数据库主进程，这是极高风险操作。可能导致数据丢失和服务中断。不建议自动执行，需要人工介入。",
                status="rejected",
                reason="高风险操作，可能导致数据丢失，拒绝自动执行，建议人工处理",
            )
            session.add(decision)
            await session.flush()
            return decision

        async def override_get_session():
            yield test_db_session

        app.dependency_overrides[get_session] = override_get_session

        try:
            with patch.object(
                DecisionEngine,
                "analyze_and_decide",
                side_effect=mock_analyze_and_decide_reject,
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/v1/reports",
                        json=report_data.model_dump(mode="json"),
                    )

            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]["l2_decisions"]) == 1

            decision_response = data["data"]["l2_decisions"][0]
            assert decision_response["status"] == "rejected"
            assert "拒绝" in decision_response["reason"]

            # 验证数据库记录
            result = await test_db_session.execute(
                select(Decision).where(Decision.agent_id == "probe-003")
            )
            stored_decision = result.scalar_one()

            assert stored_decision.status == "rejected"
            assert stored_decision.executed_at is None  # 未执行

        finally:
            app.dependency_overrides.clear()


class TestL3AlertTriggering:
    """测试 L3 问题的告警流程"""

    @pytest.mark.asyncio
    async def test_l3_database_down_触发告警(self, test_db_session: AsyncSession):
        """
        场景：Probe 检测到数据库连接失败（L3 严重问题），触发告警

        流程：
        1. Probe 检测到 L3 问题
        2. 上报 Monitor
        3. Monitor 创建 Alert 记录
        4. 触发 Telegram 通知（Mock）
        """
        from cortex.monitor.routers.reports import get_session
        from cortex.monitor.services.alert_aggregator import AlertAggregator
        from cortex.monitor.services.telegram_notifier import TelegramNotifier

        # 创建测试 Agent
        agent = Agent(
            id="probe-004",
            name="Test Probe 004",
            api_key="test-key-004",
            status="online",
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        # 模拟 L3 严重问题报告
        report_data = ProbeReport(
            agent_id="probe-004",
            timestamp=datetime.utcnow(),
            status=AgentStatus.CRITICAL,
            metrics=SystemMetrics(
                cpu_percent=40.0,
                memory_percent=60.0,
                disk_percent=50.0,
                load_average=[2.0, 2.5, 2.8],
                uptime_seconds=3600,
            ),
            issues=[
                IssueReport(
                    level="L3",
                    type="database_connection_failed",
                    description="Cannot connect to PostgreSQL database after 5 retries",
                    severity=Severity.CRITICAL,
                    proposed_fix=None,  # L3 无自动修复方案
                    risk_assessment=None,
                    details={
                        "database": "postgresql",
                        "host": "db.example.com",
                        "port": 5432,
                        "retry_count": 5,
                        "last_error": "connection timeout",
                    },
                )
            ],
            actions_taken=[],
            metadata={},
        )

        # Mock Telegram 通知
        async def mock_send_alert(alert):
            # 模拟发送 Telegram 通知
            return True

        async def override_get_session():
            yield test_db_session

        app.dependency_overrides[get_session] = override_get_session

        try:
            # Patch TelegramNotifier
            with patch.object(
                TelegramNotifier, "send_alert", side_effect=mock_send_alert
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/v1/reports",
                        json=report_data.model_dump(mode="json"),
                    )

            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["l3_alerts_triggered"] == 1

            # 验证数据库中的 Alert 记录
            result = await test_db_session.execute(
                select(Alert).where(Alert.agent_id == "probe-004")
            )
            stored_alert = result.scalar_one()

            assert stored_alert.level == "L3"
            assert stored_alert.type == "database_connection_failed"
            assert stored_alert.severity == "critical"
            assert stored_alert.status == "new"

        finally:
            app.dependency_overrides.clear()


class TestMixedIssuesReport:
    """测试混合问题报告（L1+L2+L3）"""

    @pytest.mark.asyncio
    async def test_l1_l2_l3_混合问题处理(self, test_db_session: AsyncSession):
        """
        场景：单次探测发现多个层级的问题

        - L1: 磁盘清理（已自主处理）
        - L2: 内存重启（需要决策）
        - L3: 网络异常（触发告警）
        """
        from cortex.monitor.routers.reports import get_session
        from cortex.monitor.services.decision_engine import DecisionEngine
        from cortex.monitor.services.telegram_notifier import TelegramNotifier

        # 创建测试 Agent
        agent = Agent(
            id="probe-005",
            name="Test Probe 005",
            api_key="test-key-005",
            status="online",
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        # 模拟混合问题报告
        report_data = ProbeReport(
            agent_id="probe-005",
            timestamp=datetime.utcnow(),
            status=AgentStatus.WARNING,
            metrics=SystemMetrics(
                cpu_percent=40.0,
                memory_percent=87.0,
                disk_percent=78.0,
                load_average=[3.0, 3.5, 3.8],
                uptime_seconds=86400,
            ),
            issues=[
                # L2 问题：需要决策
                IssueReport(
                    level="L2",
                    type="high_memory",
                    description="Memory usage at 87%",
                    severity=Severity.MEDIUM,
                    proposed_fix="Restart cache service",
                    risk_assessment="Low risk",
                    details={"current_percent": 87.0},
                ),
                # L3 问题：触发告警
                IssueReport(
                    level="L3",
                    type="network_connectivity_issue",
                    description="Cannot reach upstream API",
                    severity=Severity.HIGH,
                    proposed_fix=None,
                    risk_assessment=None,
                    details={"target": "api.upstream.com", "timeout": 5},
                ),
            ],
            actions_taken=[
                # L1 问题：已自主处理
                ActionReport(
                    level="L1",
                    action="disk_cleanup",
                    result=ActionResult.SUCCESS,
                    details="Cleaned /var/log directory, freed 1.5GB of space",
                )
            ],
            metadata={},
        )

        # Mock DecisionEngine 和 TelegramNotifier
        async def mock_analyze_and_decide(issue, agent_id, session):
            decision = Decision(
                agent_id=agent_id,
                issue_type=issue.type,
                issue_description=issue.description,
                proposed_action=issue.proposed_fix or "",
                llm_analysis="批准重启缓存服务",
                status="approved",
                reason="低风险操作，批准执行",
            )
            session.add(decision)
            await session.flush()
            return decision

        async def mock_send_alert(alert):
            return True

        async def override_get_session():
            yield test_db_session

        app.dependency_overrides[get_session] = override_get_session

        try:
            with patch.object(
                DecisionEngine, "analyze_and_decide", side_effect=mock_analyze_and_decide
            ):
                with patch.object(
                    TelegramNotifier, "send_alert", side_effect=mock_send_alert
                ):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.post(
                            "/api/v1/reports",
                            json=report_data.model_dump(mode="json"),
                        )

            # 验证响应
            assert response.status_code == 200
            data = response.json()

            # L1: actions_taken 有记录
            # L2: 产生决策
            assert len(data["data"]["l2_decisions"]) == 1
            assert data["data"]["l2_decisions"][0]["status"] == "approved"

            # L3: 触发告警
            assert data["data"]["l3_alerts_triggered"] == 1

            # 验证数据库记录
            # 检查 Report
            report_result = await test_db_session.execute(
                select(Report).where(Report.agent_id == "probe-005")
            )
            stored_report = report_result.scalar_one()

            assert len(stored_report.actions_taken) == 1  # L1
            assert len(stored_report.issues) == 2  # L2 + L3

            # 检查 Decision
            decision_result = await test_db_session.execute(
                select(Decision).where(Decision.agent_id == "probe-005")
            )
            decisions = decision_result.scalars().all()
            assert len(decisions) == 1  # 只有 L2 产生决策

            # 检查 Alert
            alert_result = await test_db_session.execute(
                select(Alert).where(Alert.agent_id == "probe-005")
            )
            alerts = alert_result.scalars().all()
            assert len(alerts) == 1  # 只有 L3 触发告警
            assert alerts[0].type == "network_connectivity_issue"

        finally:
            app.dependency_overrides.clear()
