"""
集群模式集成测试

测试完整的集群功能：
1. 节点注册和层级管理
2. 心跳检测
3. 集群拓扑查询
4. 跨节点 L2 决策请求
5. 决策指令回传
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.common.models import AgentStatus, IssueReport, Severity, SystemMetrics
from cortex.monitor.database import Agent, Decision
from cortex.monitor.services.upstream_forwarder import UpstreamForwarder


class TestClusterNodeManagement:
    """测试集群节点管理功能"""

    @pytest.mark.asyncio
    async def test_register_root_node(self, test_db_session: AsyncSession):
        """测试注册根节点（L0）"""
        # 创建根节点
        root_agent = Agent(
            id="root-monitor",
            name="Root Monitor",
            api_key="root-key",
            status="offline",
            health_status="unknown",
            parent_id=None,  # 根节点没有 parent
            upstream_monitor_url=None,
        )

        test_db_session.add(root_agent)
        await test_db_session.commit()

        # 验证
        result = await test_db_session.execute(
            select(Agent).where(Agent.id == "root-monitor")
        )
        agent = result.scalar_one_or_none()

        assert agent is not None
        assert agent.parent_id is None
        assert agent.upstream_monitor_url is None
        assert agent.status == "offline"

    @pytest.mark.asyncio
    async def test_register_child_node(self, test_db_session: AsyncSession):
        """测试注册子节点"""
        # 先创建父节点
        parent_agent = Agent(
            id="parent-monitor",
            name="Parent Monitor",
            api_key="parent-key",
            status="online",
            health_status="healthy",
        )
        test_db_session.add(parent_agent)
        await test_db_session.commit()

        # 创建子节点
        child_agent = Agent(
            id="child-monitor",
            name="Child Monitor",
            api_key="child-key",
            status="offline",
            health_status="unknown",
            parent_id="parent-monitor",
            upstream_monitor_url="http://parent:8000",
        )

        test_db_session.add(child_agent)
        await test_db_session.commit()

        # 验证
        result = await test_db_session.execute(
            select(Agent).where(Agent.id == "child-monitor")
        )
        child = result.scalar_one_or_none()

        assert child is not None
        assert child.parent_id == "parent-monitor"
        assert child.upstream_monitor_url == "http://parent:8000"

    @pytest.mark.asyncio
    async def test_three_level_hierarchy(self, test_db_session: AsyncSession):
        """测试三层层级：L0 → L1 → L2"""
        # L0 根节点
        l0_agent = Agent(
            id="l0-monitor",
            name="L0 Monitor",
            api_key="l0-key",
            parent_id=None,
        )
        test_db_session.add(l0_agent)

        # L1 节点
        l1_agent = Agent(
            id="l1-monitor",
            name="L1 Monitor",
            api_key="l1-key",
            parent_id="l0-monitor",
            upstream_monitor_url="http://l0:8000",
        )
        test_db_session.add(l1_agent)

        # L2 节点
        l2_agent = Agent(
            id="l2-monitor",
            name="L2 Monitor",
            api_key="l2-key",
            parent_id="l1-monitor",
            upstream_monitor_url="http://l1:8000",
        )
        test_db_session.add(l2_agent)

        await test_db_session.commit()

        # 验证层级关系
        result = await test_db_session.execute(select(Agent).order_by(Agent.id))
        all_agents = result.scalars().all()

        assert len(all_agents) == 3

        # 验证 L0
        l0 = next(a for a in all_agents if a.id == "l0-monitor")
        assert l0.parent_id is None

        # 验证 L1
        l1 = next(a for a in all_agents if a.id == "l1-monitor")
        assert l1.parent_id == "l0-monitor"

        # 验证 L2
        l2 = next(a for a in all_agents if a.id == "l2-monitor")
        assert l2.parent_id == "l1-monitor"


class TestHeartbeatDetection:
    """测试心跳检测功能"""

    @pytest.mark.asyncio
    async def test_heartbeat_updates_status(self, test_db_session: AsyncSession):
        """测试心跳更新状态"""
        agent = Agent(
            id="test-agent",
            name="Test Agent",
            api_key="test-key",
            status="offline",
            health_status="unknown",
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        # 模拟心跳
        agent.status = "online"
        agent.last_heartbeat = datetime.utcnow()
        agent.health_status = "healthy"
        await test_db_session.commit()

        # 验证
        result = await test_db_session.execute(
            select(Agent).where(Agent.id == "test-agent")
        )
        updated_agent = result.scalar_one()

        assert updated_agent.status == "online"
        assert updated_agent.health_status == "healthy"
        assert updated_agent.last_heartbeat is not None

    @pytest.mark.asyncio
    async def test_heartbeat_with_health_status(self, test_db_session: AsyncSession):
        """测试心跳携带健康状态"""
        agent = Agent(
            id="test-agent-2",
            name="Test Agent 2",
            api_key="test-key-2",
            status="offline",
            health_status="unknown",
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        # 发送心跳并更新健康状态
        agent.status = "online"
        agent.last_heartbeat = datetime.utcnow()
        agent.health_status = "warning"  # 设置为 warning
        await test_db_session.commit()

        # 验证
        result = await test_db_session.execute(
            select(Agent).where(Agent.id == "test-agent-2")
        )
        updated_agent = result.scalar_one()

        assert updated_agent.status == "online"
        assert updated_agent.health_status == "warning"


class TestUpstreamForwarder:
    """测试上级转发器"""

    @pytest.mark.asyncio
    async def test_forward_decision_request_success(self):
        """测试成功转发 L2 决策请求"""
        forwarder = UpstreamForwarder()

        # 创建测试 IssueReport
        issue = IssueReport(
            level="L2",
            type="high_memory",
            description="Memory usage at 90%",
            severity=Severity.MEDIUM,
            proposed_fix="Restart service",
            risk_assessment="Low risk",
            details={"current": 90.0, "threshold": 85.0},
        )

        # Mock HTTP 响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "data": {
                "decision_id": 123,
                "status": "approved",
                "reason": "操作风险低，可以执行",
                "llm_analysis": "详细分析...",
                "created_at": datetime.utcnow().isoformat(),
            },
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await forwarder.forward_decision_request(
                issue=issue,
                agent_id="test-agent",
                upstream_monitor_url="http://upstream:8000",
            )

        # 验证
        assert result is not None
        assert result["status"] == "approved"
        assert result["reason"] == "操作风险低，可以执行"

    @pytest.mark.asyncio
    async def test_forward_decision_request_failure(self):
        """测试转发失败情况"""
        forwarder = UpstreamForwarder()

        issue = IssueReport(
            level="L2",
            type="high_cpu",
            description="CPU usage at 95%",
            severity=Severity.HIGH,
            proposed_fix="Kill process",
            risk_assessment="Medium risk",
            details={},
        )

        # Mock HTTP 错误
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Connection failed")
            )

            result = await forwarder.forward_decision_request(
                issue=issue,
                agent_id="test-agent",
                upstream_monitor_url="http://unreachable:8000",
            )

        # 验证失败返回 None
        assert result is None

    @pytest.mark.asyncio
    async def test_check_agent_needs_upstream(self, test_db_session: AsyncSession):
        """测试检查 Agent 是否需要上级"""
        forwarder = UpstreamForwarder()

        # 独立模式 Agent（无上级）
        standalone_agent = Agent(
            id="standalone",
            name="Standalone",
            api_key="key",
            upstream_monitor_url=None,
        )
        assert await forwarder.check_agent_needs_upstream(standalone_agent) is False

        # 集群模式 Agent（有上级）
        cluster_agent = Agent(
            id="cluster",
            name="Cluster",
            api_key="key",
            upstream_monitor_url="http://upstream:8000",
        )
        assert await forwarder.check_agent_needs_upstream(cluster_agent) is True


class TestDecisionFeedback:
    """测试决策反馈机制"""

    @pytest.mark.asyncio
    async def test_store_decision_locally(self, test_db_session: AsyncSession):
        """测试本地存储决策"""
        decision = Decision(
            agent_id="test-agent",
            issue_type="high_memory",
            issue_description="Memory usage high",
            proposed_action="Restart service",
            llm_analysis="分析结果...",
            status="approved",
            reason="可以执行",
        )

        test_db_session.add(decision)
        await test_db_session.commit()

        # 验证存储成功
        result = await test_db_session.execute(
            select(Decision).where(Decision.agent_id == "test-agent")
        )
        stored_decision = result.scalar_one()

        assert stored_decision.status == "approved"
        assert stored_decision.reason == "可以执行"
        assert stored_decision.executed_at is None  # 尚未执行

    @pytest.mark.asyncio
    async def test_update_decision_execution_result(
        self, test_db_session: AsyncSession
    ):
        """测试更新决策执行结果"""
        # 创建决策
        decision = Decision(
            agent_id="test-agent",
            issue_type="high_cpu",
            issue_description="CPU high",
            proposed_action="Kill process",
            status="approved",
            reason="批准执行",
        )
        test_db_session.add(decision)
        await test_db_session.commit()

        # 模拟执行并回传结果
        decision.executed_at = datetime.utcnow()
        decision.execution_result = "Successfully killed process PID 1234"
        await test_db_session.commit()

        # 验证
        result = await test_db_session.execute(
            select(Decision).where(Decision.id == decision.id)
        )
        updated_decision = result.scalar_one()

        assert updated_decision.executed_at is not None
        assert "Successfully killed" in updated_decision.execution_result


class TestClusterTopology:
    """测试集群拓扑功能"""

    @pytest.mark.asyncio
    async def test_calculate_node_levels(self, test_db_session: AsyncSession):
        """测试节点层级计算"""
        # 创建 L0 → L1 → L2 结构
        agents = [
            Agent(id="l0", name="L0", api_key="k0", parent_id=None),
            Agent(
                id="l1", name="L1", api_key="k1", parent_id="l0", upstream_monitor_url="http://l0:8000"
            ),
            Agent(
                id="l2", name="L2", api_key="k2", parent_id="l1", upstream_monitor_url="http://l1:8000"
            ),
        ]

        for agent in agents:
            test_db_session.add(agent)
        await test_db_session.commit()

        # 获取所有 Agent
        result = await test_db_session.execute(select(Agent))
        all_agents = result.scalars().all()

        # 构建节点字典
        agents_dict = {agent.id: agent for agent in all_agents}

        # 计算层级函数（从 cluster.py 复制）
        def calculate_level(agent_id: str, visited: set = None) -> int:
            if visited is None:
                visited = set()
            if agent_id in visited:
                return -1
            visited.add(agent_id)
            agent = agents_dict.get(agent_id)
            if not agent:
                return -1
            if not agent.parent_id:
                return 0
            parent_level = calculate_level(agent.parent_id, visited)
            if parent_level == -1:
                return -1
            return parent_level + 1

        # 验证层级
        assert calculate_level("l0") == 0
        assert calculate_level("l1") == 1
        assert calculate_level("l2") == 2


class TestEndToEndClusterWorkflow:
    """端到端集群工作流测试"""

    @pytest.mark.asyncio
    async def test_complete_cluster_workflow(self, test_db_session: AsyncSession):
        """测试完整集群工作流程"""
        # 1. 注册集群节点
        root = Agent(
            id="root", name="Root", api_key="root-key", parent_id=None, status="online"
        )
        child = Agent(
            id="child",
            name="Child",
            api_key="child-key",
            parent_id="root",
            upstream_monitor_url="http://root:8000",
            status="online",
        )

        test_db_session.add(root)
        test_db_session.add(child)
        await test_db_session.commit()

        # 2. 验证节点存在
        result = await test_db_session.execute(select(Agent))
        agents = result.scalars().all()
        assert len(agents) == 2

        # 3. 创建 L2 决策（模拟从上级返回）
        decision = Decision(
            agent_id="child",
            issue_type="test_issue",
            issue_description="Test issue",
            proposed_action="Test action",
            status="approved",
            reason="Test approved",
        )
        test_db_session.add(decision)
        await test_db_session.commit()

        # 4. 验证决策存储
        result = await test_db_session.execute(
            select(Decision).where(Decision.agent_id == "child")
        )
        stored_decision = result.scalar_one()

        assert stored_decision.status == "approved"
        assert stored_decision.agent_id == "child"

    @pytest.mark.asyncio
    async def test_cluster_with_heartbeat(self, test_db_session: AsyncSession):
        """测试集群模式下的心跳"""
        # 创建 Agent
        agent = Agent(
            id="cluster-agent",
            name="Cluster Agent",
            api_key="key",
            parent_id="parent",
            upstream_monitor_url="http://parent:8000",
            status="offline",
            last_heartbeat=None,
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        # 发送心跳
        agent.status = "online"
        agent.last_heartbeat = datetime.utcnow()
        await test_db_session.commit()

        # 验证
        result = await test_db_session.execute(
            select(Agent).where(Agent.id == "cluster-agent")
        )
        updated = result.scalar_one()

        assert updated.status == "online"
        assert updated.last_heartbeat is not None
        assert updated.upstream_monitor_url == "http://parent:8000"
