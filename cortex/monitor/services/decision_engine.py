"""
L2 决策引擎
"""

from datetime import datetime
from typing import Optional

from anthropic import Anthropic
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.common.intent_recorder import IntentRecorder
from cortex.common.models import IssueReport
from cortex.config.settings import Settings
from cortex.monitor.database import Decision


class DecisionEngine:
    """
    L2 决策引擎

    使用 LLM 分析 L2 级问题，评估风险并做出批准/拒绝决策
    """

    DECISION_PROMPT_TEMPLATE = """你是一个运维决策系统的智能助手。需要你分析以下运维问题并决定是否批准建议的修复操作。

**问题信息：**
- 类型：{issue_type}
- 描述：{issue_description}
- 严重性：{severity}

**建议的修复操作：**
{proposed_action}

**风险评估（来自 Probe）：**
{risk_assessment}

**你的任务：**
1. 分析问题的严重性和影响范围
2. 评估建议操作的风险和潜在副作用
3. 考虑是否有更安全的替代方案
4. 做出决策：APPROVE（批准）或 REJECT（拒绝）

**输出格式（严格按此格式）：**
DECISION: [APPROVE 或 REJECT]
REASON: [简短说明理由，1-2 句话]
ANALYSIS: [详细分析，可选]

**决策原则：**
- 如果操作风险低且能有效解决问题，批准
- 如果操作可能影响业务或数据安全，拒绝
- 如果信息不足以做判断，拒绝并说明需要更多信息
- 优先考虑系统稳定性和数据安全
"""

    def __init__(self, settings: Settings) -> None:
        """
        初始化决策引擎

        Args:
            settings: 全局配置
        """
        self.settings = settings
        self.client = Anthropic(api_key=settings.claude.api_key)
        self.intent_recorder = IntentRecorder(settings)

    async def analyze_and_decide(
        self, issue: IssueReport, agent_id: str, session: AsyncSession
    ) -> Decision:
        """
        分析 L2 问题并做出决策

        Args:
            issue: 问题报告
            agent_id: 报告此问题的 Agent ID
            session: 数据库会话

        Returns:
            Decision 对象（已保存到数据库）
        """
        logger.info(
            f"Analyzing L2 issue from {agent_id}: {issue.type} - {issue.description[:50]}..."
        )

        # 初始化 Intent 记录器（如果未初始化）
        await self.intent_recorder.initialize()

        # 构造提示词
        prompt = self.DECISION_PROMPT_TEMPLATE.format(
            issue_type=issue.type,
            issue_description=issue.description,
            severity=issue.severity.value,
            proposed_action=issue.proposed_fix or "（未提供具体修复建议）",
            risk_assessment=issue.risk_assessment or "（未提供风险评估）",
        )

        # 调用 Claude API
        try:
            response = self.client.messages.create(
                model=self.settings.claude.model,
                max_tokens=self.settings.claude.max_tokens,
                temperature=self.settings.claude.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            llm_output = response.content[0].text
            logger.debug(f"LLM response: {llm_output[:200]}...")

            # 解析 LLM 输出
            decision_status, reason, analysis = self._parse_llm_response(llm_output)

        except Exception as e:
            logger.error(f"Error calling Claude API: {e}", exc_info=True)
            # 失败时默认拒绝
            decision_status = "rejected"
            reason = f"LLM 分析失败: {str(e)}"
            analysis = None

        # 创建决策记录
        decision = Decision(
            agent_id=agent_id,
            issue_type=issue.type,
            issue_description=issue.description,
            proposed_action=issue.proposed_fix or "",
            llm_analysis=analysis,
            status=decision_status,
            reason=reason,
        )

        session.add(decision)
        await session.commit()
        await session.refresh(decision)

        logger.info(
            f"Decision made for {agent_id}/{issue.type}: {decision_status.upper()} - {reason}"
        )

        # 记录 L2 决策到 Intent Engine
        await self.intent_recorder.record_decision(
            agent_id=agent_id,
            level="L2",
            category=issue.type,
            description=f"LLM decision for {issue.type}: {decision_status.upper()} - {reason}",
            status=decision_status,
            metadata={
                "issue_description": issue.description,
                "proposed_action": issue.proposed_fix,
                "severity": issue.severity.value,
                "llm_reason": reason,
                "llm_analysis": analysis,
                "decision_id": decision.id,
            },
        )

        return decision

    def _parse_llm_response(self, llm_output: str) -> tuple[str, str, Optional[str]]:
        """
        解析 LLM 的输出格式

        Args:
            llm_output: LLM 返回的文本

        Returns:
            (decision_status, reason, analysis)
            decision_status: "approved" 或 "rejected"
            reason: 简短理由
            analysis: 详细分析（可选）
        """
        lines = llm_output.strip().split("\n")

        decision_status = "rejected"  # 默认拒绝
        reason = "无法解析 LLM 输出"
        analysis = None

        for line in lines:
            line = line.strip()
            if line.startswith("DECISION:"):
                decision_text = line.replace("DECISION:", "").strip().upper()
                if "APPROVE" in decision_text:
                    decision_status = "approved"
                elif "REJECT" in decision_text:
                    decision_status = "rejected"

            elif line.startswith("REASON:"):
                reason = line.replace("REASON:", "").strip()

            elif line.startswith("ANALYSIS:"):
                analysis = line.replace("ANALYSIS:", "").strip()

        # 如果没有找到 REASON，使用完整输出作为分析
        if reason == "无法解析 LLM 输出" and llm_output:
            analysis = llm_output
            reason = "见详细分析"

        return decision_status, reason, analysis

    async def batch_analyze(
        self, issues: list[IssueReport], agent_id: str, session: AsyncSession
    ) -> list[Decision]:
        """
        批量分析多个 L2 问题

        Args:
            issues: 问题列表
            agent_id: Agent ID
            session: 数据库会话

        Returns:
            决策列表
        """
        decisions = []
        for issue in issues:
            try:
                decision = await self.analyze_and_decide(issue, agent_id, session)
                decisions.append(decision)
            except Exception as e:
                logger.error(f"Error analyzing issue {issue.type}: {e}", exc_info=True)
                # 继续处理下一个

        return decisions
