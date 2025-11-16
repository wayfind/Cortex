"""
L2 决策路由
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.monitor.dependencies import get_db_manager
from cortex.monitor.database import Agent, Decision

router = APIRouter()


@router.get("/decisions")
async def list_decisions(
    agent_id: Optional[str] = Query(None, description="过滤指定 Agent"),
    status: Optional[str] = Query(None, description="过滤状态: approved/rejected"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
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
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
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
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
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
