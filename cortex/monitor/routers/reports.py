"""
数据上报路由
"""

from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.common.cache import invalidate_cache_pattern
from cortex.common.models import ProbeReport
from cortex.config.settings import get_settings
from cortex.monitor.dependencies import get_db_manager, get_ws_manager
from cortex.monitor.database import Agent, Decision, Report
from cortex.monitor.services import AlertAggregator, DecisionEngine, TelegramNotifier
from cortex.monitor.services.upstream_forwarder import UpstreamForwarder

router = APIRouter()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（依赖注入）"""
    async for session in get_db_manager().get_session():
        yield session


@router.post("/reports")
async def receive_report(
    report: ProbeReport,
    session: AsyncSession = Depends(get_session),
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
                last_heartbeat=datetime.now(timezone.utc),
            )
            session.add(agent)
        else:
            # 2. 更新心跳和状态
            agent.status = "online"
            agent.health_status = report.status.value
            agent.last_heartbeat = datetime.now(timezone.utc)

        # 3. 存储报告
        db_report = Report(
            agent_id=report.agent_id,
            timestamp=report.timestamp,
            status=report.status.value,
            metrics=report.metrics.model_dump(mode='json'),
            issues=[issue.model_dump(mode='json') for issue in report.issues],
            actions_taken=[action.model_dump(mode='json') for action in report.actions_taken],
            metadata_json=report.metadata,
        )
        session.add(db_report)

        await session.commit()

        logger.info(
            f"Report received from {report.agent_id}, status: {report.status}, "
            f"issues: {len(report.issues)}, actions: {len(report.actions_taken)}"
        )

        # 广播报告接收事件
        try:
            ws_manager = get_ws_manager()
            await ws_manager.broadcast_report_received(
                agent_id=report.agent_id,
                report_id=db_report.id,
                summary={
                    "status": report.status.value,
                    "issues_count": len(report.issues),
                    "actions_count": len(report.actions_taken),
                }
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast report event: {e}")

        # 4. 处理 L2 决策请求
        settings = get_settings()
        l2_decisions = []

        l2_issues = [issue for issue in report.issues if issue.level == "L2"]
        if l2_issues:
            logger.info(f"Processing {len(l2_issues)} L2 issues from {report.agent_id}")

            # 检查是否需要转发到上级 Monitor（集群模式）
            if agent.upstream_monitor_url:
                logger.info(
                    f"Cluster mode detected: forwarding {len(l2_issues)} L2 issues to upstream "
                    f"{agent.upstream_monitor_url}"
                )
                upstream_forwarder = UpstreamForwarder()

                for issue in l2_issues:
                    decision_data = await upstream_forwarder.forward_decision_request(
                        issue, report.agent_id, agent.upstream_monitor_url
                    )

                    if decision_data:
                        # 保存上级的决策到本地数据库（作为记录）
                        decision = Decision(
                            agent_id=report.agent_id,
                            issue_type=issue.type,
                            issue_description=issue.description,
                            proposed_action=issue.proposed_fix or "",
                            llm_analysis=decision_data.get("llm_analysis"),
                            status=decision_data["status"],
                            reason=decision_data["reason"],
                        )
                        session.add(decision)
                        l2_decisions.append(decision)
                    else:
                        logger.error(
                            f"Failed to get decision from upstream for {issue.type}, "
                            f"falling back to local decision"
                        )
                        # 上级失败时，回退到本地决策
                        decision_engine = DecisionEngine(settings)
                        decision = await decision_engine.analyze_and_decide(
                            issue, report.agent_id, session
                        )
                        l2_decisions.append(decision)

                await session.commit()
            else:
                # 独立模式：本地决策
                logger.debug("Standalone mode: processing L2 issues locally")
                decision_engine = DecisionEngine(settings)
                l2_decisions = await decision_engine.batch_analyze(
                    l2_issues, report.agent_id, session
                )

        # 广播 L2 决策事件
        if l2_decisions:
            try:
                ws_manager = get_ws_manager()
                for decision in l2_decisions:
                    await ws_manager.broadcast_decision_made(
                        decision_id=decision.id,
                        agent_id=report.agent_id,
                        status=decision.status,
                        reason=decision.reason
                    )
            except Exception as e:
                logger.warning(f"Failed to broadcast decision events: {e}")

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

            # 广播 L3 告警事件
            try:
                ws_manager = get_ws_manager()
                for alert in l3_alerts:
                    await ws_manager.broadcast_alert_triggered(
                        alert_id=alert.id,
                        agent_id=report.agent_id,
                        level=alert.level,
                        alert_type=alert.type,
                        description=alert.description
                    )
            except Exception as e:
                logger.warning(f"Failed to broadcast alert events: {e}")

        # 清除集群概览缓存（报告影响统计数据）
        await invalidate_cache_pattern("cluster:overview")

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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error processing report: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/heartbeat")
async def receive_heartbeat(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
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
        agent.last_heartbeat = datetime.now(timezone.utc)

        await session.commit()

        return {
            "success": True,
            "data": {"received_at": datetime.now(timezone.utc).isoformat()},
            "message": "Heartbeat received",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing heartbeat: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
