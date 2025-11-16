"""
告警管理路由
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.monitor.dependencies import get_db_manager
from cortex.monitor.database import Alert

router = APIRouter()


class AlertAcknowledgement(BaseModel):
    """告警确认"""

    acknowledged_by: str
    notes: Optional[str] = None


class AlertResolution(BaseModel):
    """告警解决"""

    notes: Optional[str] = None


@router.get("/alerts")
async def list_alerts(
    agent_id: Optional[str] = Query(None, description="过滤指定 Agent"),
    level: Optional[str] = Query(None, description="过滤级别: L1/L2/L3"),
    status: Optional[str] = Query(None, description="过滤状态: new/acknowledged/resolved"),
    severity: Optional[str] = Query(None, description="过滤严重性: low/medium/high/critical"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
) -> dict:
    """
    查询告警列表
    """
    try:
        query = select(Alert).order_by(Alert.created_at.desc())

        if agent_id:
            query = query.where(Alert.agent_id == agent_id)
        if level:
            query = query.where(Alert.level == level)
        if status:
            query = query.where(Alert.status == status)
        if severity:
            query = query.where(Alert.severity == severity)

        query = query.limit(limit).offset(offset)

        result = await session.execute(query)
        alerts = result.scalars().all()

        return {
            "success": True,
            "data": {
                "alerts": [
                    {
                        "id": a.id,
                        "agent_id": a.agent_id,
                        "level": a.level,
                        "type": a.type,
                        "description": a.description,
                        "severity": a.severity,
                        "status": a.status,
                        "created_at": a.created_at.isoformat(),
                        "acknowledged_at": a.acknowledged_at.isoformat()
                        if a.acknowledged_at
                        else None,
                        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
                    }
                    for a in alerts
                ],
                "count": len(alerts),
                "limit": limit,
                "offset": offset,
            },
            "message": "Alerts retrieved successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error listing alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/{alert_id}")
async def get_alert(
    alert_id: int,
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
) -> dict:
    """
    获取单个告警详情
    """
    try:
        result = await session.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        return {
            "success": True,
            "data": {
                "id": alert.id,
                "agent_id": alert.agent_id,
                "level": alert.level,
                "type": alert.type,
                "description": alert.description,
                "severity": alert.severity,
                "status": alert.status,
                "details": alert.details,
                "created_at": alert.created_at.isoformat(),
                "acknowledged_at": alert.acknowledged_at.isoformat()
                if alert.acknowledged_at
                else None,
                "acknowledged_by": alert.acknowledged_by,
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                "notes": alert.notes,
            },
            "message": "Alert retrieved successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    ack: AlertAcknowledgement,
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
) -> dict:
    """
    确认告警
    """
    try:
        result = await session.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        if alert.status != "new":
            raise HTTPException(status_code=400, detail="Alert already acknowledged or resolved")

        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = ack.acknowledged_by

        if ack.notes:
            alert.notes = ack.notes

        await session.commit()

        logger.info(f"Alert {alert_id} acknowledged by {ack.acknowledged_by}")

        return {
            "success": True,
            "data": {
                "alert_id": alert_id,
                "status": alert.status,
                "acknowledged_at": alert.acknowledged_at.isoformat(),
            },
            "message": "Alert acknowledged successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert {alert_id}: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    resolution: AlertResolution,
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
) -> dict:
    """
    解决告警
    """
    try:
        result = await session.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        if alert.status == "resolved":
            raise HTTPException(status_code=400, detail="Alert already resolved")

        alert.status = "resolved"
        alert.resolved_at = datetime.utcnow()

        if resolution.notes:
            if alert.notes:
                alert.notes += f"\n\n[Resolved] {resolution.notes}"
            else:
                alert.notes = f"[Resolved] {resolution.notes}"

        await session.commit()

        logger.info(f"Alert {alert_id} resolved")

        return {
            "success": True,
            "data": {"alert_id": alert_id, "status": alert.status, "resolved_at": alert.resolved_at.isoformat()},
            "message": "Alert resolved successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert {alert_id}: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
