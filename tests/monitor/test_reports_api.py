"""
测试 Reports API
"""

import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime

from cortex.monitor.database import Agent
from cortex.common.models import ProbeReport, SystemMetrics, IssueReport, ActionReport


@pytest.mark.asyncio
class TestReportsAPI:
    """测试报告 API"""

    async def test_submit_report_success(self, test_db_session, test_app):
        """测试提交报告成功"""
        # 先创建 Agent
        agent = Agent(
            id="test-agent-001",
            name="Test Agent",
            api_key="test-api-key-001",
            status="online",
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        # 创建符合 ProbeReport 模型的报告数据
        report_data = {
            "agent_id": "test-agent-001",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",  # AgentStatus enum: healthy/warning/critical
            "metrics": {  # SystemMetrics 对象
                "cpu_percent": 45.5,
                "memory_percent": 60.2,
                "disk_percent": 70.0,
                "load_average": [1.5, 1.2, 1.0],
                "uptime_seconds": 86400,
            },
            "issues": [  # IssueReport 列表
                {
                    "level": "L1",  # IssueLevel enum: L1/L2/L3
                    "type": "high_cpu",
                    "description": "CPU usage is above 80%",
                    "severity": "medium",  # Severity enum: low/medium/high/critical
                    "details": {"threshold": 80, "current": 85},
                }
            ],
            "actions_taken": [  # ActionReport 列表
                {
                    "level": "L1",  # Literal["L1", "L2"]
                    "action": "restart_nginx",
                    "result": "success",  # ActionResult enum: success/failed/partial
                    "details": "Service restarted successfully",
                }
            ],
            "metadata": {"probe_version": "1.0.0"},
        }

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/reports",
                json=report_data,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "report_id" in data["data"]
        # API 返回包装格式：{"success": True, "data": {"report_id": 1, ...}, "message": "...", "timestamp": "..."}

    async def test_submit_report_agent_not_found(self, test_db_session, test_app):
        """测试提交报告时 Agent 不存在"""
        report_data = {
            "agent_id": "nonexistent-agent",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",
            "metrics": {
                "cpu_percent": 45.5,
                "memory_percent": 60.2,
                "disk_percent": 70.0,
                "load_average": [1.5, 1.2, 1.0],
                "uptime_seconds": 86400,
            },
        }

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/reports",
                json=report_data,
            )

        # 应该自动创建 Agent 或返回 404
        assert response.status_code in [200, 404]

    @pytest.mark.skip(reason="GET /reports API 未实现")
    async def test_list_reports(self, test_db_session, test_app, admin_token):
        """测试列出报告"""
        # 先创建 Agent
        agent = Agent(
            id="test-agent-002",
            name="Test Agent 2",
            api_key="test-api-key-002",
            status="online",
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        # 提交报告
        report_data = {
            "agent_id": "test-agent-002",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",
            "metrics": {
                "cpu_percent": 30.0,
                "memory_percent": 50.0,
                "disk_percent": 60.0,
                "load_average": [1.0, 1.0, 1.0],
                "uptime_seconds": 3600,
            },
        }

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # 提交报告
            await client.post("/api/v1/reports", json=report_data)

            # 列出报告
            response = await client.get(
                "/api/v1/reports",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.skip(reason="GET /reports API 未实现")
    async def test_list_reports_by_agent(self, test_db_session, test_app, admin_token):
        """测试按 Agent 筛选报告"""
        # 创建两个 Agent
        agent1 = Agent(id="agent-001", name="Agent 1", api_key="api-key-001", status="online")
        agent2 = Agent(id="agent-002", name="Agent 2", api_key="api-key-002", status="online")
        test_db_session.add(agent1)
        test_db_session.add(agent2)
        await test_db_session.commit()

        # 为每个 Agent 提交报告
        report1 = {
            "agent_id": "agent-001",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",
            "metrics": {
                "cpu_percent": 20.0,
                "memory_percent": 40.0,
                "disk_percent": 50.0,
                "load_average": [0.5, 0.5, 0.5],
                "uptime_seconds": 7200,
            },
        }
        report2 = {
            "agent_id": "agent-002",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "warning",
            "metrics": {
                "cpu_percent": 80.0,
                "memory_percent": 85.0,
                "disk_percent": 90.0,
                "load_average": [2.0, 2.0, 2.0],
                "uptime_seconds": 3600,
            },
        }

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            await client.post("/api/v1/reports", json=report1)
            await client.post("/api/v1/reports", json=report2)

            # 查询 agent-001 的报告
            response = await client.get(
                "/api/v1/reports?agent_id=agent-001",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # 所有报告都应该属于 agent-001
        for report in data:
            assert report["agent_id"] == "agent-001"

    @pytest.mark.skip(reason="GET /reports/{id} API 未实现")
    async def test_get_report_detail(self, test_db_session, test_app, admin_token):
        """测试获取报告详情"""
        # 创建 Agent
        agent = Agent(id="test-agent-003", name="Test Agent 3", api_key="api-key-003", status="online")
        test_db_session.add(agent)
        await test_db_session.commit()

        # 提交报告
        report_data = {
            "agent_id": "test-agent-003",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "critical",
            "metrics": {
                "cpu_percent": 95.0,
                "memory_percent": 98.0,
                "disk_percent": 99.0,
                "load_average": [5.0, 5.0, 5.0],
                "uptime_seconds": 1800,
            },
            "issues": [
                {
                    "level": "L3",
                    "type": "system_critical",
                    "description": "系统资源即将耗尽",
                    "severity": "critical",
                    "details": {"cpu": 95, "memory": 98, "disk": 99},
                }
            ],
        }

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # 提交报告
            submit_response = await client.post("/api/v1/reports", json=report_data)
            report_id = submit_response.json()["id"]

            # 获取报告详情
            response = await client.get(
                f"/api/v1/reports/{report_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == report_id
        assert data["agent_id"] == "test-agent-003"
        assert data["status"] == "critical"

    @pytest.mark.skip(reason="GET /reports/{id} API 未实现")
    async def test_get_report_not_found(self, test_db_session, test_app, admin_token):
        """测试获取不存在的报告"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/reports/999999",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 404

    async def test_submit_report_with_l2_request(self, test_db_session, test_app):
        """测试提交包含 L2 决策请求的报告"""
        # 创建 Agent
        agent = Agent(id="test-agent-004", name="Test Agent 4", api_key="api-key-004", status="online")
        test_db_session.add(agent)
        await test_db_session.commit()

        # 创建包含 L2 问题的报告
        report_data = {
            "agent_id": "test-agent-004",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "warning",
            "metrics": {
                "cpu_percent": 70.0,
                "memory_percent": 80.0,
                "disk_percent": 75.0,
                "load_average": [2.5, 2.0, 1.5],
                "uptime_seconds": 5400,
            },
            "issues": [
                {
                    "level": "L2",  # L2 级问题需要决策
                    "type": "database_connection_pool",
                    "description": "Database connection pool exhausted",
                    "severity": "high",
                    "proposed_fix": "Restart database service",
                    "risk_assessment": "中风险：会短暂中断数据库连接",
                    "details": {"pool_size": 100, "active_connections": 100},
                }
            ],
        }

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/reports",
                json=report_data,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "report_id" in data["data"]
        # L2 问题应该触发决策
        assert "l2_decisions" in data["data"]

    async def test_submit_report_invalid_data(self, test_db_session, test_app):
        """测试提交无效数据"""
        invalid_data = {
            "agent_id": "test-agent",
            # 缺少必需字段
        }

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/reports",
                json=invalid_data,
            )

        assert response.status_code == 422  # Validation error
