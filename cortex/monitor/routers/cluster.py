"""
集群管理路由
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.monitor.dependencies import get_db_manager
from cortex.monitor.database import Agent, Report

router = APIRouter()


class AgentRegistration(BaseModel):
    """Agent 注册请求"""

    agent_id: str
    name: str
    api_key: str
    metadata: Optional[dict] = None


@router.post("/agents")
async def register_agent(
    agent_reg: AgentRegistration,
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
) -> dict:
    """
    注册新 Agent
    """
    try:
        # 检查是否已存在
        result = await session.execute(select(Agent).where(Agent.id == agent_reg.agent_id))
        existing_agent = result.scalar_one_or_none()

        if existing_agent:
            raise HTTPException(status_code=409, detail="Agent ID already exists")

        # 创建新 Agent
        new_agent = Agent(
            id=agent_reg.agent_id,
            name=agent_reg.name,
            api_key=agent_reg.api_key,
            status="offline",
            health_status="unknown",
            metadata_json=agent_reg.metadata,
        )

        session.add(new_agent)
        await session.commit()

        logger.info(f"New agent registered: {agent_reg.agent_id} ({agent_reg.name})")

        return {
            "success": True,
            "data": {
                "agent_id": new_agent.id,
                "name": new_agent.name,
                "created_at": new_agent.created_at.isoformat(),
            },
            "message": "Agent registered successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering agent: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def list_agents(
    status: Optional[str] = Query(None, description="过滤状态: online/offline"),
    health_status: Optional[str] = Query(None, description="过滤健康状态: healthy/warning/critical"),
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
) -> dict:
    """
    列出所有 Agent
    """
    try:
        query = select(Agent).order_by(Agent.created_at.desc())

        if status:
            query = query.where(Agent.status == status)
        if health_status:
            query = query.where(Agent.health_status == health_status)

        result = await session.execute(query)
        agents = result.scalars().all()

        return {
            "success": True,
            "data": {
                "agents": [
                    {
                        "id": a.id,
                        "name": a.name,
                        "status": a.status,
                        "health_status": a.health_status,
                        "last_heartbeat": a.last_heartbeat.isoformat() if a.last_heartbeat else None,
                        "created_at": a.created_at.isoformat(),
                    }
                    for a in agents
                ],
                "count": len(agents),
            },
            "message": "Agents retrieved successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}")
async def get_agent(
    agent_id: str,
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
) -> dict:
    """
    获取单个 Agent 详情
    """
    try:
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # 查询最近的报告统计
        reports_count_result = await session.execute(
            select(func.count(Report.id)).where(Report.agent_id == agent_id)
        )
        total_reports = reports_count_result.scalar() or 0

        # 查询最近 24 小时的报告数
        last_24h = datetime.utcnow() - timedelta(hours=24)
        recent_reports_result = await session.execute(
            select(func.count(Report.id)).where(
                Report.agent_id == agent_id, Report.timestamp >= last_24h
            )
        )
        recent_reports = recent_reports_result.scalar() or 0

        return {
            "success": True,
            "data": {
                "id": agent.id,
                "name": agent.name,
                "status": agent.status,
                "health_status": agent.health_status,
                "upstream_monitor_url": agent.upstream_monitor_url,
                "last_heartbeat": agent.last_heartbeat.isoformat() if agent.last_heartbeat else None,
                "created_at": agent.created_at.isoformat(),
                "updated_at": agent.updated_at.isoformat(),
                "metadata": agent.metadata_json,
                "statistics": {
                    "total_reports": total_reports,
                    "reports_last_24h": recent_reports,
                },
            },
            "message": "Agent retrieved successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
) -> dict:
    """
    删除 Agent（需要管理员权限）
    """
    try:
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        await session.delete(agent)
        await session.commit()

        logger.warning(f"Agent deleted: {agent_id}")

        return {
            "success": True,
            "data": {"agent_id": agent_id},
            "message": "Agent deleted successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent {agent_id}: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cluster/overview")
async def cluster_overview(
    session: AsyncSession = Depends(lambda: get_db_manager().get_session()),
) -> dict:
    """
    集群全局概览
    """
    try:
        # 统计 Agent 数量
        total_agents_result = await session.execute(select(func.count(Agent.id)))
        total_agents = total_agents_result.scalar() or 0

        online_agents_result = await session.execute(
            select(func.count(Agent.id)).where(Agent.status == "online")
        )
        online_agents = online_agents_result.scalar() or 0

        # 统计健康状态分布
        healthy_result = await session.execute(
            select(func.count(Agent.id)).where(Agent.health_status == "healthy")
        )
        healthy_count = healthy_result.scalar() or 0

        warning_result = await session.execute(
            select(func.count(Agent.id)).where(Agent.health_status == "warning")
        )
        warning_count = warning_result.scalar() or 0

        critical_result = await session.execute(
            select(func.count(Agent.id)).where(Agent.health_status == "critical")
        )
        critical_count = critical_result.scalar() or 0

        # 统计最近 1 小时的报告数
        last_hour = datetime.utcnow() - timedelta(hours=1)
        recent_reports_result = await session.execute(
            select(func.count(Report.id)).where(Report.timestamp >= last_hour)
        )
        recent_reports = recent_reports_result.scalar() or 0

        return {
            "success": True,
            "data": {
                "agents": {
                    "total": total_agents,
                    "online": online_agents,
                    "offline": total_agents - online_agents,
                },
                "health": {
                    "healthy": healthy_count,
                    "warning": warning_count,
                    "critical": critical_count,
                    "unknown": total_agents - healthy_count - warning_count - critical_count,
                },
                "activity": {
                    "reports_last_hour": recent_reports,
                },
            },
            "message": "Cluster overview retrieved successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting cluster overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))
