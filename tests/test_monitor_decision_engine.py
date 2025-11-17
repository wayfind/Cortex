"""
DecisionEngine 测试
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.common.models import IssueReport
from cortex.monitor.database import Decision
from cortex.monitor.services.decision_engine import DecisionEngine


@pytest.fixture
def decision_engine(test_settings):
    """创建 DecisionEngine 实例（使用真实的测试配置）"""
    return DecisionEngine(test_settings)


@pytest.fixture
def sample_issue():
    """创建示例问题报告"""
    return IssueReport(
        level="L2",
        type="high_memory",
        severity="high",
        description="Memory usage at 92%, application performance degraded",
        proposed_fix="Restart the memory-intensive service",
        risk_assessment="Medium risk - may cause brief service interruption",
        details={"service_name": "data-processor", "memory_usage_mb": 7500},
    )


@pytest.mark.asyncio
async def test_analyze_and_decide_approve(decision_engine, sample_issue, test_db_session):
    """测试 LLM 批准决策"""
    # Mock Anthropic API 响应
    mock_message = MagicMock()
    mock_message.content = [
        MagicMock(
            text="""DECISION: APPROVE
REASON: The service restart is a standard operation with low risk
ANALYSIS: Memory usage at 92% is critical and requires immediate action.
Restarting the service is the most effective solution."""
        )
    ]

    with patch.object(decision_engine.client.messages, "create", return_value=mock_message):
        decision = await decision_engine.analyze_and_decide(
            issue=sample_issue, agent_id="test-agent-001", session=test_db_session
        )

    assert isinstance(decision, Decision)
    assert decision.agent_id == "test-agent-001"
    assert decision.issue_type == "high_memory"
    assert decision.status == "approved"
    assert "standard operation" in decision.reason
    assert decision.llm_analysis is not None


@pytest.mark.asyncio
async def test_analyze_and_decide_reject(decision_engine, test_db_session):
    """测试 LLM 拒绝决策"""
    risky_issue = IssueReport(
        level="L2",
        type="database_corruption",
        severity="critical",
        description="Database index corruption detected",
        proposed_fix="DROP and RECREATE all indexes",
        risk_assessment="High risk - potential data loss",
        details={"affected_tables": ["users", "orders"]},
    )

    # Mock Anthropic API 响应 - 拒绝
    mock_message = MagicMock()
    mock_message.content = [
        MagicMock(
            text="""DECISION: REJECT
REASON: Dropping indexes may cause data loss and requires manual verification
ANALYSIS: This operation is too risky to approve automatically."""
        )
    ]

    with patch.object(decision_engine.client.messages, "create", return_value=mock_message):
        decision = await decision_engine.analyze_and_decide(
            issue=risky_issue, agent_id="test-agent-002", session=test_db_session
        )

    assert decision.status == "rejected"
    assert "data loss" in decision.reason or "risky" in decision.reason


@pytest.mark.asyncio
async def test_analyze_and_decide_api_error(decision_engine, sample_issue, test_db_session):
    """测试 API 调用失败时的错误处理"""
    # Mock API 错误
    with patch.object(
        decision_engine.client.messages, "create", side_effect=Exception("API connection failed")
    ):
        decision = await decision_engine.analyze_and_decide(
            issue=sample_issue, agent_id="test-agent-003", session=test_db_session
        )

    # 失败时应该默认拒绝
    assert decision.status == "rejected"
    assert "error" in decision.reason.lower() or "failed" in decision.reason.lower()


@pytest.mark.asyncio
async def test_parse_llm_response_valid(decision_engine):
    """测试解析有效的 LLM 响应"""
    response_text = """DECISION: APPROVE
REASON: Safe operation with minimal risk
ANALYSIS: This is a detailed analysis of the situation."""

    status, reason, analysis = decision_engine._parse_llm_response(response_text)

    assert status == "approved"
    assert reason == "Safe operation with minimal risk"
    assert "detailed analysis" in analysis


@pytest.mark.asyncio
async def test_parse_llm_response_invalid_format(decision_engine):
    """测试解析格式错误的 LLM 响应"""
    invalid_response = "This is not a properly formatted response"

    status, reason, analysis = decision_engine._parse_llm_response(invalid_response)

    # 格式错误时应该默认拒绝
    assert status == "rejected"
    # 实现返回中文 reason，analysis 包含原始输出
    assert reason == "见详细分析" or "无法解析" in reason
    assert analysis == invalid_response  # 原始输出作为分析


@pytest.mark.asyncio
async def test_decision_saved_to_database(decision_engine, sample_issue, test_db_session):
    """测试决策是否正确保存到数据库"""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="DECISION: APPROVE\nREASON: Test reason")]

    with patch.object(decision_engine.client.messages, "create", return_value=mock_message):
        decision = await decision_engine.analyze_and_decide(
            issue=sample_issue, agent_id="test-agent-004", session=test_db_session
        )

    # 验证数据库中的记录
    await test_db_session.refresh(decision)
    assert decision.id is not None
    assert decision.created_at is not None
