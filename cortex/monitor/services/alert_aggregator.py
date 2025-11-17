"""
L3 告警聚合器
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.common.intent_recorder import IntentRecorder
from cortex.common.models import IssueReport
from cortex.config.settings import Settings
from cortex.monitor.database import Alert


class AlertAggregator:
    """
    L3 告警聚合器

    负责：
    1. 接收来自多个 Agent 的 L3 级告警
    2. 去重和聚合相似告警
    3. 存储到数据库
    4. 触发通知（Telegram/Email）
    """

    # 告警去重时间窗口（分钟）
    DEDUP_WINDOW_MINUTES = 30

    # 相似度阈值：如果两个告警的类型相同且描述相似度超过此值，则认为是重复告警
    SIMILARITY_THRESHOLD = 0.8

    def __init__(self, settings: Settings) -> None:
        """
        初始化告警聚合器

        Args:
            settings: 全局配置
        """
        self.settings = settings
        self.intent_recorder = IntentRecorder(settings)

    async def process_issues(
        self, issues: List[IssueReport], agent_id: str, session: AsyncSession
    ) -> List[Alert]:
        """
        处理来自 Probe 的 L3 问题列表

        Args:
            issues: L3 级问题列表
            agent_id: 报告此问题的 Agent ID
            session: 数据库会话

        Returns:
            创建的告警列表（已去重）
        """
        alerts_created = []

        for issue in issues:
            # 检查是否是重复告警
            is_duplicate = await self._check_duplicate(issue, agent_id, session)

            if is_duplicate:
                logger.info(
                    f"Duplicate alert detected for {agent_id}/{issue.type}, skipping creation"
                )
                continue

            # 创建新告警
            alert = await self._create_alert(issue, agent_id, session)
            alerts_created.append(alert)

            logger.warning(
                f"L3 Alert created: [{alert.severity}] {alert.type} from {agent_id}: {alert.description[:100]}"
            )

        return alerts_created

    async def _check_duplicate(
        self, issue: IssueReport, agent_id: str, session: AsyncSession
    ) -> bool:
        """
        检查是否存在重复告警

        Args:
            issue: 问题报告
            agent_id: Agent ID
            session: 数据库会话

        Returns:
            True 如果是重复告警
        """
        # 查询最近 DEDUP_WINDOW_MINUTES 分钟内相同类型的未解决告警
        time_threshold = datetime.now(timezone.utc) - timedelta(minutes=self.DEDUP_WINDOW_MINUTES)

        result = await session.execute(
            select(Alert)
            .where(
                Alert.agent_id == agent_id,
                Alert.type == issue.type,
                Alert.status.in_(["new", "acknowledged"]),  # 未解决的告警
                Alert.created_at >= time_threshold,
            )
            .order_by(Alert.created_at.desc())
            .limit(5)  # 只检查最近的 5 条
        )

        recent_alerts = result.scalars().all()

        if not recent_alerts:
            return False

        # 简单的去重策略：如果存在相同类型的未解决告警，认为是重复
        # TODO: 可以改进为基于描述文本相似度的去重
        return True

    async def _create_alert(
        self, issue: IssueReport, agent_id: str, session: AsyncSession
    ) -> Alert:
        """
        创建告警记录

        Args:
            issue: 问题报告
            agent_id: Agent ID
            session: 数据库会话

        Returns:
            Alert 对象（已保存到数据库）
        """
        # 初始化 Intent 记录器（如果未初始化）
        await self.intent_recorder.initialize()

        alert = Alert(
            agent_id=agent_id,
            level="L3",
            type=issue.type,
            description=issue.description,
            severity=issue.severity.value,
            status="new",
            details={
                "proposed_fix": issue.proposed_fix,
                "risk_assessment": issue.risk_assessment,
                **issue.details,  # 合并原有的 details
            },
        )

        session.add(alert)
        await session.commit()
        await session.refresh(alert)

        # 记录 L3 告警到 Intent Engine
        await self.intent_recorder.record_blocker(
            agent_id=agent_id,
            category=issue.type,
            description=f"L3 Alert created: {issue.description}",
            metadata={
                "severity": issue.severity.value,
                "proposed_fix": issue.proposed_fix,
                "risk_assessment": issue.risk_assessment,
                "alert_id": alert.id,
                "details": issue.details,
            },
        )

        return alert

    async def get_pending_alerts(
        self, session: AsyncSession, limit: int = 50
    ) -> List[Alert]:
        """
        获取所有待处理的告警（用于批量通知）

        Args:
            session: 数据库会话
            limit: 最大返回数量

        Returns:
            待处理告警列表
        """
        result = await session.execute(
            select(Alert)
            .where(Alert.status == "new")
            .order_by(Alert.created_at.desc())
            .limit(limit)
        )

        return list(result.scalars().all())

    async def get_alerts_summary(self, session: AsyncSession, hours: int = 24) -> dict:
        """
        获取告警摘要统计

        Args:
            session: 数据库会话
            hours: 统计最近 N 小时的告警

        Returns:
            统计信息字典
        """
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

        # 查询最近 N 小时的所有告警
        result = await session.execute(
            select(Alert).where(Alert.created_at >= time_threshold)
        )

        alerts = result.scalars().all()

        # 按严重性分组统计
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        status_counts = {"new": 0, "acknowledged": 0, "resolved": 0}
        agent_counts = {}

        for alert in alerts:
            severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1
            status_counts[alert.status] = status_counts.get(alert.status, 0) + 1

            if alert.agent_id not in agent_counts:
                agent_counts[alert.agent_id] = 0
            agent_counts[alert.agent_id] += 1

        return {
            "total_alerts": len(alerts),
            "time_range_hours": hours,
            "by_severity": severity_counts,
            "by_status": status_counts,
            "by_agent": agent_counts,
            "top_agents": sorted(agent_counts.items(), key=lambda x: x[1], reverse=True)[:5],
        }

    def format_alert_for_notification(self, alert: Alert) -> str:
        """
        格式化告警为通知消息

        Args:
            alert: 告警对象

        Returns:
            格式化的消息文本
        """
        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }

        emoji = severity_emoji.get(alert.severity, "⚠️")

        message = f"""{emoji} **L3 告警**

**严重性**: {alert.severity.upper()}
**Agent**: {alert.agent_id}
**类型**: {alert.type}
**时间**: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}

**描述**:
{alert.description}

**详细信息**: 查看 Monitor Web UI (Alert ID: {alert.id})
"""

        return message

    async def format_summary_for_notification(
        self, session: AsyncSession, hours: int = 24
    ) -> str:
        """
        格式化告警摘要为通知消息

        Args:
            session: 数据库会话
            hours: 统计时间范围

        Returns:
            格式化的摘要消息
        """
        summary = await self.get_alerts_summary(session, hours)

        message = f"""📊 **告警摘要报告** (最近 {hours} 小时)

**总计**: {summary['total_alerts']} 条告警

**按严重性**:
- 🔴 Critical: {summary['by_severity']['critical']}
- 🟠 High: {summary['by_severity']['high']}
- 🟡 Medium: {summary['by_severity']['medium']}
- 🟢 Low: {summary['by_severity']['low']}

**按状态**:
- 🆕 New: {summary['by_status']['new']}
- ✅ Acknowledged: {summary['by_status']['acknowledged']}
- ✔️ Resolved: {summary['by_status']['resolved']}

**告警最多的 Agent**:
"""

        for agent_id, count in summary["top_agents"]:
            message += f"- {agent_id}: {count} 条\n"

        return message
