"""
测试 Agents API
"""

import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime

from cortex.monitor.database import Agent


@pytest.mark.asyncio
class TestAgentsAPI:
    """测试 Agent 管理 API"""

    async def test_register_agent_success(self, test_db_session, test_app):
        """测试注册新 Agent 成功"""
        registration_data = {
            "agent_id": "test-agent-new-001",
            "name": "Test Agent 001",
            "api_key": "test-api-key-001",
            "registration_token": "test-token",  # 从 test_settings 中的配置
        }

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/v1/agents", json=registration_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["agent_id"] == "test-agent-new-001"
        assert data["data"]["action"] == "created"
        assert "created_at" in data["data"]

    async def test_register_agent_invalid_token(self, test_db_session, test_app):
        """测试使用无效 token 注册 Agent"""
        registration_data = {
            "agent_id": "test-agent-002",
            "name": "Test Agent 002",
            "api_key": "test-api-key-002",
            "registration_token": "invalid-token",
        }

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/v1/agents", json=registration_data)

        assert response.status_code == 401

    async def test_update_existing_agent(self, test_db_session, test_app):
        """测试更新已有 Agent"""
        # 先创建 Agent
        agent = Agent(
            id="test-agent-003",
            name="Original Name",
            api_key="original-key",
            status="offline",
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        # 使用新数据重新注册（更新）
        registration_data = {
            "agent_id": "test-agent-003",
            "name": "Updated Name",
            "api_key": "updated-key",
            "registration_token": "test-token",
        }

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/v1/agents", json=registration_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["agent_id"] == "test-agent-003"
        assert data["data"]["name"] == "Updated Name"
        assert data["data"]["action"] == "updated"

    async def test_list_agents(self, test_db_session, test_app, admin_token):
        """测试列出所有 Agents"""
        # 创建测试 Agents
        agents = [
            Agent(id="list-agent-001", name="Agent 1", api_key="key1", status="online"),
            Agent(id="list-agent-002", name="Agent 2", api_key="key2", status="offline"),
        ]
        for agent in agents:
            test_db_session.add(agent)
        await test_db_session.commit()

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/agents",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "agents" in data["data"]
        assert data["data"]["count"] >= 2

    async def test_list_agents_filter_by_status(self, test_db_session, test_app, admin_token):
        """测试按状态筛选 Agents"""
        # 创建不同状态的 Agents
        agents = [
            Agent(id="filter-agent-001", name="Online Agent", api_key="key1", status="online"),
            Agent(id="filter-agent-002", name="Offline Agent", api_key="key2", status="offline"),
        ]
        for agent in agents:
            test_db_session.add(agent)
        await test_db_session.commit()

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/agents?status=online",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # 所有返回的 agents 都应该是 online 状态
        for agent in data["data"]["agents"]:
            assert agent["status"] == "online"

    async def test_get_agent_detail(self, test_db_session, test_app, admin_token):
        """测试获取 Agent 详情"""
        # 创建 Agent
        agent = Agent(
            id="detail-agent-001",
            name="Detail Test Agent",
            api_key="detail-key",
            status="online",
            health_status="healthy",
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/agents/detail-agent-001",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == "detail-agent-001"
        assert data["data"]["name"] == "Detail Test Agent"
        assert data["data"]["status"] == "online"
        assert "statistics" in data["data"]
        assert "total_reports" in data["data"]["statistics"]

    async def test_get_agent_not_found(self, test_db_session, test_app, admin_token):
        """测试获取不存在的 Agent"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/agents/nonexistent-agent",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 404

    async def test_agent_heartbeat(self, test_db_session, test_app):
        """测试 Agent 心跳"""
        # 创建 Agent
        agent = Agent(
            id="heartbeat-agent-001",
            name="Heartbeat Test Agent",
            api_key="heartbeat-key",
            status="offline",
            health_status="unknown",
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        # 发送心跳
        heartbeat_data = {
            "health_status": "healthy"
        }

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/agents/heartbeat-agent-001/heartbeat",
                json=heartbeat_data,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["agent_id"] == "heartbeat-agent-001"
        assert data["data"]["status"] == "online"  # 心跳后应该是 online
        assert data["data"]["health_status"] == "healthy"

    async def test_agent_heartbeat_not_found(self, test_db_session, test_app):
        """测试不存在的 Agent 发送心跳"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/agents/nonexistent-agent/heartbeat",
                json={},
            )

        assert response.status_code == 404

    async def test_delete_agent(self, test_db_session, test_app, admin_token):
        """测试删除 Agent"""
        # 创建 Agent
        agent = Agent(
            id="delete-agent-001",
            name="Delete Test Agent",
            api_key="delete-key",
            status="offline",
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.delete(
                "/api/v1/agents/delete-agent-001",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["agent_id"] == "delete-agent-001"

    async def test_delete_agent_not_found(self, test_db_session, test_app, admin_token):
        """测试删除不存在的 Agent"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.delete(
                "/api/v1/agents/nonexistent-agent",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 404

    async def test_register_agent_with_parent(self, test_db_session, test_app):
        """测试注册带父节点的 Agent（集群模式）"""
        # 先创建父 Agent
        parent_agent = Agent(
            id="parent-agent-001",
            name="Parent Agent",
            api_key="parent-key",
            status="online",
        )
        test_db_session.add(parent_agent)
        await test_db_session.commit()

        # 注册子 Agent
        registration_data = {
            "agent_id": "child-agent-001",
            "name": "Child Agent",
            "api_key": "child-key",
            "registration_token": "test-token",
            "parent_id": "parent-agent-001",
            "upstream_monitor_url": "http://parent-agent:18000",
        }

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/v1/agents", json=registration_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["agent_id"] == "child-agent-001"

    async def test_register_agent_with_invalid_parent(self, test_db_session, test_app):
        """测试注册时指定不存在的父节点"""
        registration_data = {
            "agent_id": "orphan-agent-001",
            "name": "Orphan Agent",
            "api_key": "orphan-key",
            "registration_token": "test-token",
            "parent_id": "nonexistent-parent",
        }

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/api/v1/agents", json=registration_data)

        assert response.status_code == 404
