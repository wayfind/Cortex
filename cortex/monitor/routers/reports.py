"""
数据上报路由
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.common.models import ProbeReport
from cortex.config.settings import get_settings
from cortex.monitor.app import get_db_manager
from cortex.monitor.database import Agent, Report
from cortex.monitor.services import AlertAggregator, DecisionEngine, TelegramNotifier

router = APIRouter()


@router.post("/reports")
async def receive_report(
    report: ProbeReport,
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
) -> dict:
    """
    接收 Probe 上报数据

    处理流程：
    1. 验证 agent_id
    2. 更新心跳时间
    3. 存储报告到数据库
    4. 处理 L2 决策请求（如有）
    5. 触发 L3 告警（如有）
    """
    try:
        # 1. 查询 Agent
        result = await session.execute(select(Agent).where(Agent.id == report.agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            logger.warning(f"Agent not found: {report.agent_id}, creating new entry")
            # 自动注册新 Agent（独立模式）
            agent = Agent(
                id=report.agent_id,
                name=report.agent_id,
                api_key=f"auto_generated_{report.agent_id}",  # TODO: 生成真实的 API Key
                status="online",
                health_status=report.status.value,
                last_heartbeat=datetime.utcnow(),
            )
            session.add(agent)
        else:
            # 2. 更新心跳和状态
            agent.status = "online"
            agent.health_status = report.status.value
            agent.last_heartbeat = datetime.utcnow()

        # 3. 存储报告
        db_report = Report(
            agent_id=report.agent_id,
            timestamp=report.timestamp,
            status=report.status.value,
            metrics=report.metrics.model_dump(),
            issues=[issue.model_dump() for issue in report.issues],
            actions_taken=[action.model_dump() for action in report.actions_taken],
            metadata_json=report.metadata,
        )
        session.add(db_report)

        await session.commit()

        logger.info(
            f"Report received from {report.agent_id}, status: {report.status}, "
            f"issues: {len(report.issues)}, actions: {len(report.actions_taken)}"
        )

        # 4. 处理 L2 决策请求
        settings = get_settings()
        decision_engine = DecisionEngine(settings)
        l2_decisions = []

        l2_issues = [issue for issue in report.issues if issue.level == "L2"]
        if l2_issues:
            logger.info(f"Processing {len(l2_issues)} L2 issues from {report.agent_id}")
            l2_decisions = await decision_engine.batch_analyze(l2_issues, report.agent_id, session)

        # 5. 处理 L3 告警
        alert_aggregator = AlertAggregator(settings)
        l3_alerts = []

        l3_issues = [issue for issue in report.issues if issue.level == "L3"]
        if l3_issues:
            logger.warning(f"Processing {len(l3_issues)} L3 issues from {report.agent_id}")
            l3_alerts = await alert_aggregator.process_issues(l3_issues, report.agent_id, session)

            # 发送 Telegram 通知
            if l3_alerts:
                telegram_notifier = TelegramNotifier(settings)
                await telegram_notifier.send_batch_alerts(l3_alerts)

        return {
            "success": True,
            "data": {
                "report_id": db_report.id,
                "l2_decisions": [
                    {
                        "decision_id": d.id,
                        "issue_type": d.issue_type,
                        "status": d.status,
                        "reason": d.reason,
                    }
                    for d in l2_decisions
                ],
                "l3_alerts_triggered": len(l3_alerts),
            },
            "message": "Report received successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error processing report: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/heartbeat")
async def receive_heartbeat(
    agent_id: str,
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
) -> dict:
    """
    接收心跳数据（轻量级上报）
    """
    try:
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        agent.status = "online"
        agent.last_heartbeat = datetime.utcnow()

        await session.commit()

        return {
            "success": True,
            "data": {"received_at": datetime.utcnow().isoformat()},
            "message": "Heartbeat received",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing heartbeat: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
