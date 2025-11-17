"""
L2 决策路由
"""

from datetime import datetime
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.config.settings import get_settings
from cortex.monitor.dependencies import get_db_manager, get_ws_manager
from cortex.monitor.database import Agent, Decision
from cortex.monitor.services.decision_engine import DecisionEngine

router = APIRouter()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（依赖注入）"""
    async for session in get_db_manager().get_session():
        yield session


class DecisionRequest(BaseModel):
    """L2 决策请求（来自子节点）"""

    agent_id: str  # 原始报告此问题的 Agent ID
    issue_type: str
    issue_description: str
    severity: str
    proposed_action: Optional[str] = None
    risk_assessment: Optional[str] = None
    details: Optional[dict] = None


@router.post("/decisions/request")
async def request_decision(
    decision_request: DecisionRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    处理来自子节点的 L2 决策请求

    子节点 Monitor 将 L2 问题转发到此接口，由上级 Monitor 决策。
    """
    try:
        logger.info(
            f"Received L2 decision request from child for agent {decision_request.agent_id}: "
            f"{decision_request.issue_type}"
        )

        # 构造 IssueReport 对象（用于 DecisionEngine）
        from cortex.common.models import IssueReport, Severity

        # 将字符串 severity 转换为 Severity 枚举
        try:
            severity_enum = Severity(decision_request.severity)
        except ValueError:
            severity_enum = Severity.MEDIUM  # 默认值

        issue = IssueReport(
            level="L2",
            type=decision_request.issue_type,
            description=decision_request.issue_description,
            severity=severity_enum,
            proposed_fix=decision_request.proposed_action,
            risk_assessment=decision_request.risk_assessment,
            details=decision_request.details or {},
        )

        # 使用 DecisionEngine 分析
        settings = get_settings()
        decision_engine = DecisionEngine(settings)
        decision = await decision_engine.analyze_and_decide(
            issue, decision_request.agent_id, session
        )

        logger.info(
            f"Decision made for child request: {decision.status.upper()} - {decision.reason}"
        )

        # 广播决策事件
        try:
            ws_manager = get_ws_manager()
            await ws_manager.broadcast_decision_made(
                decision_id=decision.id,
                agent_id=decision_request.agent_id,
                status=decision.status,
                reason=decision.reason
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast decision event: {e}")

        return {
            "success": True,
            "data": {
                "decision_id": decision.id,
                "status": decision.status,
                "reason": decision.reason,
                "llm_analysis": decision.llm_analysis,
                "created_at": decision.created_at.isoformat(),
            },
            "message": "Decision completed",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error processing decision request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decisions")
async def list_decisions(
    agent_id: Optional[str] = Query(None, description="过滤指定 Agent"),
    status: Optional[str] = Query(None, description="过滤状态: approved/rejected"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    查询决策记录
    """
    try:
        query = select(Decision).order_by(Decision.created_at.desc())

        if agent_id:
            query = query.where(Decision.agent_id == agent_id)
        if status:
            query = query.where(Decision.status == status)

        query = query.limit(limit).offset(offset)

        result = await session.execute(query)
        decisions = result.scalars().all()

        return {
            "success": True,
            "data": {
                "decisions": [
                    {
                        "id": d.id,
                        "agent_id": d.agent_id,
                        "issue_type": d.issue_type,
                        "issue_description": d.issue_description,
                        "proposed_action": d.proposed_action,
                        "status": d.status,
                        "reason": d.reason,
                        "created_at": d.created_at.isoformat(),
                        "executed_at": d.executed_at.isoformat() if d.executed_at else None,
                    }
                    for d in decisions
                ],
                "count": len(decisions),
                "limit": limit,
                "offset": offset,
            },
            "message": "Decisions retrieved successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error listing decisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decisions/{decision_id}")
async def get_decision(
    decision_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    获取单个决策详情
    """
    try:
        result = await session.execute(select(Decision).where(Decision.id == decision_id))
        decision = result.scalar_one_or_none()

        if not decision:
            raise HTTPException(status_code=404, detail="Decision not found")

        return {
            "success": True,
            "data": {
                "id": decision.id,
                "agent_id": decision.agent_id,
                "issue_type": decision.issue_type,
                "issue_description": decision.issue_description,
                "proposed_action": decision.proposed_action,
                "llm_analysis": decision.llm_analysis,
                "status": decision.status,
                "reason": decision.reason,
                "created_at": decision.created_at.isoformat(),
                "executed_at": decision.executed_at.isoformat() if decision.executed_at else None,
                "execution_result": decision.execution_result,
            },
            "message": "Decision retrieved successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting decision {decision_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decisions/{decision_id}/feedback")
async def submit_decision_feedback(
    decision_id: int,
    execution_result: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Agent 回传决策执行结果
    """
    try:
        result = await session.execute(select(Decision).where(Decision.id == decision_id))
        decision = result.scalar_one_or_none()

        if not decision:
            raise HTTPException(status_code=404, detail="Decision not found")

        decision.executed_at = datetime.utcnow()
        decision.execution_result = execution_result

        await session.commit()

        logger.info(f"Decision {decision_id} feedback received: {execution_result[:100]}")

        return {
            "success": True,
            "data": {"decision_id": decision_id, "updated_at": decision.executed_at.isoformat()},
            "message": "Feedback received successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback for decision {decision_id}: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
